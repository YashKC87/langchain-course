from app.models.model_interface import ModelType
from app.observability.langsmith_tracer import LangSmithTracer
from app.patterns.fallback import FallbackPattern


def test_fallback_activates_slm_on_frontier_failure(trace_store):
    pattern = FallbackPattern(tracer=LangSmithTracer(store=trace_store))
    result = pattern.run(failure_type="http_503")
    assert result.findings["availability_maintained"] is True
    assert any(s.segment == "FRONTIER Attempt" for s in result.segments)
    slm = next(s for s in result.segments if s.segment == "SLM Fallback")
    assert slm.model_type == ModelType.SLM
    assert "RESILIENCY" in result.comparisons["callout"] or "availability" in result.comparisons["callout"].lower()


def test_fallback_modes(trace_store):
    pattern = FallbackPattern(tracer=LangSmithTracer(store=trace_store))
    for mode in ["timeout", "rate_limit", "auth_error", "offline", "cost_guard"]:
        result = pattern.run(failure_type=mode)
        assert result.metadata["failure"]["failed"] is True
