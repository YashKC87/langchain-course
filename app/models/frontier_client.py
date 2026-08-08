"""Azure OpenAI-compatible Frontier client."""

from __future__ import annotations

import json
import time
from typing import Any

from app.models.demo_model import FrontierUnavailableError
from app.models.model_interface import (
    GenerationResult,
    LanguageModel,
    ModelType,
    UsageStats,
)


class AzureFrontierClient(LanguageModel):
    """Frontier client using the OpenAI Azure SDK behind a common interface."""

    def __init__(
        self,
        *,
        model_name: str,
        endpoint: str,
        api_key: str,
        api_version: str,
        deployment: str,
        timeout_seconds: float = 60.0,
    ):
        self.model_name = model_name
        self.provider = "azure_openai"
        self.model_type = ModelType.FRONTIER
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.api_version = api_version
        self.deployment = deployment
        self.timeout_seconds = timeout_seconds
        self._usage = UsageStats(is_actual_usage=False, provenance="SIMULATED")
        self._fail_mode: str | None = None
        self._client = None

    def set_failure_mode(self, mode: str | None) -> None:
        self._fail_mode = mode

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from openai import AzureOpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("openai package is required for AzureFrontierClient") from exc
        self._client = AzureOpenAI(
            api_key=self.api_key,
            api_version=self.api_version,
            azure_endpoint=self.endpoint,
            timeout=self.timeout_seconds,
        )
        return self._client

    def _maybe_fail(self) -> None:
        if not self._fail_mode:
            return
        raise FrontierUnavailableError(
            f"Simulated Frontier failure: {self._fail_mode}",
            code=503,
            failure_type=self._fail_mode,
        )

    def _complete(self, prompt: str, system: str | None = None) -> tuple[str, UsageStats]:
        self._maybe_fail()
        client = self._get_client()
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        started = time.perf_counter()
        try:
            response = client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                temperature=0.2,
            )
        except Exception as exc:  # noqa: BLE001
            message = str(exc).lower()
            if "timeout" in message:
                failure = "timeout"
                code = 408
            elif "429" in message or "rate" in message:
                failure = "rate_limit"
                code = 429
            elif "auth" in message or "401" in message or "403" in message:
                failure = "auth_error"
                code = 401
            else:
                failure = "http_503"
                code = 503
            raise FrontierUnavailableError(str(exc), code=code, failure_type=failure) from exc
        latency_ms = (time.perf_counter() - started) * 1000
        text = response.choices[0].message.content or ""
        usage_obj = getattr(response, "usage", None)
        if usage_obj is not None:
            input_tokens = int(getattr(usage_obj, "prompt_tokens", 0) or 0)
            output_tokens = int(getattr(usage_obj, "completion_tokens", 0) or 0)
            actual = True
        else:
            input_tokens = max(1, len(prompt) // 4)
            output_tokens = max(1, len(text) // 4)
            actual = False
        usage = UsageStats(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            latency_ms=round(latency_ms, 1),
            is_actual_usage=actual,
            provenance="ACTUAL" if actual else "SIMULATED",
        )
        self._usage = usage
        return text, usage

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 800,
        metadata: dict[str, Any] | None = None,
    ) -> GenerationResult:
        text, usage = self._complete(prompt, system)
        return GenerationResult(
            text=text,
            confidence=0.94,
            usage=usage,
            model_name=self.model_name,
            model_type=self.model_type,
            provider=self.provider,
            metadata=metadata or {},
        )

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
        schema_prompt = (
            f"{prompt}\n\nReturn ONLY valid JSON matching this schema:\n"
            f"{json.dumps(schema)}"
        )
        text, usage = self._complete(schema_prompt, system)
        try:
            structured = json.loads(text)
        except json.JSONDecodeError:
            structured = {"raw": text}
        return GenerationResult(
            text=text,
            structured=structured,
            confidence=0.93,
            usage=usage,
            model_name=self.model_name,
            model_type=self.model_type,
            provider=self.provider,
            metadata=metadata or {},
        )

    def classify(
        self,
        text: str,
        labels: list[str],
        *,
        metadata: dict[str, Any] | None = None,
    ) -> GenerationResult:
        prompt = (
            f"Classify the following into one label from {labels}.\n\nTEXT:\n{text}\n\n"
            "Respond with the label only."
        )
        result = self.generate(prompt, metadata=metadata)
        label = result.text.strip().splitlines()[0]
        result.structured = {"label": label, "labels": labels}
        return result

    def summarize(
        self,
        text: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> GenerationResult:
        return self.generate(f"Summarize with architectural rigor:\n{text}", metadata=metadata)

    def health_check(self) -> dict[str, Any]:
        if not (self.endpoint and self.api_key and self.deployment):
            return {
                "healthy": False,
                "provider": self.provider,
                "error": "Azure OpenAI is not fully configured",
            }
        return {
            "healthy": True,
            "provider": self.provider,
            "model": self.model_name,
            "deployment": self.deployment,
            "model_type": self.model_type.value,
        }

    def get_usage(self) -> UsageStats:
        return self._usage
