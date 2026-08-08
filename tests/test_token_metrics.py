from app.config import get_settings
from app.models.factory import build_frontier_client, build_slm_client
from app.models.model_interface import ModelType
from app.observability.cost_calculator import CostCalculator
from app.observability.langsmith_tracer import LangSmithTracer
from app.observability.token_metrics import TokenMetrics
from app.services.baseline_estimator import BaselineEstimator
from app.services.scenario_service import ScenarioService


def test_token_metrics_provenance():
    m = TokenMetrics(
        trace_id="t1",
        pattern="p",
        scenario="s",
        segment="seg",
        model_name="demo",
        model_type=ModelType.SLM,
        model_role="worker",
        provider="demo",
        input_tokens=10,
        output_tokens=5,
        is_actual_usage=False,
    )
    assert m.total_tokens == 15
    assert m.provenance == "SIMULATED"


def test_demo_mode_and_langsmith_disabled(trace_store):
    settings = get_settings()
    assert settings.effective_demo_mode() is True
    assert settings.langsmith_active() is False
    tracer = LangSmithTracer(settings=settings, store=trace_store)
    with tracer.trace(pattern="demo", scenario="s") as ctx:
        tracer.record(
            ctx,
            segment="x",
            model_name="demo",
            model_type=ModelType.SLM,
            model_role="worker",
            provider="demo",
            input_tokens=1,
            output_tokens=1,
            latency_ms=1,
        )
    assert trace_store.aggregates()["total_model_calls"] >= 1


def test_baseline_estimator_does_not_need_frontier_client():
    est = BaselineEstimator()
    baseline = est.estimate_all_frontier(["planning", "cpu", "rca_synthesis"])
    assert baseline["provenance"] == "ESTIMATED"
    assert "No extra Frontier API call" in baseline["note"]
    assert baseline["total_tokens"] > 0


def test_cost_calculator_disclaimer():
    calc = CostCalculator()
    assert "Illustrative" in calc.disclaimer
    cost = calc.estimate(model_type=ModelType.FRONTIER, input_tokens=1000, output_tokens=1000)
    assert cost > 0


def test_model_factory_demo_clients():
    slm = build_slm_client()
    frontier = build_frontier_client()
    assert slm.provider == "demo"
    assert frontier.provider == "demo"
    assert slm.health_check()["healthy"] is True


def test_scenario_service_run_all(scenario_service: ScenarioService):
    results = scenario_service.run_all()
    assert set(results) == {
        "planner_worker",
        "router",
        "confidence_cascade",
        "rag",
        "fallback",
    }
    dash = scenario_service.mlops_dashboard()
    assert "kpis" in dash
    assert dash["efficiency_table"]
