"""Reusable architecture visualization helpers for Streamlit."""

from __future__ import annotations

from typing import Any

import streamlit as st

from app.models.schemas import PatternResult, SegmentResult


def render_kpi_row(cards: dict[str, Any]) -> None:
    cols = st.columns(5)
    items = [
        ("Endpoints", cards.get("endpoints")),
        ("Healthy", cards.get("healthy")),
        ("At Risk", cards.get("at_risk")),
        ("Critical", cards.get("critical")),
        ("Cost Avoided*", cards.get("estimated_cost_avoided")),
    ]
    for col, (label, value) in zip(cols, items):
        col.metric(label, value)
    cols2 = st.columns(5)
    items2 = [
        ("SLM Calls", cards.get("slm_calls")),
        ("Frontier Calls", cards.get("frontier_calls")),
        ("SLM Tokens", cards.get("slm_tokens")),
        ("Frontier Tokens", cards.get("frontier_tokens")),
        ("Frontier Calls Avoided", cards.get("frontier_calls_avoided")),
    ]
    for col, (label, value) in zip(cols2, items2):
        col.metric(label, value)
    st.caption(cards.get("pricing_disclaimer", "Illustrative pricing."))


def render_node(segment: SegmentResult) -> None:
    alt = segment.alternative
    st.markdown(
        f"""
<div style="border:1px solid #8a8a8a;padding:0.8rem;margin-bottom:0.6rem;">
  <div><strong>{segment.model_type.value}</strong> · {segment.segment}</div>
  <div>Task: {segment.task}</div>
  <div>Model: {segment.model_name}</div>
  <div>Tokens: {segment.tokens} ({segment.provenance})</div>
  <div>Latency: {segment.latency_ms} ms</div>
  <div>Confidence: {segment.confidence:.0%}</div>
  <div>Why: {segment.why}</div>
</div>
""",
        unsafe_allow_html=True,
    )
    if alt:
        with st.expander(f"What if {alt.model_type.value}?"):
            st.write(
                {
                    "expected_tokens": alt.expected_tokens,
                    "expected_latency_ms": alt.expected_latency_ms,
                    "expected_confidence": alt.expected_confidence,
                    "expected_cost": alt.expected_cost,
                    "provenance": alt.provenance,
                    "recommendation": alt.recommendation,
                    "rationale": alt.rationale,
                }
            )


def render_architecture_flow(result: PatternResult) -> None:
    st.subheader("Architecture Flow")
    st.caption("Every node explicitly labels SLM, FRONTIER, or NON-LLM.")
    for segment in result.segments:
        # Aggregate router children in UI
        if result.pattern_id == "router" and segment.segment.startswith("REQ-"):
            continue
        render_node(segment)
    if result.pattern_id == "router":
        st.info(
            "Router request children are aggregated below. Use Trace Explorer for drill-down."
        )


def render_why_this_model(result: PatternResult) -> None:
    st.subheader("Why This Model?")
    rows = []
    for segment in result.segments:
        if result.pattern_id == "router" and segment.segment.startswith("REQ-"):
            continue
        rows.append(
            {
                "Segment": segment.segment,
                "Selected": segment.model_type.value,
                "Why": segment.why,
                "Decision": segment.decision,
                "Decision Why": segment.decision_why,
            }
        )
    st.dataframe(rows, use_container_width=True)


def render_architect_decision(result: PatternResult) -> None:
    st.subheader("AI Architect Decision")
    d = result.architect_decision
    if not d:
        st.warning("No architect decision available.")
        return
    st.markdown(f"**Pattern:** {d.pattern}")
    st.markdown(f"**Scenario:** {d.scenario}")
    st.markdown(f"**Frontier used for:** {', '.join(d.frontier_used_for) or 'None'}")
    st.markdown(f"**SLM used for:** {', '.join(d.slm_used_for) or 'None'}")
    st.markdown(f"**Why this architecture?** {d.why_this_architecture}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("SLM Calls", d.slm_calls)
    c2.metric("Frontier Calls", d.frontier_calls)
    c3.metric("SLM Tokens", d.slm_tokens)
    c4.metric("Frontier Tokens", d.frontier_tokens)
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Total Tokens", d.total_tokens)
    c6.metric("All-Frontier (ESTIMATED)", d.all_frontier_tokens)
    c7.metric("Frontier Tokens Avoided", f"{d.frontier_tokens_avoided} ({d.frontier_tokens_avoided_pct}%)")
    c8.metric("Cost Avoided*", d.cost_avoided)
    st.markdown(
        f"**Latency:** Hybrid {d.hybrid_latency_ms} ms vs Estimated All-Frontier "
        f"{d.all_frontier_latency_ms} ms"
    )
    st.markdown(
        f"**Quality:** Hybrid {d.hybrid_confidence:.0%} vs All-Frontier "
        f"{d.all_frontier_confidence:.0%}"
    )
    st.success(d.recommendation)
    for note in d.notes:
        st.caption(note)


def render_pattern_page(result: PatternResult) -> None:
    st.header(result.pattern)
    st.subheader("Scenario")
    st.write(result.scenario)
    if result.device_id:
        st.caption(f"Device: {result.device_id}")

    render_architecture_flow(result)
    render_why_this_model(result)

    st.subheader("Token Utilization")
    from app.ui.token_charts import render_token_utilization

    render_token_utilization(result)

    st.subheader("Performance Comparison")
    st.json(result.comparisons)

    st.subheader("LangSmith Trace")
    st.write(f"Local Trace ID: `{result.trace_id}`")
    if result.langsmith_url:
        st.link_button("Open Trace in LangSmith", result.langsmith_url)
    else:
        st.info(
            "LangSmith remote URL unavailable (disabled, missing key, or local-only mode). "
            "Full parent/child spans are stored locally for the LLMOps views."
        )
    st.dataframe(
        [
            {
                "segment": s.segment,
                "model_type": s.model_type.value,
                "tokens": s.tokens,
                "latency_ms": s.latency_ms,
                "confidence": s.confidence,
                "provenance": s.provenance,
            }
            for s in result.segments
            if not (result.pattern_id == "router" and s.segment.startswith("REQ-"))
        ],
        use_container_width=True,
    )
    render_architect_decision(result)
