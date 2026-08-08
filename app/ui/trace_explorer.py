"""Simplified distributed tracing waterfall."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import plotly.figure_factory as ff
import streamlit as st

from app.observability.trace_store import get_trace_store


def render_trace_explorer() -> None:
    st.header("Trace Explorer")
    store = get_trace_store()

    c1, c2, c3 = st.columns(3)
    pattern = c1.text_input("Filter pattern contains", "")
    model_type = c2.selectbox("Model Type", ["", "SLM", "FRONTIER", "NON_LLM"])
    device_id = c3.text_input("Device ID", "")
    c4, c5 = st.columns(2)
    escalated = c4.selectbox("Escalated", ["any", "yes", "no"])
    fallback = c5.selectbox("Fallback", ["any", "yes", "no"])

    rows = store.list_runs(
        pattern=None,
        model_type=model_type or None,
        device_id=device_id or None,
        escalated=None if escalated == "any" else escalated == "yes",
        fallback=None if fallback == "any" else fallback == "yes",
        limit=2000,
    )
    if pattern:
        rows = [r for r in rows if pattern.lower() in str(r.get("pattern", "")).lower()]

    if not rows:
        st.info("No traces yet. Run a pattern scenario first.")
        return

    by_trace: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_trace[row["trace_id"]].append(row)

    trace_ids = list(by_trace.keys())[::-1]
    selected = st.selectbox("Trace", trace_ids)
    spans = by_trace[selected]
    total_tokens = sum(int(s.get("total_tokens") or 0) for s in spans)
    total_latency = sum(float(s.get("latency_ms") or 0) for s in spans)
    st.write(
        {
            "trace_id": selected,
            "spans": len(spans),
            "total_tokens": total_tokens,
            "total_latency_ms": round(total_latency, 1),
            "pattern": spans[0].get("pattern"),
            "scenario": spans[0].get("scenario"),
        }
    )

    # Waterfall using cumulative offsets
    df = []
    cursor = 0.0
    for span in spans:
        if span.get("segment") == "root":
            continue
        # For router, aggregate unless expanded
        start = cursor
        dur = max(0.001, float(span.get("latency_ms") or 0) / 1000.0)
        df.append(
            dict(
                Task=f"{span.get('model_type')} · {span.get('segment')}",
                Start=start,
                Finish=start + dur,
            )
        )
        # parallel workers: keep same cursor for sequential demo simplicity
        cursor += dur

    if df:
        # Convert to figure factory gantt-like by fabricating dates is awkward;
        # use bar chart waterfall instead for robustness.
        import plotly.graph_objects as go

        fig = go.Figure()
        for item in df:
            fig.add_trace(
                go.Bar(
                    x=[item["Finish"] - item["Start"]],
                    y=[item["Task"]],
                    base=[item["Start"]],
                    orientation="h",
                    name=item["Task"],
                    showlegend=False,
                    hovertext=(
                        f"{item['Task']}<br>{item['Start']:.2f}s → {item['Finish']:.2f}s"
                    ),
                )
            )
        fig.update_layout(
            title="Execution Waterfall (seconds)",
            barmode="stack",
            height=max(360, 28 * len(df)),
            xaxis_title="Time (s)",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(spans, use_container_width=True)
    _ = ff  # imported for future fancy gantt; bar chart used for reliability
