"""Architecture visualization and explainable pattern page rendering."""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
import streamlit as st

from app.models.schemas import PatternResult, SegmentResult
from app.observability.trace_store import get_trace_store
from app.services.telemetry import TelemetryService
from app.ui.theme import (
    CHART_LAYOUT,
    badge,
    callout,
    kpi_grid,
    panel,
    provenance_badge,
)
from app.ui.token_charts import render_token_utilization


def _fmt_ms(value: float | int | None) -> str:
    if value is None:
        return "—"
    v = float(value)
    if v >= 1000:
        return f"{v/1000:.2f} s"
    return f"{v:.0f} ms"


def _fmt_pct(value: float | int | None) -> str:
    if value is None:
        return "—"
    v = float(value)
    if v <= 1:
        return f"{v:.0%}"
    return f"{v:.1f}%"


def _visible_segments(result: PatternResult) -> list[SegmentResult]:
    if result.pattern_id == "router":
        return [s for s in result.segments if not s.segment.startswith("REQ-")]
    return list(result.segments)


def render_kpi_row(cards: dict[str, Any], extras: dict[str, Any] | None = None) -> None:
    extras = extras or {}
    items = [
        ("Endpoints", cards.get("endpoints", 0), "Fleet size"),
        ("Healthy", cards.get("healthy", 0), "Risk < 30"),
        ("At Risk", cards.get("at_risk", 0), "Risk 30–69"),
        ("Critical", cards.get("critical", 0), "Risk ≥ 70"),
        ("Cost Avoided*", f"{cards.get('estimated_cost_avoided', 0)}", "Illustrative USD"),
        ("SLM Calls", cards.get("slm_calls", 0), "Routine capacity"),
        ("Frontier Calls", cards.get("frontier_calls", 0), "Reasoning capacity"),
        ("SLM Tokens", cards.get("slm_tokens", 0), "High-volume path"),
        ("Frontier Tokens", cards.get("frontier_tokens", 0), "Premium path"),
        ("Frontier Calls Avoided", cards.get("frontier_calls_avoided", 0), "Primary efficiency"),
        ("Frontier Tokens Avoided", extras.get("frontier_tokens_avoided", cards.get("frontier_tokens_avoided", 0)), "Primary metric"),
        ("Avg Latency", _fmt_ms(extras.get("average_latency_ms")), "Across model calls"),
        ("P95 Latency", _fmt_ms(extras.get("p95_latency_ms")), "Tail latency"),
        ("Avg Confidence", _fmt_pct(extras.get("average_confidence")), "Quality signal"),
        ("Estimated Cost*", f"{extras.get('estimated_cost', 0)}", "Illustrative USD"),
    ]
    kpi_grid(items)
    st.caption(cards.get("pricing_disclaimer", "Illustrative pricing — configure using current provider pricing."))
    st.caption("What this means: Frontier avoidance preserves premium model capacity for ambiguous/complex work.")


def render_node(segment: SegmentResult) -> None:
    alt = segment.alternative
    st.markdown(
        f"""
<div class="node-card">
  {badge(segment.model_type.value)} {provenance_badge(segment.provenance)}
  <div style="font-weight:700;margin:0.35rem 0 0.2rem 0;color:#f8fafc;">{segment.segment}</div>
  <div class="meta">
    Task: {segment.task}<br/>
    Model: {segment.model_name}<br/>
    Tokens: {segment.tokens} · Latency: {_fmt_ms(segment.latency_ms)} · Confidence: {_fmt_pct(segment.confidence)}<br/>
    Why: {segment.why}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    if alt:
        with st.expander(f"What if {alt.model_type.value} instead?"):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Alt Tokens (ESTIMATED)", alt.expected_tokens)
            c2.metric("Alt Latency", _fmt_ms(alt.expected_latency_ms))
            c3.metric("Alt Confidence", _fmt_pct(alt.expected_confidence))
            c4.metric("Alt Cost*", alt.expected_cost)
            st.write(f"**Recommendation:** {alt.recommendation}")
            st.caption(alt.rationale)


def render_architecture_flow(result: PatternResult) -> None:
    st.markdown("### 2) Architecture Flow")
    st.caption("Every node explicitly labels SLM, FRONTIER, or NON-LLM. Color is supportive, not required.")
    segments = _visible_segments(result)
    cols = st.columns(2)
    for idx, segment in enumerate(segments):
        with cols[idx % 2]:
            render_node(segment)
    if result.pattern_id == "router":
        callout(
            "Router request children are aggregated here. Use the Router Tail View below or Trace Explorer for request-level drill-down.",
            "info",
        )


def render_why_this_model(result: PatternResult) -> None:
    st.markdown("### 3) Why This Model?")
    rows = []
    for segment in _visible_segments(result):
        alt = segment.alternative
        token_delta = None
        latency_delta = None
        quality_delta = None
        if alt and segment.tokens:
            token_delta = round(100.0 * (alt.expected_tokens - segment.tokens) / max(1, segment.tokens), 1)
            latency_delta = round(
                100.0 * (alt.expected_latency_ms - segment.latency_ms) / max(1.0, segment.latency_ms), 1
            )
            quality_delta = round((alt.expected_confidence - segment.confidence) * 100, 1)
        rows.append(
            {
                "Segment": segment.segment,
                "Selected": segment.model_type.value,
                "Selected Tokens": segment.tokens,
                "Selected Latency": _fmt_ms(segment.latency_ms),
                "Selected Confidence": _fmt_pct(segment.confidence),
                "Alternative": alt.model_type.value if alt else "—",
                "Alt Tokens (ESTIMATED)": alt.expected_tokens if alt else "—",
                "Alt Latency (ESTIMATED)": _fmt_ms(alt.expected_latency_ms) if alt else "—",
                "Alt Confidence (ESTIMATED)": _fmt_pct(alt.expected_confidence) if alt else "—",
                "Token Δ %": token_delta if token_delta is not None else "—",
                "Latency Δ %": latency_delta if latency_delta is not None else "—",
                "Quality Δ pp": quality_delta if quality_delta is not None else "—",
                "Decision": segment.decision,
                "Why": segment.decision_why or segment.why,
                "Provenance": segment.provenance,
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)
    callout(
        "Fewer tokens is not automatically better. Prefer Frontier when confidence/quality requirements justify the extra inference.",
        "info",
    )


def render_performance_comparison(result: PatternResult) -> None:
    st.markdown("### 5) Performance Comparison")
    d = result.architect_decision
    comps = result.comparisons or {}
    if d:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Hybrid Latency", _fmt_ms(d.hybrid_latency_ms))
        c2.metric("All-Frontier Latency (ESTIMATED)", _fmt_ms(d.all_frontier_latency_ms))
        c3.metric("Hybrid Confidence", _fmt_pct(d.hybrid_confidence))
        c4.metric("All-Frontier Confidence (ESTIMATED)", _fmt_pct(d.all_frontier_confidence))
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Hybrid Cost*", d.hybrid_cost)
        c6.metric("All-Frontier Cost*", d.all_frontier_cost)
        c7.metric("Cost Avoided*", d.cost_avoided)
        c8.metric("Frontier Tokens Avoided", f"{d.frontier_tokens_avoided} ({d.frontier_tokens_avoided_pct}%)")
    # pattern-specific honest tradeoffs
    if result.pattern_id == "confidence_cascade":
        if comps.get("cascade_exceeds_direct_frontier"):
            callout(str(comps.get("callout")), "warn")
        st.markdown("#### Strategy options")
        st.dataframe(comps.get("options") or [], use_container_width=True, hide_index=True)
        st.markdown("#### Fleet economics")
        st.json(comps.get("fleet_economics") or {})
        callout(
            "Cascade value appears at fleet scale even when one escalated incident costs more than direct Frontier.",
            "info",
        )
    elif result.pattern_id == "rag":
        st.markdown("#### RAG + SLM vs RAG + Frontier")
        st.dataframe(
            [
                {"Approach": k, **v}
                for k, v in (comps.get("rag_slm_vs_rag_frontier") or {}).items()
            ],
            use_container_width=True,
            hide_index=True,
        )
        callout(str(comps.get("callout") or "Retrieval supplied enterprise knowledge; SLM is sufficient."), "good")
    elif result.pattern_id == "fallback":
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Normal Frontier (ESTIMATED)**")
            st.json(comps.get("normal_frontier") or {})
        with c2:
            st.markdown("**Frontier failure + SLM**")
            st.json(comps.get("frontier_failure_slm") or {})
        callout(str(comps.get("callout") or "Fallback preserves availability with degraded quality."), "warn")
    elif result.pattern_id == "router":
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("SLM Requests", comps.get("slm_requests"))
        c2.metric("Frontier Requests", comps.get("frontier_requests"))
        c3.metric("P50 Latency", _fmt_ms(comps.get("p50_latency_ms")))
        c4.metric("P95 Latency", _fmt_ms(comps.get("p95_latency_ms")))
        callout(
            f"Frontier avoidance rate: {comps.get('frontier_avoidance_rate')}%. "
            "Routine health checks should not consume Frontier capacity.",
            "good",
        )
    else:
        if comps.get("callout"):
            callout(str(comps["callout"]), "info")
        with st.expander("Raw comparison payload"):
            st.json(comps)


def render_langsmith_section(result: PatternResult) -> None:
    st.markdown("### 6) LangSmith Trace")
    spans = get_trace_store().by_trace(result.trace_id)
    c1, c2 = st.columns([2, 1])
    with c1:
        st.write(f"Local Trace ID: `{result.trace_id}`")
        if result.langsmith_url:
            st.link_button("Open Trace in LangSmith", result.langsmith_url)
        else:
            st.info(
                "Remote LangSmith URL unavailable in this run context. "
                "Parent/child spans are still captured locally and listed below."
            )
    with c2:
        st.metric("Spans", len(spans))
        st.metric("Trace Tokens", sum(int(s.get("total_tokens") or 0) for s in spans))

    # waterfall
    cursor = 0.0
    fig = go.Figure()
    labels = []
    for span in spans:
        if span.get("segment") == "root":
            continue
        dur = max(0.001, float(span.get("latency_ms") or 0) / 1000.0)
        label = f"{span.get('model_type')} · {span.get('segment')}"
        labels.append(label)
        fig.add_trace(
            go.Bar(
                x=[dur],
                y=[label],
                base=[cursor],
                orientation="h",
                showlegend=False,
                hovertext=f"{label}<br>{dur:.2f}s · {span.get('total_tokens')} tokens · {span.get('provenance')}",
            )
        )
        cursor += dur
    if labels:
        fig.update_layout(
            title="Execution Waterfall (seconds)",
            height=max(320, 28 * len(labels)),
            xaxis_title="Time (s)",
            **CHART_LAYOUT,
        )
        st.plotly_chart(fig, use_container_width=True)
        callout(
            "What this means: the waterfall shows where latency accumulates across SLM, Frontier, and NON-LLM steps.",
            "info",
        )

    st.dataframe(
        [
            {
                "segment": s.get("segment"),
                "model_type": s.get("model_type"),
                "model_role": s.get("model_role"),
                "tokens": s.get("total_tokens"),
                "latency_ms": s.get("latency_ms"),
                "confidence": s.get("confidence"),
                "cost*": s.get("estimated_cost"),
                "provenance": s.get("provenance"),
                "parent_run_id": s.get("parent_run_id"),
            }
            for s in spans
            if s.get("segment") != "root"
        ],
        use_container_width=True,
        hide_index=True,
    )


def render_architect_decision(result: PatternResult) -> None:
    st.markdown("### AI Architect Decision")
    d = result.architect_decision
    if not d:
        st.warning("No architect decision available.")
        return
    st.markdown(
        f"""
<div class="panel">
  <div><strong>Pattern:</strong> {d.pattern}</div>
  <div><strong>Scenario:</strong> {d.scenario}</div>
  <div style="margin-top:0.45rem;"><strong>Frontier used for:</strong> {", ".join(d.frontier_used_for) or "None"}</div>
  <div><strong>SLM used for:</strong> {", ".join(d.slm_used_for) or "None"}</div>
  <div style="margin-top:0.45rem;"><strong>Why this architecture?</strong> {d.why_this_architecture}</div>
</div>
""",
        unsafe_allow_html=True,
    )
    kpi_grid(
        [
            ("SLM Calls", d.slm_calls, "Selected architecture"),
            ("Frontier Calls", d.frontier_calls, "Selected architecture"),
            ("SLM Tokens", d.slm_tokens, d.notes[0][:40] + "..." if d.notes else ""),
            ("Frontier Tokens", d.frontier_tokens, "Premium consumption"),
            ("Total Tokens", d.total_tokens, "Hybrid total"),
            ("All-Frontier Tokens", d.all_frontier_tokens, "ESTIMATED baseline"),
            ("Frontier Tokens Avoided", f"{d.frontier_tokens_avoided} ({d.frontier_tokens_avoided_pct}%)", "Primary metric"),
            ("Hybrid Latency", _fmt_ms(d.hybrid_latency_ms), "Selected path"),
            ("All-Frontier Latency", _fmt_ms(d.all_frontier_latency_ms), "ESTIMATED"),
            ("Cost Avoided*", d.cost_avoided, "Illustrative USD"),
        ]
    )
    callout(d.recommendation, "good")
    for note in d.notes:
        st.caption(note)


def _scenario_telemetry(result: PatternResult) -> None:
    st.markdown("### 1) Scenario")
    st.write(result.scenario)
    if not result.device_id:
        st.caption("Fleet / batch scenario")
        return
    try:
        device = TelemetryService().get_device(result.device_id)
    except KeyError:
        st.caption(f"Device: {result.device_id}")
        return
    anomalies = []
    checks = [
        ("cpu_percent", 85, "CPU high"),
        ("memory_percent", 85, "Memory high"),
        ("disk_percent", 90, "Disk critical"),
        ("teams_crashes_24h", 3, "Teams crashes elevated"),
        ("vpn_disconnects_24h", 3, "VPN unstable"),
        ("onedrive_sync_errors", 5, "OneDrive sync errors"),
        ("packet_loss_percent", 2, "Packet loss present"),
        ("incident_count_30d", 3, "Recurring incidents"),
    ]
    for key, threshold, label in checks:
        val = device.get(key)
        try:
            if float(val) >= threshold:
                anomalies.append(f"{label}: {val}")
        except Exception:  # noqa: BLE001
            continue
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown(f"**Device:** `{result.device_id}`")
        st.markdown(f"**User:** {device.get('user')}")
        st.markdown(f"**DEX:** {device.get('dex_score')} · **Risk:** {device.get('risk_score')}")
    with c2:
        st.markdown("**Key telemetry anomalies**")
        st.write(anomalies or ["No threshold anomalies flagged"])
    business_q = {
        "planner_worker": "What is the cross-domain root cause and recommended remediation?",
        "confidence_cascade": "Can an SLM resolve this ambiguous incident, or must Frontier escalate?",
        "rag": "What does the approved Digital Workplace SOP recommend?",
        "fallback": "Can operations continue with degraded local reasoning during Frontier outage?",
        "router": "Which requests need Frontier reasoning vs safe SLM handling?",
    }.get(result.pattern_id, "What is the right model for each workflow segment?")
    callout(f"Business question: {business_q}", "info")


def _tail_view(result: PatternResult) -> None:
    st.markdown("### Tail View — Precise Operational Detail")
    comps = result.comparisons or {}

    # Segment table always
    st.markdown("#### Segment ledger")
    st.dataframe(
        [
            {
                "segment": s.segment,
                "model_type": s.model_type.value,
                "model_role": s.model_role.value if hasattr(s.model_role, "value") else s.model_role,
                "tokens": s.tokens,
                "input_tokens": s.input_tokens,
                "output_tokens": s.output_tokens,
                "latency_ms": s.latency_ms,
                "confidence": s.confidence,
                "cost*": s.estimated_cost,
                "provenance": s.provenance,
                "decision": s.decision,
            }
            for s in result.segments
            if not (result.pattern_id == "router" and s.segment.startswith("REQ-"))
        ],
        use_container_width=True,
        hide_index=True,
    )

    if result.pattern_id == "planner_worker":
        callout("WHY NOT FRONTIER FOR CPU ANALYSIS?", "warn")
        cpu = next((s for s in result.segments if "CPU" in s.segment), None)
        if cpu and cpu.alternative:
            st.write(cpu.decision_why)
        st.markdown("#### Worker selected vs alternative")
        st.dataframe(
            [
                {
                    "worker": s.segment,
                    "selected": s.model_type.value,
                    "selected_tokens": s.tokens,
                    "alt": s.alternative.model_type.value if s.alternative else None,
                    "alt_tokens": s.alternative.expected_tokens if s.alternative else None,
                    "alt_confidence": s.alternative.expected_confidence if s.alternative else None,
                    "decision": s.decision,
                }
                for s in result.segments
                if s.model_role.value == "worker" or "Worker" in s.segment or s.segment.endswith("Analysis")
            ],
            use_container_width=True,
            hide_index=True,
        )

    if result.pattern_id == "router":
        st.markdown("#### Request drill-down")
        per_request = (result.metadata or {}).get("per_request") or []
        preview_n = st.slider("Rows to show", min_value=5, max_value=min(100, max(5, len(per_request))), value=min(15, len(per_request) or 5))
        st.dataframe(per_request[:preview_n], use_container_width=True, hide_index=True)
        examples = comps.get("examples") or {}
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Routine example → SLM**")
            st.json(examples.get("routine") or {})
        with c2:
            st.markdown("**Complex example → Frontier**")
            st.json(examples.get("complex") or {})

    if result.pattern_id == "confidence_cascade":
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Initial Confidence", _fmt_pct(comps.get("initial_confidence")))
        c2.metric("Threshold", _fmt_pct(comps.get("threshold")))
        c3.metric("Escalated", str(comps.get("escalated")))
        c4.metric("Final Confidence", _fmt_pct(comps.get("final_confidence")))
        st.markdown("#### Escalation event details")
        st.json(
            {
                "device_id": result.device_id,
                "escalated": comps.get("escalated"),
                "cascade_tokens": comps.get("cascade_tokens"),
                "direct_frontier_tokens": comps.get("direct_frontier_tokens"),
                "cascade_exceeds_direct_frontier": comps.get("cascade_exceeds_direct_frontier"),
            }
        )

    if result.pattern_id == "rag":
        st.markdown("#### Retrieval citations")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Query Tokens", comps.get("query_tokens"))
        c2.metric("Context Tokens", comps.get("retrieved_context_tokens"))
        c3.metric("SLM Input/Output", f"{comps.get('slm_input_tokens')}/{comps.get('slm_output_tokens')}")
        c4.metric("Grounding Score", comps.get("grounding_score"))
        st.write("Retrieved documents:", comps.get("retrieved_documents"))
        st.dataframe(comps.get("retrieved_chunks") or [], use_container_width=True, hide_index=True)

    if result.pattern_id == "fallback":
        failure = (result.metadata or {}).get("failure") or {}
        st.markdown("#### Failure / recovery details")
        st.json(failure)
        ff = comps.get("frontier_failure_slm") or {}
        c1, c2, c3 = st.columns(3)
        c1.metric("Time to Failure", _fmt_ms(ff.get("time_to_failure_ms")))
        c2.metric("Recovery Time", _fmt_ms(ff.get("total_recovery_time_ms")))
        c3.metric("Degraded Confidence", _fmt_pct(ff.get("confidence")))


def render_pattern_page(result: PatternResult) -> None:
    st.markdown(
        f"""
<div class="hero-banner">
  <div class="eyebrow">Pattern Lab · Explainable Model Selection</div>
  <div class="title">{result.pattern}</div>
  <p class="subtitle">Scenario → Segments → SLM/Frontier/NON-LLM → Trace → Baseline → Decision</p>
</div>
""",
        unsafe_allow_html=True,
    )
    _scenario_telemetry(result)
    render_architecture_flow(result)
    render_why_this_model(result)

    st.markdown("### 4) Token Utilization")
    render_token_utilization(result)

    render_performance_comparison(result)
    render_langsmith_section(result)
    _tail_view(result)
    render_architect_decision(result)
