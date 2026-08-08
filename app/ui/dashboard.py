"""Streamlit application entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Ensure project root is importable when launched via `streamlit run app/ui/dashboard.py`
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.data.generator import write_datasets
from app.services.scenario_service import PATTERN_CATALOG, get_scenario_service
from app.ui.architecture_components import render_kpi_row, render_pattern_page
from app.ui.mlops_dashboard import render_langsmith_page, render_mlops_page
from app.ui.trace_explorer import render_trace_explorer

st.set_page_config(
    page_title="SLM + Frontier Architecture Lab",
    page_icon="AI",
    layout="wide",
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
    "LangSmith / LLMOps",
    "Trace Explorer",
    "Architecture",
    "Model Comparison",
]


def page_overview() -> None:
    st.title("SLM + FRONTIER AI ARCHITECTURE LAB")
    st.subheader("Digital Workplace Device Monitoring")
    st.caption(
        "USE THE RIGHT MODEL FOR THE RIGHT TASK — Demo Mode returns deterministic SIMULATED metrics."
    )
    status = settings.public_status()
    st.write(
        {
            "demo_mode": status["demo_mode"],
            "slm": f"{status['slm_provider']} / {status['slm_model']}",
            "frontier": f"{status['frontier_provider']} / {status['frontier_model']}",
            "langsmith_active": status["langsmith_active"],
        }
    )
    if st.button("Run all five pattern scenarios", type="primary"):
        with st.spinner("Executing patterns..."):
            service.run_all()
        st.success("All patterns executed. Metrics refreshed.")
    cards = service.overview_cards()
    render_kpi_row(cards)

    st.header("The Five Architecture Patterns")
    cols = st.columns(5)
    for col, item in zip(cols, PATTERN_CATALOG):
        with col:
            st.markdown(f"### {item['pattern']}")
            st.write(item["scenario"])
            st.caption(f"SLM: {item['slm_role']}")
            st.caption(f"Frontier: {item['frontier_role']}")
            st.success(item["primary_benefit"])


def _run_and_render(pattern_id: str, **kwargs) -> None:
    # Hydrate from persisted results so refreshes still show the latest execution.
    if f"result_{pattern_id}" not in st.session_state:
        cached = service.result_store.get(pattern_id)
        if cached is not None:
            st.session_state[f"result_{pattern_id}"] = cached

    col_a, col_b = st.columns([1, 1])
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
            "Running pattern with live/demo providers. Live Ollama/Azure calls can take 1–3 minutes..."
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
        return
    render_pattern_page(result)


def page_planner() -> None:
    st.title("Pattern 1 — Planner-Worker Hierarchy")
    st.write("Scenario locked to complete multi-domain RCA for LAPTOP-1204.")
    _run_and_render("planner_worker")


def page_router() -> None:
    st.title("Pattern 2 — Router Pattern")
    st.write("Scenario locked to routing 100 endpoint health requests.")
    _run_and_render("router", n=100)


def page_cascade() -> None:
    st.title("Pattern 3 — Confidence Cascade")
    st.write("Scenario locked to ambiguous Teams + VPN instability on LAPTOP-9910.")
    _run_and_render("confidence_cascade")
    result = st.session_state.get("result_confidence_cascade")
    if result and result.comparisons.get("cascade_exceeds_direct_frontier"):
        st.error(result.comparisons.get("callout"))
        st.json(result.comparisons.get("fleet_economics"))


def page_rag() -> None:
    st.title("Pattern 4 — RAG")
    st.write("Scenario locked to LAPTOP-1507 disk/OneDrive approved SOP remediation.")
    _run_and_render("rag")


def page_fallback() -> None:
    st.title("Pattern 5 — Designing for Fallback")
    st.write("Scenario locked to critical RCA during Frontier unavailability.")
    failure_type = st.selectbox(
        "Simulate Frontier Failure",
        ["http_503", "timeout", "rate_limit", "auth_error", "offline", "cost_guard"],
    )
    st.caption("UI controls: Simulate Frontier Failure / Timeout / Rate Limit / Offline / Cost Guard")
    _run_and_render("fallback", failure_type=failure_type)
    result = st.session_state.get("result_fallback")
    if result:
        st.warning(result.comparisons.get("callout"))


def page_architecture() -> None:
    st.title("SLM + Frontier Architecture Summary")
    st.markdown(
        """
```
                    DEVICE MONITORING
                           |
     ------------------------------------------------
     |          |           |          |           |
     v          v           v          v           v
 PLANNER      ROUTER     CONFIDENCE    RAG      FALLBACK
 WORKER                  CASCADE
     |          |           |          |           |
     v          v           v          v           v
 Frontier     SLM/F       SLM→F      KB+SLM      F→SLM
 +SLMs
```
"""
    )
    st.subheader("Executive Model Analogy")
    st.markdown(
        """
**SLM** — Think of it as an experienced Service Desk Engineer. Fast. Low cost. Handles known and repetitive work.

**Frontier Model** — Think of it as a Senior Solution Architect. More expensive. More reasoning capability. Use for difficult or unfamiliar problems.

**Planner-Worker** — Senior Architect creates the plan. Service Desk engineers perform routine checks. Senior Architect reviews everything and produces the RCA.

**Router** — Dispatcher looks at the request. Easy work → Service Desk Engineer. Difficult work → Senior Architect.

**Confidence Cascade** — Service Desk Engineer tries first. If confident → finish. If uncertain → escalate to Senior Architect.

**RAG** — Engineer checks the approved SOP before answering.

**Fallback** — Senior Architect is unavailable. Local engineer continues service with reduced capability.
"""
    )
    for item in PATTERN_CATALOG:
        st.markdown(f"### {item['pattern']}")
        st.write(item["scenario"])
        st.write(f"- SLM role: {item['slm_role']}")
        st.write(f"- Frontier role: {item['frontier_role']}")
        st.write(f"- Primary benefit: {item['primary_benefit']}")


def page_model_comparison() -> None:
    st.title("Model Comparison")
    st.write(
        "Lower token count is NOT automatically better. Compare tokens, cost, latency, "
        "confidence, grounding, escalation, and availability."
    )
    if not service._last_results:
        if st.button("Generate comparisons by running all patterns"):
            service.run_all()
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
                    "alternative": alt.model_type.value if alt else None,
                    "alt_tokens": alt.expected_tokens if alt else None,
                    "alt_latency_ms": alt.expected_latency_ms if alt else None,
                    "alt_confidence": alt.expected_confidence if alt else None,
                    "decision": seg.decision,
                    "why": seg.decision_why or seg.why,
                    "selected_provenance": seg.provenance,
                    "alt_provenance": alt.provenance if alt else None,
                }
            )
        st.dataframe(rows, use_container_width=True)


def main() -> None:
    st.sidebar.title("Navigation")
    # selectbox is more reliable than radio in some remote/browser automation setups
    page = st.sidebar.selectbox("Go to", PAGES, index=0, key="nav_page")
    st.sidebar.markdown("---")
    st.sidebar.write(settings.public_status())
    st.sidebar.caption(settings.pricing_disclaimer)
    st.sidebar.caption("Secrets are never displayed.")

    pages = {
        "Overview": page_overview,
        "1 — Planner-Worker": page_planner,
        "2 — Router Pattern": page_router,
        "3 — Confidence Cascade": page_cascade,
        "4 — RAG": page_rag,
        "5 — Fallback": page_fallback,
        "AI Model Operations": render_mlops_page,
        "LangSmith / LLMOps": render_langsmith_page,
        "Trace Explorer": render_trace_explorer,
        "Architecture": page_architecture,
        "Model Comparison": page_model_comparison,
    }
    pages[page]()


if __name__ == "__main__":
    main()
else:
    main()
