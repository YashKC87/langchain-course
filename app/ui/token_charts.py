"""Token and comparison charts."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from app.models.schemas import PatternResult


def render_token_utilization(result: PatternResult) -> None:
    comps = result.comparisons or {}
    hybrid = comps.get("selected_hybrid") or {}
    all_f = comps.get("estimated_all_frontier") or {}
    slm = hybrid.get("slm_tokens", 0)
    frontier = hybrid.get("frontier_tokens", 0)
    all_frontier = all_f.get("frontier_tokens", 0)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Selected Hybrid — SLM",
            x=["Selected Hybrid Architecture"],
            y=[slm],
            text=[f"SLM {slm}"],
            textposition="auto",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Selected Hybrid — Frontier",
            x=["Selected Hybrid Architecture"],
            y=[frontier],
            text=[f"Frontier {frontier}"],
            textposition="auto",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Estimated All-Frontier",
            x=["Estimated All-Frontier Baseline"],
            y=[all_frontier],
            text=[f"Frontier {all_frontier} (ESTIMATED)"],
            textposition="auto",
        )
    )
    fig.update_layout(
        barmode="stack",
        title="Token Utilization (Frontier avoidance is the primary metric)",
        yaxis_title="Tokens",
        height=420,
    )
    st.plotly_chart(fig, use_container_width=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Frontier Tokens Avoided", comps.get("frontier_tokens_avoided"))
    c2.metric("Token Reduction %", comps.get("frontier_tokens_avoided_pct"))
    c3.metric("Latency Improvement %", comps.get("latency_improvement_pct"))
    c4.metric("Quality Difference", comps.get("quality_difference"))
    st.caption(
        "Do not treat lower total tokens as automatically better. Evaluate tokens, cost, "
        "latency, confidence, grounding, escalation, and availability together."
    )


def render_mlops_charts(dashboard: dict) -> None:
    by_pattern = dashboard.get("by_pattern") or {}
    if not by_pattern:
        st.info("Run scenarios to populate MLOps charts.")
        return
    patterns = list(by_pattern.keys())
    slm_tokens = [by_pattern[p]["slm_tokens"] for p in patterns]
    frontier_tokens = [by_pattern[p]["frontier_tokens"] for p in patterns]

    fig1 = go.Figure(
        data=[
            go.Bar(name="SLM", x=patterns, y=slm_tokens),
            go.Bar(name="Frontier", x=patterns, y=frontier_tokens),
        ]
    )
    fig1.update_layout(barmode="group", title="1. Token Consumption by Pattern", height=400)
    st.plotly_chart(fig1, use_container_width=True)

    efficiency = dashboard.get("efficiency_table") or []
    if efficiency:
        fig2 = go.Figure(
            data=[
                go.Bar(
                    name="Selected Architecture",
                    x=[e["pattern"] for e in efficiency],
                    y=[e["total_tokens"] for e in efficiency],
                ),
                go.Bar(
                    name="Estimated All-Frontier",
                    x=[e["pattern"] for e in efficiency],
                    y=[e["all_frontier_baseline"] for e in efficiency],
                ),
            ]
        )
        fig2.update_layout(barmode="group", title="2. Selected vs All-Frontier", height=400)
        st.plotly_chart(fig2, use_container_width=True)

        fig3 = go.Figure(
            data=[
                go.Scatter(
                    x=[e["actual_latency_ms"] for e in efficiency],
                    y=[e["total_tokens"] for e in efficiency],
                    mode="markers+text",
                    text=[e["pattern"] for e in efficiency],
                    textposition="top center",
                )
            ]
        )
        fig3.update_layout(
            title="10. Tokens vs Latency",
            xaxis_title="Latency (ms)",
            yaxis_title="Tokens",
            height=400,
        )
        st.plotly_chart(fig3, use_container_width=True)

        fig4 = go.Figure(
            data=[
                go.Bar(
                    name="Estimated Cost",
                    x=[e["pattern"] for e in efficiency],
                    y=[e["estimated_cost"] for e in efficiency],
                )
            ]
        )
        fig4.update_layout(title="7. Cost by Pattern (Illustrative)", height=400)
        st.plotly_chart(fig4, use_container_width=True)

        fig5 = go.Figure(
            data=[
                go.Bar(
                    name="Frontier Tokens Avoided",
                    x=[e["pattern"] for e in efficiency],
                    y=[e["frontier_tokens_avoided"] for e in efficiency],
                )
            ]
        )
        fig5.update_layout(title="9. Frontier Avoidance", height=400)
        st.plotly_chart(fig5, use_container_width=True)
