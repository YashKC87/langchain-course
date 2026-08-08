from app.models.model_interface import ModelType
from app.patterns.planner_worker import PlannerWorkerPattern
from app.observability.langsmith_tracer import LangSmithTracer


def test_planner_worker_roles(trace_store):
    pattern = PlannerWorkerPattern(tracer=LangSmithTracer(store=trace_store))
    result = pattern.run()
    assert result.device_id == "LAPTOP-1204"
    assert result.pattern_id == "planner_worker"
    types = {s.segment: s.model_type for s in result.segments}
    assert types["Planning"] == ModelType.FRONTIER
    assert types["CPU Analysis"] == ModelType.SLM
    assert types["Teams Analysis"] == ModelType.SLM
    assert types["Network/VPN Analysis"] == ModelType.SLM
    assert types["Compliance Analysis"] == ModelType.SLM
    assert types["History Analysis"] == ModelType.SLM
    assert types["RCA Synthesis"] == ModelType.FRONTIER
    assert result.architect_decision is not None
    assert result.architect_decision.frontier_calls == 2
    assert result.architect_decision.slm_calls == 5
    assert result.comparisons["estimated_all_frontier"]["label"]
    assert "ESTIMATED" in result.comparisons["estimated_all_frontier"]["label"]
