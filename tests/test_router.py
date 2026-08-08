from app.models.model_interface import ModelType
from app.observability.langsmith_tracer import LangSmithTracer
from app.patterns.router import RouterPattern


def test_router_splits_routine_and_complex(trace_store):
    pattern = RouterPattern(tracer=LangSmithTracer(store=trace_store))
    result = pattern.run(n=100)
    per_request = result.metadata["per_request"]
    slm = [r for r in per_request if r["selected_model"] == "SLM"]
    frontier = [r for r in per_request if r["selected_model"] == "FRONTIER"]
    assert len(per_request) == 100
    assert len(slm) == 85
    assert len(frontier) == 15
    assert any(s.model_type == ModelType.NON_LLM for s in result.segments)
    assert result.comparisons["frontier_calls_avoided"] == 85
    assert result.comparisons["examples"]["routine"] is not None
    assert result.comparisons["examples"]["complex"] is not None
