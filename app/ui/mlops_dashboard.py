"""AI Model Operations / LangSmith LLMOps pages."""

from __future__ import annotations

import streamlit as st

from app.config import get_settings
from app.observability.trace_store import get_trace_store
from app.services.scenario_service import get_scenario_service
from app.ui.theme import callout, inject_theme, kpi_grid, page_header, status_strip
from app.ui.token_charts import render_mlops_charts


def render_mlops_page() -> None:
    inject_theme()
    page_header("AI Model Operations", "MLOps control tower · right-model evidence")
    service = get_scenario_service()
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("Refresh by running all five patterns", use_container_width=True):
            with st.spinner("Executing all patterns..."):
                service.run_all()
            st.success("All patterns executed.")
    with c2:
        st.caption("Live runs can take minutes. Prefer loading saved pattern results first for demos.")

    dash = service.mlops_dashboard()
    kpis = dash.get("kpis") or {}
    status_strip(
        [
            ("Scenarios", str(kpis.get("total_scenarios", 0))),
            ("Traces", str(kpis.get("total_traces", 0))),
            ("Model Calls", str(kpis.get("total_model_calls", 0))),
            ("Escalation Rate", str(kpis.get("escalation_rate", 0))),
            ("Fallback Rate", str(kpis.get("fallback_rate", 0))),
        ]
    )
    kpi_grid(
        [
            ("Total Scenarios", kpis.get("total_scenarios", 0), "Completed pattern runs"),
            ("Total Traces", kpis.get("total_traces", 0), "Parent executions"),
            ("Total Model Calls", kpis.get("total_model_calls", 0), "All spans"),
            ("SLM Calls", kpis.get("slm_calls", 0), "Routine capacity"),
            ("Frontier Calls", kpis.get("frontier_calls", 0), "Reasoning capacity"),
            ("SLM Tokens", kpis.get("slm_tokens", 0), "High-volume path"),
            ("Frontier Tokens", kpis.get("frontier_tokens", 0), "Premium path"),
            ("Total Tokens", kpis.get("total_tokens", 0), "All model tokens"),
            ("Frontier Calls Avoided", kpis.get("frontier_calls_avoided", 0), "Primary efficiency"),
            ("Frontier Tokens Avoided", kpis.get("frontier_tokens_avoided", 0), "Primary metric"),
            ("Average Latency", f"{kpis.get('average_latency_ms', 0)} ms", "Mean span latency"),
            ("P95 Latency", f"{kpis.get('p95_latency_ms', 0)} ms", "Tail latency"),
            ("Average Confidence", kpis.get("average_confidence", 0), "Quality signal"),
            ("Escalation Rate", kpis.get("escalation_rate", 0), "Cascade pressure"),
            ("Fallback Rate", kpis.get("fallback_rate", 0), "Resiliency events"),
            ("Estimated Cost*", kpis.get("estimated_cost", 0), "Illustrative USD"),
            ("Estimated Cost Avoided*", kpis.get("estimated_cost_avoided", 0), "Illustrative USD"),
        ]
    )
    st.caption(dash.get("pricing_disclaimer", "Illustrative pricing — configure using current provider pricing."))

    st.markdown("### Interactive Charts")
    render_mlops_charts(dash)

    st.markdown("### Pattern Efficiency Table")
    st.dataframe(dash.get("efficiency_table") or [], use_container_width=True, hide_index=True)
    callout(
        "Primary benefits: Planner-Worker = selective reasoning; Router = high-volume efficiency; "
        "Cascade = quality-aware escalation; RAG = grounded smaller-model answers; Fallback = availability.",
        "info",
    )


def render_langsmith_page() -> None:
    inject_theme()
    page_header("LangSmith / LLMOps", "Which model · segment · tokens · latency · confidence")
    settings = get_settings()
    status = settings.public_status()
    status_strip(
        [
            ("LangSmith Enabled", str(status["langsmith_enabled"])),
            ("LangSmith Active", str(status["langsmith_active"])),
            ("Project", status["langsmith_project"]),
            ("Mode", "DEMO" if status["demo_mode"] else "LIVE"),
            ("Secrets Hidden", "yes"),
        ]
    )
    if not status["langsmith_active"]:
        st.warning(
            "LangSmith is not active. Set LANGSMITH_ENABLED=true, LANGSMITH_TRACING=true, "
            "and LANGSMITH_API_KEY to send remote traces. Local spans still power this page."
        )
    else:
        callout(
            "LangSmith is active. Local spans are always shown; remote project links appear when run IDs are available.",
            "good",
        )

    store = get_trace_store()
    agg = store.aggregates()
    kpi_grid(
        [
            ("Total Traces", agg.get("total_traces", 0), "Parents"),
            ("Model Calls", agg.get("total_model_calls", 0), "Spans"),
            ("SLM Tokens", agg.get("slm_tokens", 0), "ACTUAL/SIMULATED mix"),
            ("Frontier Tokens", agg.get("frontier_tokens", 0), "ACTUAL/SIMULATED mix"),
            ("Est. Cost*", agg.get("estimated_cost", 0), "Illustrative"),
        ]
    )
    st.markdown("### Recent Spans")
    runs = store.list_runs(limit=150)
    st.dataframe(
        [
            {
                "trace_id": r.get("trace_id"),
                "segment": r.get("segment"),
                "pattern": r.get("pattern"),
                "model_type": r.get("model_type"),
                "model_role": r.get("model_role"),
                "tokens": r.get("total_tokens"),
                "latency_ms": r.get("latency_ms"),
                "confidence": r.get("confidence"),
                "provenance": r.get("provenance"),
                "escalated": (r.get("metadata") or {}).get("escalated"),
                "fallback": (r.get("metadata") or {}).get("fallback"),
            }
            for r in reversed(runs)
        ],
        use_container_width=True,
        hide_index=True,
    )
    st.markdown(
        """
#### What LangSmith shows for each pattern
- **Planner-Worker:** Frontier planner, SLM workers, Frontier synthesis
- **Router:** Router node + request children (aggregated in UI)
- **Confidence Cascade:** SLM diagnosis → evaluator → optional Frontier RCA
- **RAG:** Query/retrieval/ranking/context + SLM grounded generation
- **Fallback:** Frontier attempt → failure detector → SLM fallback
"""
    )
