"""Architectural views for each SLM + Frontier pattern."""

from __future__ import annotations

import streamlit as st

from app.services.scenario_service import PATTERN_CATALOG
from app.ui.theme import callout, inject_theme, page_header

# Explicit node graphs: clear labels, no overlapping text.
PATTERN_ARCHITECTURES: dict[str, dict] = {
    "planner_worker": {
        "short": "Planner-Worker",
        "thesis": "Frontier plans and synthesizes; SLM workers run routine checks in parallel.",
        "lanes": [
            {
                "label": "Plan",
                "nodes": [{"title": "Frontier Planner", "role": "FRONTIER", "desc": "Break RCA into investigation tasks"}],
            },
            {
                "label": "Execute",
                "nodes": [
                    {"title": "SLM Worker · OS", "role": "SLM", "desc": "Routine endpoint checks"},
                    {"title": "SLM Worker · Network", "role": "SLM", "desc": "Connectivity / VPN signals"},
                    {"title": "SLM Worker · App", "role": "SLM", "desc": "Teams / client health"},
                ],
            },
            {
                "label": "Synthesize",
                "nodes": [{"title": "Frontier RCA", "role": "FRONTIER", "desc": "Merge evidence into final RCA"}],
            },
        ],
        "edges": "Incident → Frontier plan → SLM workers → Frontier synthesis → RCA",
    },
    "router": {
        "short": "Router",
        "thesis": "A lightweight router sends routine volume to SLM and hard cases to Frontier.",
        "lanes": [
            {
                "label": "Ingress",
                "nodes": [{"title": "Health Requests", "role": "NON-LLM", "desc": "100 endpoint requests"}],
            },
            {
                "label": "Classify",
                "nodes": [{"title": "Router Node", "role": "NON-LLM", "desc": "Complexity / ambiguity rules"}],
            },
            {
                "label": "Serve",
                "nodes": [
                    {"title": "SLM Path", "role": "SLM", "desc": "Routine health / status"},
                    {"title": "Frontier Path", "role": "FRONTIER", "desc": "Complex / ambiguous RCA"},
                ],
            },
        ],
        "edges": "Request → Router → SLM (routine) or Frontier (complex)",
    },
    "confidence_cascade": {
        "short": "Cascade",
        "thesis": "Try SLM first; escalate to Frontier only when confidence is below threshold.",
        "lanes": [
            {
                "label": "First pass",
                "nodes": [{"title": "SLM Diagnosis", "role": "SLM", "desc": "Fast first-pass RCA"}],
            },
            {
                "label": "Gate",
                "nodes": [{"title": "Confidence Check", "role": "NON-LLM", "desc": "Accept or escalate"}],
            },
            {
                "label": "Escalate",
                "nodes": [
                    {"title": "Accept SLM", "role": "SLM", "desc": "High confidence → done"},
                    {"title": "Frontier RCA", "role": "FRONTIER", "desc": "Low confidence → escalate"},
                ],
            },
        ],
        "edges": "Incident → SLM → confidence gate → accept or Frontier escalate",
    },
    "rag": {
        "short": "RAG",
        "thesis": "Retrieve approved SOPs, then answer with a grounded SLM — Frontier not required.",
        "lanes": [
            {
                "label": "Query",
                "nodes": [{"title": "User / Ticket", "role": "NON-LLM", "desc": "Disk / OneDrive issue"}],
            },
            {
                "label": "Retrieve",
                "nodes": [
                    {"title": "Vector Search", "role": "NON-LLM", "desc": "TF-IDF / embeddings"},
                    {"title": "SOP Knowledge Base", "role": "NON-LLM", "desc": "Approved enterprise docs"},
                ],
            },
            {
                "label": "Generate",
                "nodes": [{"title": "SLM Grounded Answer", "role": "SLM", "desc": "Remediation from retrieved SOP"}],
            },
        ],
        "edges": "Ticket → retrieve SOP → rank context → SLM grounded answer",
    },
    "fallback": {
        "short": "Fallback",
        "thesis": "Prefer Frontier for hard RCA; if it fails, continue on SLM with degraded quality.",
        "lanes": [
            {
                "label": "Primary",
                "nodes": [{"title": "Frontier Attempt", "role": "FRONTIER", "desc": "Advanced RCA path"}],
            },
            {
                "label": "Detect",
                "nodes": [{"title": "Failure Detector", "role": "NON-LLM", "desc": "503 · timeout · rate limit · offline"}],
            },
            {
                "label": "Continue",
                "nodes": [
                    {"title": "Frontier Success", "role": "FRONTIER", "desc": "Primary path OK"},
                    {"title": "SLM Fallback", "role": "SLM", "desc": "Availability continuity"},
                ],
            },
        ],
        "edges": "Incident → Frontier → on failure → SLM fallback → response",
    },
}


def _role_class(role: str) -> str:
    key = (role or "").upper()
    if key == "SLM":
        return "slm"
    if key == "FRONTIER":
        return "frontier"
    return "nonllm"


def render_architecture_diagram(pattern_id: str) -> None:
    """Render one pattern's architectural flow as a clear labeled diagram."""
    meta = next((p for p in PATTERN_CATALOG if p["pattern_id"] == pattern_id), None)
    arch = PATTERN_ARCHITECTURES.get(pattern_id)
    if not meta or not arch:
        st.warning(f"No architecture defined for {pattern_id}")
        return

    lanes_html: list[str] = []
    for idx, lane in enumerate(arch["lanes"]):
        nodes_html = "".join(
            f"""
            <div class="arch-node {_role_class(node['role'])}">
              <div class="arch-role">{node['role']}</div>
              <div class="arch-title">{node['title']}</div>
              <div class="arch-desc">{node['desc']}</div>
            </div>
            """
            for node in lane["nodes"]
        )
        lanes_html.append(
            f"""
            <div class="arch-lane">
              <div class="arch-lane-label">Step {idx + 1} · {lane['label']}</div>
              <div class="arch-nodes">{nodes_html}</div>
            </div>
            """
        )
        if idx < len(arch["lanes"]) - 1:
            lanes_html.append('<div class="arch-connector" aria-hidden="true">→</div>')

    st.markdown(
        f"""
<div class="arch-card">
  <div class="arch-head">
    <div class="arch-name">{meta['pattern']}</div>
    <div class="arch-scenario">{meta['scenario']}</div>
  </div>
  <div class="arch-thesis">{arch['thesis']}</div>
  <div class="arch-flow">
    {''.join(lanes_html)}
  </div>
  <div class="arch-legend">
    <span class="arch-pill slm">SLM</span>
    <span class="arch-pill frontier">FRONTIER</span>
    <span class="arch-pill nonllm">NON-LLM</span>
    <span class="arch-edge">{arch['edges']}</span>
  </div>
  <div class="arch-roles">
    <div><b>SLM role:</b> {meta['slm_role']}</div>
    <div><b>Frontier role:</b> {meta['frontier_role']}</div>
    <div><b>Primary benefit:</b> {meta['primary_benefit']}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_architecture_page() -> None:
    inject_theme()
    page_header(
        "Architecture",
        "One diagram per pattern · SLM · Frontier · NON-LLM",
    )
    callout(
        "Each view shows how work moves between models. Frontier is reserved for planning, "
        "ambiguity, and synthesis; SLM handles routine high-volume work.",
        "info",
    )
    st.markdown(
        """
<div class="arch-system">
  <div class="arch-system-title">System context</div>
  <div class="arch-system-flow">
    <div class="arch-node nonllm"><div class="arch-role">NON-LLM</div><div class="arch-title">Device Fleet</div><div class="arch-desc">Endpoints · incidents · telemetry</div></div>
    <div class="arch-connector">→</div>
    <div class="arch-node nonllm"><div class="arch-role">NON-LLM</div><div class="arch-title">Right Model Lab</div><div class="arch-desc">Pattern engines · metrics</div></div>
    <div class="arch-connector">→</div>
    <div class="arch-node slm"><div class="arch-role">SLM</div><div class="arch-title">Local / Ollama</div><div class="arch-desc">Routine inference</div></div>
    <div class="arch-connector">→</div>
    <div class="arch-node frontier"><div class="arch-role">FRONTIER</div><div class="arch-title">Azure OpenAI</div><div class="arch-desc">Reasoning capacity</div></div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    for item in PATTERN_CATALOG:
        render_architecture_diagram(item["pattern_id"])
        st.markdown("")  # spacing
