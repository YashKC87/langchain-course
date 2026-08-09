"""Streamlit application entrypoint — explainable analytics dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.data.generator import write_datasets
from app.services.scenario_service import PATTERN_CATALOG, get_scenario_service
from app.ui.architecture_components import render_kpi_row, render_pattern_page
from app.ui.mlops_dashboard import render_mlops_page
from app.ui.theme import callout, inject_theme, page_header, status_strip

APP_NAME = "Right Model Lab"

st.set_page_config(
    page_title=APP_NAME,
    page_icon="AI",
    layout="wide",
    initial_sidebar_state="expanded",
)

write_datasets()
settings = get_settings()
service = get_scenario_service()

PAGES = [
    "Overview",
    "1 — Planner-Worker",
    "2 — Router Pattern",
    "3 — Confidence Cascade",
    "4 — RAG",
    "5 — Fallback",
    "AI Model Operations",
    "Model Comparison",
]

PAGE_ALIASES = {
    "planner_worker": "1 — Planner-Worker",
    "router": "2 — Router Pattern",
    "confidence_cascade": "3 — Confidence Cascade",
    "rag": "4 — RAG",
    "fallback": "5 — Fallback",
}


def page_overview() -> None:
    status = settings.public_status()
    cards = service.overview_cards()
    mlops = service.mlops_dashboard().get("kpis") or {}

    # Compact analytics toolbar (no large blocking hero panel)
    page_header(APP_NAME, "Right model · right task · measurable evidence")
    st.markdown(
        '<p class="thesis-line">Frontier for planning/ambiguity/synthesis · SLM for routine high-volume work</p>',
        unsafe_allow_html=True,
    )
    status_strip(
        [
            ("Mode", "DEMO" if status["demo_mode"] else "LIVE"),
            ("SLM", f"{status['slm_provider']} / {status['slm_model']}"),
            ("Frontier", f"{status['frontier_provider']} / {status['frontier_model']}"),
            ("LangSmith", "active" if status["langsmith_active"] else "local-only"),
            (
                "Fleet",
                f"{cards.get('endpoints', 0)} · {cards.get('healthy', 0)} healthy · "
                f"{cards.get('at_risk', 0)} risk · {cards.get('critical', 0)} critical",
            ),
        ]
    )

    action_l, action_r = st.columns([1, 4])
    with action_l:
        if st.button("Run all patterns", type="primary", use_container_width=True):
            with st.spinner("Executing patterns (live runs can take several minutes)..."):
                service.run_all()
            st.success("All patterns executed.")
    with action_r:
        st.caption("Demo tip: open a pattern and use “Load latest saved result” for instant review.")

    render_kpi_row(
        cards,
        extras={
            "frontier_tokens_avoided": mlops.get("frontier_tokens_avoided", 0),
            "average_latency_ms": mlops.get("average_latency_ms"),
            "p95_latency_ms": mlops.get("p95_latency_ms"),
            "average_confidence": mlops.get("average_confidence"),
            "estimated_cost": mlops.get("estimated_cost", 0),
        },
    )

    st.markdown("### Patterns")
    saved = service.result_store.all()
    cols = st.columns(5)
    for col, item in zip(cols, PATTERN_CATALOG):
        result = saved.get(item["pattern_id"])
        ts = (
            result.created_at.strftime("%Y-%m-%d %H:%M")
            if result
            else "Not run"
        )
        with col:
            st.markdown(
                f"""
<div class="pattern-tile">
  <div class="name">{item['pattern']}</div>
  <div class="scenario">{item['scenario']}</div>
  <div class="role"><b>SLM:</b> {item['slm_role']}</div>
  <div class="role"><b>Frontier:</b> {item['frontier_role']}</div>
  <div class="benefit">{item['primary_benefit']}</div>
  <div class="role" style="margin-top:0.35rem;">Last run: {ts}</div>
</div>
""",
                unsafe_allow_html=True,
            )
            if st.button("Open", key=f"open_{item['pattern_id']}", use_container_width=True):
                st.session_state["pending_nav_page"] = PAGE_ALIASES[item["pattern_id"]]
                st.rerun()


def _run_and_render(pattern_id: str, **kwargs) -> None:
    if f"result_{pattern_id}" not in st.session_state:
        cached = service.result_store.get(pattern_id)
        if cached is not None:
            st.session_state[f"result_{pattern_id}"] = cached

    col_a, col_b = st.columns(2)
    with col_a:
        run_clicked = st.button(
            f"Execute {pattern_id}",
            type="primary",
            key=f"run_{pattern_id}",
            use_container_width=True,
        )
    with col_b:
        reload_clicked = st.button(
            "Load latest saved result",
            key=f"load_{pattern_id}",
            use_container_width=True,
        )

    if run_clicked:
        with st.spinner(
            "Running pattern with configured providers. Live Ollama/Azure calls can take 1–3+ minutes..."
        ):
            result = service.run_pattern(pattern_id, **kwargs)
        st.session_state[f"result_{pattern_id}"] = result
        st.success("Execution complete.")
    elif reload_clicked:
        cached = service.result_store.get(pattern_id)
        if cached is None:
            st.warning("No saved result yet. Click Execute first.")
        else:
            st.session_state[f"result_{pattern_id}"] = cached
            st.info("Loaded latest saved result.")

    result = st.session_state.get(f"result_{pattern_id}")
    if result is None:
        st.info("Click Execute to run this scenario, or Load latest saved result if one exists.")
        # Still show locked scenario context
        meta = next((p for p in PATTERN_CATALOG if p["pattern_id"] == pattern_id), None)
        if meta:
            st.markdown(f"**Locked scenario:** {meta['scenario']}")
            st.caption(f"SLM role: {meta['slm_role']} · Frontier role: {meta['frontier_role']}")
        return
    render_pattern_page(result)


def page_planner() -> None:
    st.caption("Pattern 1 · Locked to complete multi-domain RCA for LAPTOP-1204")
    _run_and_render("planner_worker")


def page_router() -> None:
    st.caption("Pattern 2 · Locked to routing 100 endpoint health requests")
    _run_and_render("router", n=100)


def page_cascade() -> None:
    st.caption("Pattern 3 · Locked to ambiguous Teams + VPN instability on LAPTOP-9910")
    _run_and_render("confidence_cascade")


def page_rag() -> None:
    st.caption("Pattern 4 · Locked to LAPTOP-1507 disk/OneDrive approved SOP remediation")
    _run_and_render("rag")


def page_fallback() -> None:
    st.caption("Pattern 5 · Locked to critical RCA during Frontier unavailability")
    failure_type = st.selectbox(
        "Simulate Frontier Failure",
        ["http_503", "timeout", "rate_limit", "auth_error", "offline", "cost_guard"],
    )
    st.caption("Controls: 503 · Timeout · Rate Limit · Auth/Service · Offline · Cost Guard")
    _run_and_render("fallback", failure_type=failure_type)


def page_model_comparison() -> None:
    page_header(
        "Model Comparison",
        "Selected vs alternative by segment · tokens · latency · confidence · cost",
    )
    if not service._last_results:
        if st.button("Generate comparisons by running all patterns"):
            service.run_all()
            st.rerun()
    for pattern_id, result in service._last_results.items():
        st.subheader(result.pattern)
        rows = []
        for seg in result.segments:
            if result.pattern_id == "router" and seg.segment.startswith("REQ-"):
                continue
            alt = seg.alternative
            rows.append(
                {
                    "segment": seg.segment,
                    "selected": seg.model_type.value,
                    "selected_tokens": seg.tokens,
                    "selected_latency_ms": seg.latency_ms,
                    "selected_confidence": seg.confidence,
                    "selected_provenance": seg.provenance,
                    "alternative": alt.model_type.value if alt else None,
                    "alt_tokens_ESTIMATED": alt.expected_tokens if alt else None,
                    "alt_latency_ESTIMATED": alt.expected_latency_ms if alt else None,
                    "alt_confidence_ESTIMATED": alt.expected_confidence if alt else None,
                    "decision": seg.decision,
                    "why": seg.decision_why or seg.why,
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)
        if result.architect_decision:
            callout(
                f"Frontier tokens avoided: {result.architect_decision.frontier_tokens_avoided} "
                f"({result.architect_decision.frontier_tokens_avoided_pct}%). "
                f"{result.architect_decision.recommendation}",
                "info",
            )


def main() -> None:
    # Apply navigation requests before the selectbox widget is created.
    pending = st.session_state.pop("pending_nav_page", None)
    if pending in PAGES:
        st.session_state["nav_page"] = pending
    if st.session_state.get("nav_page") not in PAGES:
        st.session_state["nav_page"] = "Overview"
    if "ui_theme" not in st.session_state:
        st.session_state["ui_theme"] = "Dark"

    st.sidebar.markdown(f"### {APP_NAME}")
    st.sidebar.caption("Use this left panel to navigate pages and change theme.")
    theme = st.sidebar.radio("Theme", ["Dark", "Light"], horizontal=True, key="ui_theme")
    inject_theme(theme)

    page = st.sidebar.selectbox("Go to", PAGES, key="nav_page")
    st.sidebar.markdown("---")
    status = settings.public_status()
    st.sidebar.markdown(
        f"""
**Mode:** {"DEMO" if status["demo_mode"] else "LIVE"}  
**SLM:** {status["slm_provider"]} / {status["slm_model"]}  
**Frontier:** {status["frontier_provider"]} / {status["frontier_model"]}  
**LangSmith:** {"active" if status["langsmith_active"] else "local-only"}
"""
    )
    st.sidebar.caption(settings.pricing_disclaimer)
    st.sidebar.caption("Secrets are never displayed.")
    st.sidebar.markdown(
        '<div class="sidebar-help">If the left panel is hidden, click the arrow at the top-left of the page to expand it.</div>',
        unsafe_allow_html=True,
    )

    pages = {
        "Overview": page_overview,
        "1 — Planner-Worker": page_planner,
        "2 — Router Pattern": page_router,
        "3 — Confidence Cascade": page_cascade,
        "4 — RAG": page_rag,
        "5 — Fallback": page_fallback,
        "AI Model Operations": render_mlops_page,
        "Model Comparison": page_model_comparison,
    }
    pages[page]()


def _is_streamlit_runtime() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:  # noqa: BLE001
        return False


if __name__ == "__main__" or _is_streamlit_runtime():
    main()
