"""Token and execution metrics models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from app.models.model_interface import ModelRole, ModelType


def new_id() -> str:
    return uuid4().hex


class TokenMetrics(BaseModel):
    trace_id: str
    run_id: str = Field(default_factory=new_id)
    parent_run_id: str | None = None
    pattern: str
    scenario: str
    device_id: str | None = None
    segment: str
    model_name: str
    model_type: ModelType
    model_role: ModelRole | str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    context_tokens: int = 0
    latency_ms: float = 0.0
    estimated_cost: float = 0.0
    confidence: float | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_actual_usage: bool = False
    provenance: Literal["ACTUAL", "SIMULATED", "ESTIMATED"] = "SIMULATED"
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if self.total_tokens == 0:
            self.total_tokens = self.input_tokens + self.output_tokens
        if self.is_actual_usage:
            self.provenance = "ACTUAL"
