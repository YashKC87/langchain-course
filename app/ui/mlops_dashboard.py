"""AI Model Operations / LLMOps dashboard page helpers."""

from __future__ import annotations

import streamlit as st

from app.services.scenario_service import get_scenario_service
from app.ui.token_charts import render_mlops_charts


def render_mlops_page() -> None:
    st.header("AI Model Operations")
    st.caption("MLOps / LLMOps visualization of model selection decisions.")
    service = get_scenario_service()
    if st.button("Refresh by running all five patterns", key="mlops_run_all"):
        with st.spinner("Executing all patterns in Demo Mode..."):
            service.run_all()
        st.success("All patterns executed.")

    dash = service.mlops_dashboard()
    kpis = dash.get("kpis") or {}
    labels = [
        ("Total Scenarios", "total_scenarios"),
        ("Total Traces", "total_traces"),
        ("Total Model Calls", "total_model_calls"),
        ("SLM Calls", "slm_calls"),
        ("Frontier Calls", "frontier_calls"),
        ("SLM Tokens", "slm_tokens"),
        ("Frontier Tokens", "frontier_tokens"),
        ("Total Tokens", "total_tokens"),
        ("Frontier Calls Avoided", "frontier_calls_avoided"),
        ("Frontier Tokens Avoided", "frontier_tokens_avoided"),
        ("Average Latency", "average_latency_ms"),
        ("P95 Latency", "p95_latency_ms"),
        ("Average Confidence", "average_confidence"),
        ("Escalation Rate", "escalation_rate"),
        ("Fallback Rate", "fallback_rate"),
        ("Estimated Cost", "estimated_cost"),
        ("Estimated Cost Avoided", "estimated_cost_avoided"),
    ]
    for i in range(0, len(labels), 4):
        cols = st.columns(4)
        for col, (label, key) in zip(cols, labels[i : i + 4]):
            col.metric(label, kpis.get(key))
    st.caption(dash.get("pricing_disclaimer", ""))

    st.subheader("Interactive Charts")
    render_mlops_charts(dash)

    st.subheader("Pattern Efficiency Table")
    st.dataframe(dash.get("efficiency_table") or [], use_container_width=True)


def render_langsmith_page() -> None:
    st.header("LangSmith / LLMOps")
    from app.config import get_settings
    from app.observability.trace_store import get_trace_store

    settings = get_settings()
    status = settings.public_status()
    st.write(
        {
            "langsmith_enabled": status["langsmith_enabled"],
            "langsmith_active": status["langsmith_active"],
            "project": status["langsmith_project"],
            "demo_mode": status["demo_mode"],
        }
    )
    if not status["langsmith_active"]:
        st.warning(
            "LangSmith is not active. Set LANGSMITH_ENABLED=true, LANGSMITH_TRACING=true, "
            "and LANGSMITH_API_KEY in .env to send remote traces. Local parent/child spans "
            "still power this page."
        )
    store = get_trace_store()
    agg = store.aggregates()
    st.subheader("Local Trace Aggregates")
    st.json(agg)
    runs = store.list_runs(limit=100)
    st.subheader("Recent Spans")
    st.dataframe(runs, use_container_width=True)
    st.markdown(
        """
### What LangSmith shows for each pattern
- **Planner-Worker:** Frontier planner, SLM workers, Frontier synthesis
- **Router:** Router node + request children (aggregated in UI)
- **Confidence Cascade:** SLM diagnosis → evaluator → optional Frontier RCA
- **RAG:** Query/retrieval/ranking/context + SLM grounded generation
- **Fallback:** Frontier attempt → failure detector → SLM fallback
"""
    )
