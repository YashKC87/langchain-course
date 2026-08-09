"""Premium analytics theme and shared UI primitives."""

from __future__ import annotations

from typing import Any

import streamlit as st

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
  font-family: "IBM Plex Sans", sans-serif;
}
.stApp {
  background:
    radial-gradient(1200px 500px at 10% -10%, rgba(34,211,238,0.12), transparent 50%),
    radial-gradient(900px 400px at 90% 0%, rgba(16,185,129,0.10), transparent 45%),
    linear-gradient(180deg, #0b1220 0%, #111827 45%, #0f172a 100%);
  color: #e5e7eb;
}
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0a101b 0%, #111827 100%);
  border-right: 1px solid rgba(148,163,184,0.18);
}
section[data-testid="stSidebar"] * { color: #e5e7eb !important; }
h1, h2, h3, h4 { letter-spacing: -0.02em; color: #f8fafc !important; }
.block-container { padding-top: 1.2rem; max-width: 1400px; }

.hero-banner {
  border: 1px solid rgba(34,211,238,0.35);
  background: linear-gradient(120deg, rgba(34,211,238,0.14), rgba(16,185,129,0.10));
  border-radius: 16px;
  padding: 1rem 1.25rem;
  margin-bottom: 1rem;
}
.hero-banner .eyebrow {
  color: #67e8f9;
  font-size: 0.78rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.hero-banner .title {
  font-size: 1.55rem;
  font-weight: 700;
  margin: 0.25rem 0;
  color: #f8fafc;
}
.hero-banner .subtitle { color: #cbd5e1; margin: 0; }

.status-strip {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0.6rem;
  margin: 0.8rem 0 1rem 0;
}
.status-chip {
  border: 1px solid rgba(148,163,184,0.25);
  background: rgba(15,23,42,0.72);
  backdrop-filter: blur(8px);
  border-radius: 12px;
  padding: 0.65rem 0.75rem;
}
.status-chip .label {
  color: #94a3b8;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.status-chip .value {
  color: #f8fafc;
  font-weight: 600;
  font-size: 0.95rem;
  margin-top: 0.2rem;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0.65rem;
  margin-bottom: 0.85rem;
}
.kpi-card {
  border: 1px solid rgba(148,163,184,0.22);
  background: linear-gradient(180deg, rgba(30,41,59,0.85), rgba(15,23,42,0.9));
  border-radius: 14px;
  padding: 0.8rem 0.85rem;
  min-height: 92px;
}
.kpi-card .label { color: #94a3b8; font-size: 0.75rem; }
.kpi-card .value {
  color: #f8fafc;
  font-size: 1.35rem;
  font-weight: 700;
  font-family: "IBM Plex Mono", monospace;
  margin: 0.2rem 0;
}
.kpi-card .hint { color: #64748b; font-size: 0.72rem; }

.panel {
  border: 1px solid rgba(148,163,184,0.2);
  background: rgba(15,23,42,0.62);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  padding: 0.95rem 1rem;
  margin-bottom: 0.85rem;
}
.panel h3, .panel h4 { margin-top: 0; }
.panel-title {
  font-size: 0.95rem;
  font-weight: 700;
  color: #f1f5f9;
  margin-bottom: 0.35rem;
}
.panel-note { color: #94a3b8; font-size: 0.82rem; margin-bottom: 0.7rem; }

.badge {
  display: inline-block;
  border-radius: 999px;
  padding: 0.15rem 0.55rem;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  border: 1px solid transparent;
}
.badge-slm { background: rgba(16,185,129,0.18); color: #6ee7b7; border-color: rgba(16,185,129,0.45); }
.badge-frontier { background: rgba(59,130,246,0.18); color: #93c5fd; border-color: rgba(59,130,246,0.45); }
.badge-nonllm { background: rgba(245,158,11,0.16); color: #fcd34d; border-color: rgba(245,158,11,0.4); }
.badge-actual { background: rgba(34,197,94,0.15); color: #86efac; border-color: rgba(34,197,94,0.35); }
.badge-simulated { background: rgba(56,189,248,0.15); color: #7dd3fc; border-color: rgba(56,189,248,0.35); }
.badge-estimated { background: rgba(251,146,60,0.15); color: #fdba74; border-color: rgba(251,146,60,0.35); }

.node-card {
  border: 1px solid rgba(148,163,184,0.22);
  border-radius: 14px;
  padding: 0.8rem;
  background: rgba(2,6,23,0.55);
  margin-bottom: 0.55rem;
}
.node-card .meta {
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.78rem;
  color: #cbd5e1;
  line-height: 1.45;
}
.callout {
  border-left: 3px solid #22d3ee;
  background: rgba(8,47,73,0.45);
  border-radius: 0 12px 12px 0;
  padding: 0.75rem 0.9rem;
  color: #e2e8f0;
  margin: 0.6rem 0 0.9rem 0;
}
.callout.warn {
  border-left-color: #f59e0b;
  background: rgba(69,26,3,0.35);
}
.callout.good {
  border-left-color: #10b981;
  background: rgba(6,78,59,0.35);
}
.pattern-tile {
  border: 1px solid rgba(148,163,184,0.22);
  background: linear-gradient(160deg, rgba(30,41,59,0.9), rgba(15,23,42,0.92));
  border-radius: 14px;
  padding: 0.85rem;
  min-height: 220px;
}
.pattern-tile .name { font-weight: 700; color: #f8fafc; margin-bottom: 0.35rem; }
.pattern-tile .scenario { color: #cbd5e1; font-size: 0.84rem; min-height: 3.2rem; }
.pattern-tile .role { color: #94a3b8; font-size: 0.78rem; margin-top: 0.35rem; }
.pattern-tile .benefit {
  margin-top: 0.55rem;
  color: #6ee7b7;
  font-size: 0.8rem;
  font-weight: 600;
}
div[data-testid="stMetricValue"] { font-family: "IBM Plex Mono", monospace; }
</style>
"""


def inject_theme() -> None:
    st.markdown(THEME_CSS, unsafe_allow_html=True)


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
    # render in rows of 5
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


CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(15,23,42,0.35)",
    font=dict(color="#e2e8f0", family="IBM Plex Sans"),
    margin=dict(l=40, r=20, t=50, b=40),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
)
