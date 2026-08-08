"""Architecture pattern implementations."""

from app.patterns.confidence_cascade import ConfidenceCascadePattern
from app.patterns.fallback import FallbackPattern
from app.patterns.planner_worker import PlannerWorkerPattern
from app.patterns.rag import RAGPattern
from app.patterns.router import RouterPattern

PATTERN_REGISTRY = {
    "planner_worker": PlannerWorkerPattern,
    "router": RouterPattern,
    "confidence_cascade": ConfidenceCascadePattern,
    "rag": RAGPattern,
    "fallback": FallbackPattern,
}

__all__ = [
    "PATTERN_REGISTRY",
    "PlannerWorkerPattern",
    "RouterPattern",
    "ConfidenceCascadePattern",
    "RAGPattern",
    "FallbackPattern",
]
