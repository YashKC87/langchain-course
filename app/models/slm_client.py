"""Ollama-compatible local SLM client."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.models.model_interface import (
    GenerationResult,
    LanguageModel,
    ModelType,
    UsageStats,
)


class LocalSLMClient(LanguageModel):
    """Talks to an Ollama-compatible HTTP API. Model name is configurable."""

    def __init__(
        self,
        model_name: str,
        base_url: str = "http://localhost:11434",
        timeout_seconds: float = 60.0,
    ):
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.provider = "ollama"
        self.model_type = ModelType.SLM
        self._usage = UsageStats(is_actual_usage=False, provenance="SIMULATED")

    def _chat(self, prompt: str, system: str | None = None) -> tuple[str, UsageStats]:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.2},
        }
        started = time.perf_counter()
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        latency_ms = (time.perf_counter() - started) * 1000
        text = data.get("message", {}).get("content", "")
        # Ollama may return eval counts
        input_tokens = int(data.get("prompt_eval_count") or max(1, len(prompt) // 4))
        output_tokens = int(data.get("eval_count") or max(1, len(text) // 4))
        actual = "prompt_eval_count" in data or "eval_count" in data
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
        text, usage = self._chat(prompt, system)
        return GenerationResult(
            text=text,
            confidence=0.88,
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
        text, usage = self._chat(schema_prompt, system)
        structured: dict[str, Any] | None
        try:
            structured = json.loads(text)
        except json.JSONDecodeError:
            structured = {"raw": text}
        return GenerationResult(
            text=text,
            structured=structured,
            confidence=0.85,
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
        return self.generate(f"Summarize concisely:\n{text}", metadata=metadata)

    def health_check(self) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
            return {
                "healthy": True,
                "provider": self.provider,
                "model": self.model_name,
                "model_type": self.model_type.value,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "healthy": False,
                "provider": self.provider,
                "model": self.model_name,
                "error": str(exc),
            }

    def get_usage(self) -> UsageStats:
        return self._usage
