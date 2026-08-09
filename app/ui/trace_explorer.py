"""Trace explorer with filters, waterfall, and span detail."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import plotly.graph_objects as go
import streamlit as st

from app.observability.trace_store import get_trace_store
from app.ui.theme import CHART_LAYOUT, callout, inject_theme, kpi_grid, page_header, provenance_badge


def render_trace_explorer() -> None:
    inject_theme()
    page_header("Trace Explorer", "Filter · waterfall · span detail")
    store = get_trace_store()

    c1, c2, c3, c4 = st.columns(4)
    pattern = c1.text_input("Pattern contains", "")
    model_type = c2.selectbox("Model Type", ["", "SLM", "FRONTIER", "NON_LLM"])
    device_id = c3.text_input("Device ID", "")
    segment_q = c4.text_input("Segment contains", "")
    c5, c6 = st.columns(2)
    escalated = c5.selectbox("Escalated", ["any", "yes", "no"])
    fallback = c6.selectbox("Fallback", ["any", "yes", "no"])

    rows = store.list_runs(
        pattern=None,
        model_type=model_type or None,
        device_id=device_id or None,
        escalated=None if escalated == "any" else escalated == "yes",
        fallback=None if fallback == "any" else fallback == "yes",
        limit=3000,
    )
    if pattern:
        rows = [r for r in rows if pattern.lower() in str(r.get("pattern", "")).lower()]
    if segment_q:
        rows = [r for r in rows if segment_q.lower() in str(r.get("segment", "")).lower()]

    if not rows:
        st.info("No traces yet. Execute a pattern scenario first.")
        return

    by_trace: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_trace[row["trace_id"]].append(row)
    trace_ids = list(by_trace.keys())[::-1]
    selected = st.selectbox("Trace", trace_ids)
    spans = by_trace[selected]
    total_tokens = sum(int(s.get("total_tokens") or 0) for s in spans)
    total_latency = sum(float(s.get("latency_ms") or 0) for s in spans)
    kpi_grid(
        [
            ("Trace", selected[:10] + "…", spans[0].get("pattern")),
            ("Spans", len(spans), "Including root/helpers"),
            ("Total Tokens", total_tokens, "Sum of child spans"),
            ("Total Latency", f"{total_latency:.0f} ms", "Sequential sum view"),
            ("Scenario", (spans[0].get("scenario") or "")[:28], spans[0].get("device_id") or "fleet"),
        ]
    )

    fig = go.Figure()
    cursor = 0.0
    detail_rows = []
    for span in spans:
        if span.get("segment") == "root":
            continue
        start = cursor
        dur = max(0.001, float(span.get("latency_ms") or 0) / 1000.0)
        label = f"{span.get('model_type')} · {span.get('segment')}"
        fig.add_trace(
            go.Bar(
                x=[dur],
                y=[label],
                base=[start],
                orientation="h",
                showlegend=False,
                hovertext=(
                    f"{label}<br>{start:.2f}s → {start+dur:.2f}s<br>"
                    f"tokens={span.get('total_tokens')} · conf={span.get('confidence')} · {span.get('provenance')}"
                ),
            )
        )
        detail_rows.append(span)
        cursor += dur
    if detail_rows:
        fig.update_layout(
            title="Execution Waterfall (seconds)",
            barmode="stack",
            height=max(360, 28 * len(detail_rows)),
            xaxis_title="Time (s)",
            **CHART_LAYOUT,
        )
        st.plotly_chart(fig, use_container_width=True)
        callout(
            "What this means: long SLM worker bars are usually acceptable; long Frontier bars should map to planning/synthesis value.",
            "info",
        )

    st.markdown("### Span table")
    st.dataframe(
        [
            {
                "segment": s.get("segment"),
                "parent_run_id": s.get("parent_run_id"),
                "model_type": s.get("model_type"),
                "model_role": s.get("model_role"),
                "model_name": s.get("model_name"),
                "tokens": s.get("total_tokens"),
                "latency_ms": s.get("latency_ms"),
                "confidence": s.get("confidence"),
                "cost*": s.get("estimated_cost"),
                "provenance": s.get("provenance"),
                "device_id": s.get("device_id"),
            }
            for s in detail_rows
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### Span detail drawer")
    if detail_rows:
        labels = [f"{s.get('model_type')} · {s.get('segment')}" for s in detail_rows]
        chosen = st.selectbox("Inspect span", labels)
        span = detail_rows[labels.index(chosen)]
        st.markdown(
            provenance_badge(str(span.get("provenance") or "SIMULATED")),
            unsafe_allow_html=True,
        )
        st.json(span)
