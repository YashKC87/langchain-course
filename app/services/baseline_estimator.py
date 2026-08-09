"""Estimated All-Frontier baseline without making unnecessary Frontier calls."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.models.model_interface import ModelType
from app.observability.cost_calculator import CostCalculator


# Task-specific benchmark averages derived from demo/historical telemetry.
# These are ESTIMATED and must never be presented as ACTUAL provider usage.
BENCHMARKS: dict[str, dict[str, float]] = {
    "planning": {"tokens": 1420, "latency_ms": 1310, "confidence": 0.95},
    "cpu": {"tokens": 1600, "latency_ms": 1900, "confidence": 0.97},
    "cpu_memory": {"tokens": 1600, "latency_ms": 1900, "confidence": 0.97},
    "teams": {"tokens": 1750, "latency_ms": 2000, "confidence": 0.96},
    "network": {"tokens": 1850, "latency_ms": 2100, "confidence": 0.96},
    "vpn": {"tokens": 1850, "latency_ms": 2100, "confidence": 0.96},
    "compliance": {"tokens": 1500, "latency_ms": 1700, "confidence": 0.98},
    "history": {"tokens": 1700, "latency_ms": 1800, "confidence": 0.95},
    "incidents": {"tokens": 1700, "latency_ms": 1800, "confidence": 0.95},
    "rca_synthesis": {"tokens": 2800, "latency_ms": 2600, "confidence": 0.95},
    "synthesis": {"tokens": 2800, "latency_ms": 2600, "confidence": 0.95},
    "complex_rca": {"tokens": 3200, "latency_ms": 2800, "confidence": 0.94},
    "health_classification": {"tokens": 3000, "latency_ms": 2400, "confidence": 0.96},
    "routine_request": {"tokens": 3000, "latency_ms": 2400, "confidence": 0.96},
    "initial_diagnosis": {"tokens": 3600, "latency_ms": 2700, "confidence": 0.94},
    "diagnose": {"tokens": 3600, "latency_ms": 2700, "confidence": 0.94},
    "cascade": {"tokens": 3600, "latency_ms": 2700, "confidence": 0.94},
    "rag_generation": {"tokens": 3400, "latency_ms": 2500, "confidence": 0.95},
    "fallback": {"tokens": 3000, "latency_ms": 2400, "confidence": 0.94},
    "default": {"tokens": 2200, "latency_ms": 2000, "confidence": 0.94},
}


class BaselineEstimator:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.costs = CostCalculator(self.settings)

    def estimate_task(self, task: str) -> dict[str, Any]:
        bench = BENCHMARKS.get(task, BENCHMARKS["default"])
        tokens = int(bench["tokens"])
        cost = self.costs.estimate_total_tokens(ModelType.FRONTIER, tokens)
        return {
            "model_type": ModelType.FRONTIER.value,
            "model_name": f"estimated::{self.settings.frontier_model}",
            "expected_tokens": tokens,
            "expected_latency_ms": float(bench["latency_ms"]),
            "expected_confidence": float(bench["confidence"]),
            "expected_cost": cost,
            "provenance": "ESTIMATED",
            "label": "ESTIMATED ALL-FRONTIER BASELINE",
        }

    def estimate_all_frontier(self, tasks: list[str]) -> dict[str, Any]:
        parts = [self.estimate_task(task) for task in tasks]
        total_tokens = sum(p["expected_tokens"] for p in parts)
        total_latency = sum(p["expected_latency_ms"] for p in parts)
        total_cost = round(sum(p["expected_cost"] for p in parts), 6)
        avg_conf = round(
            sum(p["expected_confidence"] for p in parts) / max(1, len(parts)), 3
        )
        return {
            "label": "ESTIMATED ALL-FRONTIER BASELINE",
            "tasks": parts,
            "total_tokens": total_tokens,
            "total_latency_ms": total_latency,
            "total_cost": total_cost,
            "average_confidence": avg_conf,
            "provenance": "ESTIMATED",
            "note": (
                "Baseline estimated from configured benchmarks and historical telemetry. "
                "No extra Frontier API call was made solely to compute this comparison."
            ),
        }
