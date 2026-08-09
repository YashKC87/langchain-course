"""Shared execution result schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.model_interface import ModelRole, ModelType


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AlternativeEstimate(BaseModel):
    model_type: ModelType
    model_name: str
    expected_tokens: int
    expected_latency_ms: float
    expected_confidence: float
    expected_cost: float
    provenance: Literal["ESTIMATED"] = "ESTIMATED"
    recommendation: str = ""
    rationale: str = ""


class SegmentResult(BaseModel):
    segment: str
    task: str
    model_name: str
    model_type: ModelType
    model_role: ModelRole
    provider: str
    tokens: int
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float
    confidence: float = 0.0
    why: str
    content: str = ""
    structured: dict[str, Any] = Field(default_factory=dict)
    is_actual_usage: bool = False
    provenance: str = "SIMULATED"
    estimated_cost: float = 0.0
    alternative: AlternativeEstimate | None = None
    decision: str = ""
    decision_why: str = ""


class ArchitectDecision(BaseModel):
    pattern: str
    scenario: str
    frontier_used_for: list[str]
    slm_used_for: list[str]
    why_this_architecture: str
    slm_calls: int
    frontier_calls: int
    slm_tokens: int
    frontier_tokens: int
    total_tokens: int
    all_frontier_tokens: int
    frontier_tokens_avoided: int
    frontier_tokens_avoided_pct: float
    hybrid_latency_ms: float
    all_frontier_latency_ms: float
    hybrid_confidence: float
    all_frontier_confidence: float
    hybrid_cost: float
    all_frontier_cost: float
    cost_avoided: float
    recommendation: str
    notes: list[str] = Field(default_factory=list)


class PatternResult(BaseModel):
    pattern: str
    pattern_id: str
    scenario: str
    device_id: str | None = None
    segments: list[SegmentResult] = Field(default_factory=list)
    summary: str = ""
    findings: dict[str, Any] = Field(default_factory=dict)
    architect_decision: ArchitectDecision | None = None
    trace_id: str = ""
    langsmith_url: str | None = None
    comparisons: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
