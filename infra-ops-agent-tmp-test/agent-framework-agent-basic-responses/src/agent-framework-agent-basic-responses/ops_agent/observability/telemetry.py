"""Observability helpers — emit structured events for App Insights / LA."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import json


class OpsTelemetry:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def emit(self, name: str, properties: dict[str, Any], metrics: dict[str, float] | None = None) -> None:
        self.events.append(
            {
                "name": name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "properties": properties,
                "metrics": metrics or {},
            }
        )

    def tool_call(self, tool: str, ok: bool, duration_ms: float, correlation_id: str) -> None:
        self.emit(
            "tool_call",
            {"tool": tool, "ok": ok, "correlation_id": correlation_id},
            {"duration_ms": duration_ms},
        )

    def prediction(self, model_version: str, probability: float, latency_ms: float) -> None:
        self.emit(
            "prediction",
            {"model_version": model_version},
            {"probability": probability, "latency_ms": latency_ms},
        )

    def dump(self) -> str:
        return json.dumps(self.events, indent=2)


DASHBOARD_TILES = [
    "overall_agent_health",
    "specialist_agent_activity",
    "tool_success_rate",
    "top_incident_categories",
    "prediction_performance",
    "automation_success",
    "approvals",
    "token_and_inference_cost",
    "security_events",
    "business_outcomes",
]
