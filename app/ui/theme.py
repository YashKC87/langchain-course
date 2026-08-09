"""Premium analytics theme and shared UI primitives."""

from __future__ import annotations

from typing import Any

import streamlit as st

CHART_LAYOUT_DARK = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(15,23,42,0.35)",
    font=dict(color="#e2e8f0", family="IBM Plex Sans"),
    margin=dict(l=40, r=20, t=50, b=40),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
)

CHART_LAYOUT_LIGHT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(248,250,252,0.9)",
    font=dict(color="#0f172a", family="IBM Plex Sans"),
    margin=dict(l=40, r=20, t=50, b=40),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
)

# Mutable chart layout shared by importers; updated when theme changes.
CHART_LAYOUT: dict = dict(CHART_LAYOUT_DARK)


def _css(mode: str) -> str:
    dark = mode != "Light"
    if dark:
        return """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: "IBM Plex Sans", sans-serif; }
.stApp {
  background:
    radial-gradient(1200px 500px at 10% -10%, rgba(34,211,238,0.10), transparent 50%),
    linear-gradient(180deg, #0b1220 0%, #111827 50%, #0f172a 100%);
  color: #e5e7eb;
}
section[data-testid="stSidebar"] {
  background: #0a101b !important;
  border-right: 1px solid rgba(148,163,184,0.25);
  min-width: 17rem;
  transform: none !important;
  visibility: visible !important;
}
section[data-testid="stSidebar"] * { color: #e5e7eb !important; }
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stRadio label { color: #cbd5e1 !important; }
h1, h2, h3, h4 { color: #f8fafc !important; letter-spacing: -0.02em; }
.block-container { padding-top: 0.8rem; max-width: 1440px; }
header[data-testid="stHeader"] { background: rgba(11,18,32,0.85); }
[data-testid="stAppDeployButton"] { display: none !important; }
footer { visibility: hidden; }

.page-header {
  display:flex; align-items:baseline; justify-content:space-between; gap:1rem;
  margin:0 0 0.7rem 0; padding-bottom:0.55rem;
  border-bottom:1px solid rgba(148,163,184,0.18);
}
.page-header .title { font-size:1.25rem; font-weight:700; color:#f8fafc; margin:0; }
.page-header .subtitle { color:#94a3b8; font-size:0.86rem; margin:0; }
.thesis-line {
  color:#a7f3d0; font-size:0.82rem; margin:0 0 0.75rem 0;
  padding:0.35rem 0 0.35rem 0.65rem; border-left:2px solid #10b981;
}
.status-strip { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:0.5rem; margin:0 0 0.75rem 0; }
.status-chip {
  border:1px solid rgba(148,163,184,0.25); background:rgba(15,23,42,0.72);
  border-radius:10px; padding:0.5rem 0.65rem;
}
.status-chip .label { color:#94a3b8; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em; }
.status-chip .value { color:#f8fafc; font-weight:600; font-size:0.92rem; margin-top:0.2rem; }
.kpi-card {
  border:1px solid rgba(148,163,184,0.22);
  background:linear-gradient(180deg, rgba(30,41,59,0.85), rgba(15,23,42,0.9));
  border-radius:12px; padding:0.75rem; min-height:84px; margin-bottom:0.45rem;
}
.kpi-card .label { color:#94a3b8; font-size:0.75rem; }
.kpi-card .value { color:#f8fafc; font-size:1.25rem; font-weight:700; font-family:"IBM Plex Mono", monospace; }
.kpi-card .hint { color:#64748b; font-size:0.72rem; }
.panel {
  border:1px solid rgba(148,163,184,0.2); background:rgba(15,23,42,0.62);
  border-radius:14px; padding:0.9rem 1rem; margin-bottom:0.85rem;
}
.badge { display:inline-block; border-radius:999px; padding:0.15rem 0.55rem; font-size:0.72rem; font-weight:700; }
.badge-slm { background:rgba(16,185,129,0.18); color:#6ee7b7; border:1px solid rgba(16,185,129,0.45); }
.badge-frontier { background:rgba(59,130,246,0.18); color:#93c5fd; border:1px solid rgba(59,130,246,0.45); }
.badge-nonllm { background:rgba(245,158,11,0.16); color:#fcd34d; border:1px solid rgba(245,158,11,0.4); }
.badge-actual { background:rgba(34,197,94,0.15); color:#86efac; border:1px solid rgba(34,197,94,0.35); }
.badge-simulated { background:rgba(56,189,248,0.15); color:#7dd3fc; border:1px solid rgba(56,189,248,0.35); }
.badge-estimated { background:rgba(251,146,60,0.15); color:#fdba74; border:1px solid rgba(251,146,60,0.35); }
.node-card {
  border:1px solid rgba(148,163,184,0.22); border-radius:12px; padding:0.75rem;
  background:rgba(2,6,23,0.55); margin-bottom:0.5rem;
}
.node-card .meta { font-family:"IBM Plex Mono", monospace; font-size:0.78rem; color:#cbd5e1; line-height:1.45; }
.callout {
  border-left:3px solid #22d3ee; background:rgba(8,47,73,0.45);
  border-radius:0 10px 10px 0; padding:0.65rem 0.8rem; color:#e2e8f0; margin:0.5rem 0 0.75rem 0;
}
.callout.warn { border-left-color:#f59e0b; background:rgba(69,26,3,0.35); }
.callout.good { border-left-color:#10b981; background:rgba(6,78,59,0.35); }
.pattern-tile {
  border:1px solid rgba(148,163,184,0.22);
  background:linear-gradient(160deg, rgba(30,41,59,0.9), rgba(15,23,42,0.92));
  border-radius:12px; padding:0.7rem; min-height:170px;
}
.pattern-tile .name { font-weight:700; color:#f8fafc; margin-bottom:0.3rem; }
.pattern-tile .scenario { color:#cbd5e1; font-size:0.82rem; min-height:2.8rem; }
.pattern-tile .role { color:#94a3b8; font-size:0.76rem; margin-top:0.3rem; }
.pattern-tile .benefit { margin-top:0.45rem; color:#6ee7b7; font-size:0.78rem; font-weight:600; }
.sidebar-help {
  margin-top:0.6rem; padding:0.55rem 0.65rem; border-radius:10px;
  border:1px dashed rgba(148,163,184,0.35); color:#94a3b8; font-size:0.75rem;
}
</style>
"""
    return """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: "IBM Plex Sans", sans-serif; }
.stApp {
  background:
    radial-gradient(1000px 420px at 8% -8%, rgba(14,165,233,0.10), transparent 50%),
    linear-gradient(180deg, #f8fafc 0%, #eef2ff 45%, #f8fafc 100%);
  color: #0f172a;
}
section[data-testid="stSidebar"] {
  background: #ffffff !important;
  border-right: 1px solid #dbe3ef;
  min-width: 17rem;
  transform: none !important;
  visibility: visible !important;
}
section[data-testid="stSidebar"] * { color: #0f172a !important; }
h1, h2, h3, h4 { color: #0f172a !important; letter-spacing: -0.02em; }
.block-container { padding-top: 0.8rem; max-width: 1440px; }
header[data-testid="stHeader"] { background: rgba(248,250,252,0.9); }
[data-testid="stAppDeployButton"] { display: none !important; }
footer { visibility: hidden; }

.page-header {
  display:flex; align-items:baseline; justify-content:space-between; gap:1rem;
  margin:0 0 0.7rem 0; padding-bottom:0.55rem; border-bottom:1px solid #dbe3ef;
}
.page-header .title { font-size:1.25rem; font-weight:700; color:#0f172a; margin:0; }
.page-header .subtitle { color:#64748b; font-size:0.86rem; margin:0; }
.thesis-line {
  color:#047857; font-size:0.82rem; margin:0 0 0.75rem 0;
  padding:0.35rem 0 0.35rem 0.65rem; border-left:2px solid #10b981;
}
.status-strip { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:0.5rem; margin:0 0 0.75rem 0; }
.status-chip {
  border:1px solid #dbe3ef; background:#ffffff; border-radius:10px; padding:0.5rem 0.65rem;
  box-shadow: 0 1px 2px rgba(15,23,42,0.04);
}
.status-chip .label { color:#64748b; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em; }
.status-chip .value { color:#0f172a; font-weight:600; font-size:0.92rem; margin-top:0.2rem; }
.kpi-card {
  border:1px solid #dbe3ef; background:#ffffff; border-radius:12px; padding:0.75rem;
  min-height:84px; margin-bottom:0.45rem; box-shadow:0 1px 2px rgba(15,23,42,0.04);
}
.kpi-card .label { color:#64748b; font-size:0.75rem; }
.kpi-card .value { color:#0f172a; font-size:1.25rem; font-weight:700; font-family:"IBM Plex Mono", monospace; }
.kpi-card .hint { color:#94a3b8; font-size:0.72rem; }
.panel {
  border:1px solid #dbe3ef; background:#ffffff; border-radius:14px; padding:0.9rem 1rem; margin-bottom:0.85rem;
}
.badge { display:inline-block; border-radius:999px; padding:0.15rem 0.55rem; font-size:0.72rem; font-weight:700; }
.badge-slm { background:#ecfdf5; color:#047857; border:1px solid #a7f3d0; }
.badge-frontier { background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe; }
.badge-nonllm { background:#fffbeb; color:#b45309; border:1px solid #fde68a; }
.badge-actual { background:#ecfdf5; color:#047857; border:1px solid #a7f3d0; }
.badge-simulated { background:#ecfeff; color:#0e7490; border:1px solid #a5f3fc; }
.badge-estimated { background:#fff7ed; color:#c2410c; border:1px solid #fed7aa; }
.node-card {
  border:1px solid #dbe3ef; border-radius:12px; padding:0.75rem; background:#f8fafc; margin-bottom:0.5rem;
}
.node-card .meta { font-family:"IBM Plex Mono", monospace; font-size:0.78rem; color:#334155; line-height:1.45; }
.callout {
  border-left:3px solid #0284c7; background:#f0f9ff;
  border-radius:0 10px 10px 0; padding:0.65rem 0.8rem; color:#0f172a; margin:0.5rem 0 0.75rem 0;
}
.callout.warn { border-left-color:#d97706; background:#fffbeb; }
.callout.good { border-left-color:#059669; background:#ecfdf5; }
.pattern-tile {
  border:1px solid #dbe3ef; background:#ffffff; border-radius:12px; padding:0.7rem; min-height:170px;
  box-shadow:0 1px 2px rgba(15,23,42,0.04);
}
.pattern-tile .name { font-weight:700; color:#0f172a; margin-bottom:0.3rem; }
.pattern-tile .scenario { color:#475569; font-size:0.82rem; min-height:2.8rem; }
.pattern-tile .role { color:#64748b; font-size:0.76rem; margin-top:0.3rem; }
.pattern-tile .benefit { margin-top:0.45rem; color:#047857; font-size:0.78rem; font-weight:600; }
.sidebar-help {
  margin-top:0.6rem; padding:0.55rem 0.65rem; border-radius:10px;
  border:1px dashed #cbd5e1; color:#64748b; font-size:0.75rem;
}
</style>
"""


def inject_theme(mode: str | None = None) -> None:
    selected = mode or st.session_state.get("ui_theme", "Dark")
    st.markdown(_css(selected), unsafe_allow_html=True)
    # Keep imported CHART_LAYOUT dict in sync for Plotly charts
    CHART_LAYOUT.clear()
    CHART_LAYOUT.update(CHART_LAYOUT_LIGHT if selected == "Light" else CHART_LAYOUT_DARK)


def chart_layout() -> dict:
    mode = st.session_state.get("ui_theme", "Dark")
    return CHART_LAYOUT_LIGHT if mode == "Light" else CHART_LAYOUT_DARK


def badge(model_type: str) -> str:
    key = (model_type or "").upper()
    cls = {
        "SLM": "badge-slm",
        "FRONTIER": "badge-frontier",
        "NON_LLM": "badge-nonllm",
        "NON-LLM": "badge-nonllm",
    }.get(key, "badge-nonllm")
    label = "NON-LLM" if key in {"NON_LLM", "NON-LLM"} else key
    return f'<span class="badge {cls}">{label}</span>'


def provenance_badge(provenance: str) -> str:
    p = (provenance or "SIMULATED").upper()
    cls = {
        "ACTUAL": "badge-actual",
        "SIMULATED": "badge-simulated",
        "ESTIMATED": "badge-estimated",
    }.get(p, "badge-simulated")
    return f'<span class="badge {cls}">{p}</span>'


def panel(title: str, note: str = "", body_html: str = "") -> None:
    st.markdown(
        f"""
<div class="panel">
  <div class="panel-title">{title}</div>
  {"<div class='panel-note'>" + note + "</div>" if note else ""}
  {body_html}
</div>
""",
        unsafe_allow_html=True,
    )


def kpi_grid(items: list[tuple[str, Any, str]]) -> None:
    for i in range(0, len(items), 5):
        chunk = items[i : i + 5]
        cols = st.columns(len(chunk))
        for col, (label, value, hint) in zip(cols, chunk):
            with col:
                st.markdown(
                    f"""
<div class="kpi-card">
  <div class="label">{label}</div>
  <div class="value">{value}</div>
  <div class="hint">{hint}</div>
</div>
""",
                    unsafe_allow_html=True,
                )


def callout(text: str, kind: str = "info") -> None:
    cls = "callout"
    if kind == "warn":
        cls += " warn"
    elif kind == "good":
        cls += " good"
    st.markdown(f'<div class="{cls}">{text}</div>', unsafe_allow_html=True)


def status_strip(chips: list[tuple[str, str]]) -> None:
    html = ['<div class="status-strip">']
    for label, value in chips:
        html.append(
            f'<div class="status-chip"><div class="label">{label}</div>'
            f'<div class="value">{value}</div></div>'
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
<div class="page-header">
  <div class="title">{title}</div>
  {"<div class='subtitle'>" + subtitle + "</div>" if subtitle else ""}
</div>
""",
        unsafe_allow_html=True,
    )
