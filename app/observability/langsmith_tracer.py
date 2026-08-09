"""LangSmith + local tracing wrapper."""

from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import uuid4

from app.config import Settings, get_settings
from app.models.model_interface import ModelRole, ModelType
from app.observability.cost_calculator import CostCalculator
from app.observability.token_metrics import TokenMetrics
from app.observability.trace_store import TraceStore, get_trace_store


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            key_l = str(key).lower()
            if any(s in key_l for s in ("key", "secret", "token", "password", "authorization")):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = _sanitize(item)
        return redacted
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    return value


@dataclass
class TraceContext:
    trace_id: str
    pattern: str
    scenario: str
    device_id: str | None = None
    parent_run_id: str | None = None
    langsmith_url: str | None = None
    metrics: list[TokenMetrics] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class LangSmithTracer:
    """First-class tracer that works with or without LangSmith connectivity."""

    def __init__(
        self,
        settings: Settings | None = None,
        store: TraceStore | None = None,
    ):
        self.settings = settings or get_settings()
        self.store = store or get_trace_store()
        self.cost_calculator = CostCalculator(self.settings)
        self._client = None
        if self.settings.langsmith_active():
            self._configure_env()
            try:
                from langsmith import Client

                self._client = Client(
                    api_key=self.settings.langsmith_api_key,
                    api_url=self.settings.langsmith_endpoint,
                )
            except Exception:  # noqa: BLE001
                self._client = None

    def _configure_env(self) -> None:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGSMITH_PROJECT"] = self.settings.langsmith_project
        os.environ["LANGSMITH_ENDPOINT"] = self.settings.langsmith_endpoint
        # API key set in process env for SDK; never logged
        os.environ["LANGSMITH_API_KEY"] = self.settings.langsmith_api_key

    @contextlib.contextmanager
    def trace(
        self,
        *,
        pattern: str,
        scenario: str,
        device_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Iterator[TraceContext]:
        ctx = TraceContext(
            trace_id=uuid4().hex,
            pattern=pattern,
            scenario=scenario,
            device_id=device_id,
            metadata=_sanitize(metadata or {}),
        )
        root = self.record(
            ctx,
            segment="root",
            model_name="orchestrator",
            model_type=ModelType.NON_LLM,
            model_role=ModelRole.EVALUATOR,
            provider="local",
            input_tokens=0,
            output_tokens=0,
            latency_ms=0,
            confidence=None,
            metadata={"event": "start"},
        )
        ctx.parent_run_id = root.run_id
        if self._client is not None:
            try:
                run = self._client.create_run(
                    name=f"{pattern}",
                    run_type="chain",
                    inputs=_sanitize({"scenario": scenario, "device_id": device_id}),
                    project_name=self.settings.langsmith_project,
                    extra={"metadata": ctx.metadata},
                )
                run_id = getattr(run, "id", None) or getattr(run, "run_id", None)
                if run_id:
                    ctx.langsmith_url = (
                        f"https://smith.langchain.com/o/default/projects/"
                        f"p/{self.settings.langsmith_project}/r/{run_id}"
                    )
                    ctx.metadata["langsmith_run_id"] = str(run_id)
            except Exception:  # noqa: BLE001
                ctx.langsmith_url = None
        try:
            yield ctx
        finally:
            # already persisted per segment
            pass

    def record(
        self,
        ctx: TraceContext,
        *,
        segment: str,
        model_name: str,
        model_type: ModelType,
        model_role: ModelRole | str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        confidence: float | None = None,
        is_actual_usage: bool = False,
        context_tokens: int = 0,
        metadata: dict[str, Any] | None = None,
        parent_run_id: str | None = None,
    ) -> TokenMetrics:
        cost = self.cost_calculator.estimate(
            model_type=model_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        metrics = TokenMetrics(
            trace_id=ctx.trace_id,
            parent_run_id=parent_run_id or ctx.parent_run_id,
            pattern=ctx.pattern,
            scenario=ctx.scenario,
            device_id=ctx.device_id,
            segment=segment,
            model_name=model_name,
            model_type=model_type,
            model_role=model_role,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            context_tokens=context_tokens,
            latency_ms=latency_ms,
            estimated_cost=cost,
            confidence=confidence,
            is_actual_usage=is_actual_usage,
            provenance="ACTUAL" if is_actual_usage else "SIMULATED",
            metadata=_sanitize(metadata or {}),
            timestamp=datetime.now(timezone.utc),
        )
        self.store.add(metrics)
        ctx.metrics.append(metrics)
        if self._client is not None:
            try:
                self._client.create_run(
                    name=segment,
                    run_type="llm" if model_type != ModelType.NON_LLM else "tool",
                    inputs=_sanitize({"segment": segment, "metadata": metadata or {}}),
                    outputs=_sanitize(
                        {
                            "tokens": metrics.total_tokens,
                            "latency_ms": latency_ms,
                            "confidence": confidence,
                        }
                    ),
                    project_name=self.settings.langsmith_project,
                    parent_run_id=ctx.metadata.get("langsmith_run_id"),
                    extra={
                        "metadata": {
                            "model_name": model_name,
                            "model_type": model_type.value,
                            "model_role": str(model_role),
                            "provider": provider,
                            "estimated_cost": cost,
                            "provenance": metrics.provenance,
                        }
                    },
                )
            except Exception:  # noqa: BLE001
                pass
        return metrics
