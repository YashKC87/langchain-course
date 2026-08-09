"""Token and MLOps chart components."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.models.schemas import PatternResult
from app.observability.trace_store import get_trace_store
from app.ui.theme import CHART_LAYOUT, callout, kpi_grid

# Short axis / marker labels so letters do not overlap on MLOps charts.
SHORT_PATTERN_LABELS = {
    "Planner-Worker Hierarchy": "Planner-Worker",
    "Router Pattern": "Router",
    "Confidence Cascade": "Cascade",
    "Retrieval-Augmented Generation (RAG)": "RAG",
    "Designing for Fallback": "Fallback",
}

# Staggered label positions keep nearby scatter points readable.
_TEXT_POSITIONS = (
    "top center",
    "bottom center",
    "middle left",
    "middle right",
    "top right",
)


def short_pattern(name: str | None) -> str:
    raw = (name or "").strip()
    if not raw:
        return "Unknown"
    if raw in SHORT_PATTERN_LABELS:
        return SHORT_PATTERN_LABELS[raw]
    # Fallback: keep first readable chunk for any unexpected long name.
    return raw.replace("Retrieval-Augmented Generation (RAG)", "RAG")[:18]


def _bar_layout(title: str, height: int = 400, **extra: Any) -> dict[str, Any]:
    layout = dict(CHART_LAYOUT)
    layout.update(
        {
            "title": title,
            "height": height,
            "margin": dict(l=48, r=24, t=56, b=88),
            "xaxis": dict(tickangle=-20, automargin=True, title=""),
        }
    )
    layout.update(extra)
    return layout


def _scatter_with_clear_labels(
    *,
    x: list[float],
    y: list[float],
    full_names: list[str],
    title: str,
    xaxis_title: str,
    yaxis_title: str,
    color: str,
) -> go.Figure:
    labels = [short_pattern(n) for n in full_names]
    positions = [_TEXT_POSITIONS[i % len(_TEXT_POSITIONS)] for i in range(len(labels))]
    # Small deterministic offsets reduce exact overlaps when values cluster.
    x_plot = [val + (i - (len(x) - 1) / 2) * (max(x) - min(x) + 1e-6) * 0.01 for i, val in enumerate(x)]
    y_plot = [val + ((i % 3) - 1) * (max(y) - min(y) + 1e-6) * 0.02 for i, val in enumerate(y)]

    fig = go.Figure(
        data=[
            go.Scatter(
                x=x_plot,
                y=y_plot,
                mode="markers+text",
                text=labels,
                textposition=positions,
                textfont=dict(size=12),
                marker=dict(size=18, color=color, line=dict(width=1, color="rgba(255,255,255,0.35)")),
                customdata=full_names,
                hovertemplate="<b>%{customdata}</b><br>"
                + f"{xaxis_title}: %{{x:.3g}}<br>"
                + f"{yaxis_title}: %{{y:.3g}}<extra></extra>",
                cliponaxis=False,
            )
        ]
    )
    layout = dict(CHART_LAYOUT)
    layout.update(
        {
            "title": title,
            "xaxis_title": xaxis_title,
            "yaxis_title": yaxis_title,
            "height": 420,
            "margin": dict(l=56, r=40, t=56, b=56),
        }
    )
    fig.update_layout(**layout)
    # Keep room so labels are not clipped.
    if x:
        pad_x = max(0.05, (max(x) - min(x)) * 0.18 or 0.08)
        fig.update_xaxes(range=[min(x) - pad_x, max(x) + pad_x], automargin=True)
    if y:
        pad_y = max(0.05, (max(y) - min(y)) * 0.22 or 0.08)
        fig.update_yaxes(range=[min(y) - pad_y, max(y) + pad_y], automargin=True)
    return fig


def render_token_utilization(result: PatternResult) -> None:
    comps = result.comparisons or {}
    hybrid = comps.get("selected_hybrid") or {}
    all_f = comps.get("estimated_all_frontier") or {}
    slm = int(hybrid.get("slm_tokens") or 0)
    frontier = int(hybrid.get("frontier_tokens") or 0)
    all_frontier = int(all_f.get("frontier_tokens") or 0)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Selected Hybrid — SLM",
            x=["Selected Hybrid"],
            y=[slm],
            marker_color="#10b981",
            text=[f"SLM {slm:,}"],
            textposition="auto",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Selected Hybrid — Frontier",
            x=["Selected Hybrid"],
            y=[frontier],
            marker_color="#3b82f6",
            text=[f"Frontier {frontier:,}"],
            textposition="auto",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Estimated All-Frontier Baseline",
            x=["All-Frontier (ESTIMATED)"],
            y=[all_frontier],
            marker_color="#f59e0b",
            text=[f"ESTIMATED {all_frontier:,}"],
            textposition="auto",
        )
    )
    fig.update_layout(
        barmode="stack",
        title="Token Utilization — Frontier avoidance is the primary metric",
        yaxis_title="Tokens",
        height=420,
        **CHART_LAYOUT,
    )
    st.plotly_chart(fig, use_container_width=True)

    kpi_grid(
        [
            ("Frontier Tokens Avoided", comps.get("frontier_tokens_avoided", 0), "Primary metric"),
            ("Avoidance %", f"{comps.get('frontier_tokens_avoided_pct', 0)}%", "vs All-Frontier"),
            ("Latency Improvement", f"{comps.get('latency_improvement_pct', 0)}%", "Hybrid vs baseline"),
            ("Quality Difference", comps.get("quality_difference", 0), "Hybrid − All-Frontier"),
            (
                "Cost Avoided*",
                comps.get(
                    "cost_avoided",
                    result.architect_decision.cost_avoided if result.architect_decision else 0,
                ),
                "Illustrative USD",
            ),
        ]
    )
    callout(
        "What this means: the useful efficiency signal is Frontier token consumption avoided, "
        "not merely a lower total token count.",
        "info",
    )


def render_mlops_charts(dashboard: dict[str, Any]) -> None:
    by_pattern = dashboard.get("by_pattern") or {}
    efficiency = dashboard.get("efficiency_table") or []
    rows = get_trace_store().list_runs(limit=5000)

    if not by_pattern and not efficiency and not rows:
        st.info("Run scenarios to populate MLOps charts.")
        return

    patterns = list(by_pattern.keys()) or [e["pattern"] for e in efficiency]
    pattern_labels = [short_pattern(p) for p in patterns]
    st.caption(
        "Chart labels use short pattern names (Planner-Worker · Router · Cascade · RAG · Fallback) "
        "so letters stay readable. Hover a point for the full name."
    )

    # 1 Token consumption by pattern
    if by_pattern:
        fig1 = go.Figure(
            data=[
                go.Bar(
                    name="SLM",
                    x=pattern_labels,
                    y=[by_pattern[p]["slm_tokens"] for p in patterns],
                    marker_color="#10b981",
                    customdata=patterns,
                    hovertemplate="<b>%{customdata}</b><br>SLM tokens: %{y}<extra></extra>",
                ),
                go.Bar(
                    name="Frontier",
                    x=pattern_labels,
                    y=[by_pattern[p]["frontier_tokens"] for p in patterns],
                    marker_color="#3b82f6",
                    customdata=patterns,
                    hovertemplate="<b>%{customdata}</b><br>Frontier tokens: %{y}<extra></extra>",
                ),
            ]
        )
        fig1.update_layout(barmode="group", **_bar_layout("1. Token Consumption by Pattern"))
        st.plotly_chart(fig1, use_container_width=True)
        callout(
            "What this means: each pattern should show Frontier concentrated only where reasoning is required.",
            "info",
        )

    if efficiency:
        eff_labels = [short_pattern(e["pattern"]) for e in efficiency]
        eff_full = [e["pattern"] for e in efficiency]

        # 2 Selected vs All-Frontier
        fig2 = go.Figure(
            data=[
                go.Bar(
                    name="Selected Architecture",
                    x=eff_labels,
                    y=[e["total_tokens"] for e in efficiency],
                    marker_color="#22d3ee",
                    customdata=eff_full,
                    hovertemplate="<b>%{customdata}</b><br>Selected tokens: %{y}<extra></extra>",
                ),
                go.Bar(
                    name="Estimated All-Frontier",
                    x=eff_labels,
                    y=[e["all_frontier_baseline"] for e in efficiency],
                    marker_color="#f59e0b",
                    customdata=eff_full,
                    hovertemplate="<b>%{customdata}</b><br>All-Frontier tokens: %{y}<extra></extra>",
                ),
            ]
        )
        fig2.update_layout(barmode="group", **_bar_layout("2. Selected vs All-Frontier (ESTIMATED)"))
        st.plotly_chart(fig2, use_container_width=True)

        # 3 Model usage mix
        slm_calls = sum(e.get("slm_calls", 0) for e in efficiency)
        frontier_calls = sum(e.get("frontier_calls", 0) for e in efficiency)
        fig3 = go.Figure(
            data=[
                go.Pie(
                    labels=["SLM", "Frontier"],
                    values=[slm_calls, frontier_calls],
                    hole=0.55,
                    marker_colors=["#10b981", "#3b82f6"],
                    textinfo="label+percent",
                    textposition="outside",
                    insidetextorientation="horizontal",
                )
            ]
        )
        layout3 = dict(CHART_LAYOUT)
        layout3.update(
            {
                "title": "3. Model Usage Mix (Calls)",
                "height": 380,
                "margin": dict(l=40, r=40, t=56, b=40),
            }
        )
        fig3.update_layout(**layout3)
        st.plotly_chart(fig3, use_container_width=True)

    # 4 Token trend over time
    if rows:
        trend = defaultdict(lambda: {"SLM": 0, "FRONTIER": 0})
        for r in rows:
            ts = str(r.get("timestamp") or "")[:16]
            mt = r.get("model_type") or "NON_LLM"
            if mt in {"SLM", "FRONTIER"}:
                trend[ts][mt] += int(r.get("total_tokens") or 0)
        xs = sorted(trend)
        fig4 = go.Figure()
        fig4.add_trace(go.Scatter(x=xs, y=[trend[x]["SLM"] for x in xs], name="SLM", line=dict(color="#10b981")))
        fig4.add_trace(
            go.Scatter(x=xs, y=[trend[x]["FRONTIER"] for x in xs], name="Frontier", line=dict(color="#3b82f6"))
        )
        layout4 = dict(CHART_LAYOUT)
        layout4.update(
            {
                "title": "4. Token Trend Over Time",
                "height": 360,
                "margin": dict(l=48, r=24, t=56, b=72),
                "xaxis": dict(tickangle=-25, automargin=True),
            }
        )
        fig4.update_layout(**layout4)
        st.plotly_chart(fig4, use_container_width=True)

        # 5 Latency by model
        lat_model = {"SLM": [], "FRONTIER": [], "NON_LLM": []}
        for r in rows:
            mt = r.get("model_type") or "NON_LLM"
            if mt in lat_model:
                lat_model[mt].append(float(r.get("latency_ms") or 0))
        fig5 = go.Figure()
        for name, vals in lat_model.items():
            if vals:
                fig5.add_trace(go.Box(y=vals, name=name))
        fig5.update_layout(title="5. Latency by Model Type (ms)", height=360, **CHART_LAYOUT)
        st.plotly_chart(fig5, use_container_width=True)

        # 6 Latency by pattern
        fig6 = px.box(
            [
                {
                    "pattern": short_pattern(r.get("pattern")),
                    "full_pattern": r.get("pattern"),
                    "latency_ms": float(r.get("latency_ms") or 0),
                }
                for r in rows
                if r.get("pattern")
            ],
            x="pattern",
            y="latency_ms",
            title="6. Latency by Pattern",
            hover_data=["full_pattern"],
        )
        fig6.update_layout(**_bar_layout("6. Latency by Pattern", height=400))
        st.plotly_chart(fig6, use_container_width=True)

    if efficiency:
        eff_labels = [short_pattern(e["pattern"]) for e in efficiency]
        eff_full = [e["pattern"] for e in efficiency]

        # 7 Cost by pattern
        fig7 = go.Figure(
            data=[
                go.Bar(
                    x=eff_labels,
                    y=[e["estimated_cost"] for e in efficiency],
                    marker_color="#a78bfa",
                    name="Estimated Cost",
                    customdata=eff_full,
                    hovertemplate="<b>%{customdata}</b><br>Cost*: %{y}<extra></extra>",
                )
            ]
        )
        fig7.update_layout(**_bar_layout("7. Cost by Pattern (Illustrative)"))
        st.plotly_chart(fig7, use_container_width=True)
        st.caption("Illustrative pricing — configure using current provider pricing.")

        # 8 Confidence vs escalation
        fig8 = _scatter_with_clear_labels(
            x=[float(e["confidence"] or 0) for e in efficiency],
            y=[float(e.get("frontier_calls", 0) or 0) for e in efficiency],
            full_names=eff_full,
            title="8. Confidence vs Frontier Calls",
            xaxis_title="Confidence",
            yaxis_title="Frontier Calls",
            color="#22d3ee",
        )
        st.plotly_chart(fig8, use_container_width=True)

        # 9 Frontier avoidance rate
        avoid_rates = []
        for e in efficiency:
            baseline = max(1, int(e.get("all_frontier_baseline") or 1))
            avoided = int(e.get("frontier_tokens_avoided") or 0)
            avoid_rates.append(round(100.0 * avoided / baseline, 1))
        fig9 = go.Figure(
            data=[
                go.Bar(
                    x=eff_labels,
                    y=avoid_rates,
                    marker_color="#34d399",
                    text=[f"{v}%" for v in avoid_rates],
                    textposition="outside",
                    cliponaxis=False,
                    customdata=eff_full,
                    hovertemplate="<b>%{customdata}</b><br>Avoidance: %{y}%<extra></extra>",
                )
            ]
        )
        fig9.update_layout(**_bar_layout("9. Frontier Avoidance Rate (%)"))
        st.plotly_chart(fig9, use_container_width=True)

        # 10 Tokens vs latency
        fig10 = _scatter_with_clear_labels(
            x=[float(e["actual_latency_ms"] or 0) for e in efficiency],
            y=[float(e["total_tokens"] or 0) for e in efficiency],
            full_names=eff_full,
            title="10. Tokens vs Latency",
            xaxis_title="Latency (ms)",
            yaxis_title="Tokens",
            color="#60a5fa",
        )
        st.plotly_chart(fig10, use_container_width=True)

        # 11 Cost vs quality
        fig11 = _scatter_with_clear_labels(
            x=[float(e["estimated_cost"] or 0) for e in efficiency],
            y=[float(e["confidence"] or 0) for e in efficiency],
            full_names=eff_full,
            title="11. Cost vs Quality (Confidence)",
            xaxis_title="Estimated Cost*",
            yaxis_title="Confidence",
            color="#fbbf24",
        )
        st.plotly_chart(fig11, use_container_width=True)
        callout(
            "What this means: the best architecture is not always the cheapest — "
            "it is the one that meets quality at acceptable Frontier spend.",
            "info",
        )

        # 12 Pattern usage
        fig12 = go.Figure(
            data=[
                go.Bar(
                    x=eff_labels,
                    y=[e.get("slm_calls", 0) + e.get("frontier_calls", 0) for e in efficiency],
                    marker_color="#38bdf8",
                    customdata=eff_full,
                    hovertemplate="<b>%{customdata}</b><br>Model calls: %{y}<extra></extra>",
                )
            ]
        )
        fig12.update_layout(**_bar_layout("12. Pattern Usage (Model Calls)"))
        st.plotly_chart(fig12, use_container_width=True)

    # Optional radar for confidence/avoidance profile
    if efficiency:
        fig_r = go.Figure()
        for e in efficiency:
            baseline = max(1, int(e.get("all_frontier_baseline") or 1))
            avoided_pct = 100.0 * int(e.get("frontier_tokens_avoided") or 0) / baseline
            fig_r.add_trace(
                go.Scatterpolar(
                    r=[
                        float(e.get("confidence") or 0) * 100,
                        min(100, avoided_pct),
                        min(100, 1000 / max(1.0, float(e.get("actual_latency_ms") or 1)) * 10),
                        min(100, 1 / max(1e-6, float(e.get("estimated_cost") or 1e-6))),
                    ],
                    theta=["Confidence", "Frontier Avoidance", "Latency Efficiency", "Cost Efficiency"],
                    fill="toself",
                    name=short_pattern(e["pattern"]),
                    hovertemplate="<b>" + e["pattern"] + "</b><br>%{theta}: %{r:.1f}<extra></extra>",
                )
            )
        layout_r = dict(CHART_LAYOUT)
        layout_r.update(
            {
                "title": "Pattern Quality / Efficiency Radar",
                "polar": dict(bgcolor="rgba(15,23,42,0.2)"),
                "height": 440,
                "legend": dict(orientation="h", yanchor="bottom", y=-0.22, x=0),
                "margin": dict(l=48, r=48, t=56, b=80),
            }
        )
        fig_r.update_layout(**layout_r)
        st.plotly_chart(fig_r, use_container_width=True)
