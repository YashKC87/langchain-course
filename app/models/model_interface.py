"""Provider-independent language model interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ModelType(str, Enum):
    SLM = "SLM"
    FRONTIER = "FRONTIER"
    NON_LLM = "NON_LLM"


class ModelRole(str, Enum):
    PLANNER = "planner"
    WORKER = "worker"
    ROUTER = "router"
    SYNTHESIZER = "synthesizer"
    DIAGNOSER = "diagnoser"
    GENERATOR = "generator"
    CLASSIFIER = "classifier"
    FALLBACK = "fallback"
    EVALUATOR = "evaluator"
    RETRIEVER = "retriever"


class UsageStats(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    latency_ms: float = 0.0
    is_actual_usage: bool = False
    provenance: str = "SIMULATED"  # ACTUAL | SIMULATED | ESTIMATED

    def model_post_init(self, __context: Any) -> None:
        if self.total_tokens == 0:
            self.total_tokens = self.input_tokens + self.output_tokens
        if self.is_actual_usage:
            self.provenance = "ACTUAL"
        elif self.provenance not in {"ACTUAL", "SIMULATED", "ESTIMATED"}:
            self.provenance = "SIMULATED"


class GenerationResult(BaseModel):
    text: str
    structured: dict[str, Any] | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    usage: UsageStats = Field(default_factory=UsageStats)
    model_name: str = ""
    model_type: ModelType = ModelType.SLM
    provider: str = "demo"
    metadata: dict[str, Any] = Field(default_factory=dict)


class LanguageModel(ABC):
    """Common interface for SLM and Frontier clients."""

    model_type: ModelType
    provider: str
    model_name: str

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 800,
        metadata: dict[str, Any] | None = None,
    ) -> GenerationResult:
        raise NotImplementedError

    @abstractmethod
    def structured_generate(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        system: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 800,
        metadata: dict[str, Any] | None = None,
    ) -> GenerationResult:
        raise NotImplementedError

    @abstractmethod
    def classify(
        self,
        text: str,
        labels: list[str],
        *,
        metadata: dict[str, Any] | None = None,
    ) -> GenerationResult:
        raise NotImplementedError

    @abstractmethod
    def summarize(
        self,
        text: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> GenerationResult:
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_usage(self) -> UsageStats:
        raise NotImplementedError
