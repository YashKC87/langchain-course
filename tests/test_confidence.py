from app.models.model_interface import ModelType
from app.observability.langsmith_tracer import LangSmithTracer
from app.patterns.confidence_cascade import ConfidenceCascadePattern


def test_confidence_cascade_escalates_low_confidence(trace_store):
    pattern = ConfidenceCascadePattern(tracer=LangSmithTracer(store=trace_store))
    result = pattern.run()
    assert result.device_id == "LAPTOP-9910"
    assert result.comparisons["initial_confidence"] == 0.54
    assert result.comparisons["threshold"] == 0.85
    assert result.comparisons["escalated"] is True
    model_types = [s.model_type for s in result.segments]
    assert ModelType.SLM in model_types
    assert ModelType.FRONTIER in model_types
    assert result.comparisons["cascade_exceeds_direct_frontier"] in {True, False}
    assert "fleet_economics" in result.comparisons
    assert len(result.comparisons["options"]) == 3


def test_high_confidence_avoids_escalation():
    pattern = ConfidenceCascadePattern()
    smoke = pattern.run_high_confidence_smoke()
    assert smoke["confidence"] >= smoke["threshold"]
    assert smoke["escalated"] is False
