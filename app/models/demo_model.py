"""Deterministic Demo Mode SLM and Frontier clients."""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

from app.models.model_interface import (
    GenerationResult,
    LanguageModel,
    ModelType,
    UsageStats,
)


def _stable_int(text: str, modulo: int = 10_000) -> int:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo


def _estimate_tokens(text: str) -> int:
    # Rough but stable tokenizer substitute for demo mode
    words = re.findall(r"\w+|[^\w\s]", text or "")
    return max(1, int(len(words) * 1.3))


class _DemoBase(LanguageModel):
    def __init__(self, model_name: str, provider: str, model_type: ModelType):
        self.model_name = model_name
        self.provider = provider
        self.model_type = model_type
        self._usage = UsageStats(is_actual_usage=False, provenance="SIMULATED")

    def _latency_ms(self, prompt: str, role_hint: str) -> float:
        base = 180 if self.model_type == ModelType.SLM else 900
        jitter = _stable_int(f"{role_hint}:{prompt[:80]}", 400)
        multiplier = 1.0 if self.model_type == ModelType.SLM else 1.8
        return round((base + jitter) * multiplier, 1)

    def _confidence(self, prompt: str, metadata: dict[str, Any] | None) -> float:
        metadata = metadata or {}
        if "force_confidence" in metadata:
            return float(metadata["force_confidence"])
        if self.model_type == ModelType.FRONTIER:
            return 0.94
        # Intentionally low for ambiguous LAPTOP-9910 cascade scenario
        if "9910" in prompt or metadata.get("device_id") == "LAPTOP-9910":
            if metadata.get("task") in {"initial_diagnosis", "diagnose", "cascade"}:
                return 0.54
        if metadata.get("complexity") == "complex":
            return 0.61
        if metadata.get("task") == "rag_generation":
            return 0.91
        return 0.92 + (_stable_int(prompt, 40) / 1000.0)

    def _build_usage(self, prompt: str, output: str, latency_ms: float) -> UsageStats:
        input_tokens = _estimate_tokens(prompt)
        # Frontier tends to produce richer outputs in demos
        output_tokens = _estimate_tokens(output)
        if self.model_type == ModelType.FRONTIER:
            input_tokens = int(input_tokens * 1.8) + 120
            output_tokens = int(output_tokens * 1.6) + 80
        usage = UsageStats(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            latency_ms=latency_ms,
            is_actual_usage=False,
            provenance="SIMULATED",
        )
        self._usage = usage
        return usage

    def health_check(self) -> dict[str, Any]:
        return {
            "healthy": True,
            "provider": self.provider,
            "model": self.model_name,
            "model_type": self.model_type.value,
            "mode": "DEMO",
        }

    def get_usage(self) -> UsageStats:
        return self._usage


class DemoSLMClient(_DemoBase):
    def __init__(self, model_name: str = "demo-slm"):
        super().__init__(model_name=model_name, provider="demo", model_type=ModelType.SLM)

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 800,
        metadata: dict[str, Any] | None = None,
    ) -> GenerationResult:
        metadata = metadata or {}
        task = metadata.get("task", "analysis")
        device = metadata.get("device_id", "device")
        start = time.perf_counter()
        text = self._text_for_task(task, device, prompt, metadata)
        latency = self._latency_ms(prompt, task)
        # Keep wall time tiny but include simulated latency in metrics
        _ = start
        conf = self._confidence(prompt, metadata)
        usage = self._build_usage((system or "") + prompt, text, latency)
        return GenerationResult(
            text=text,
            confidence=round(conf, 3),
            usage=usage,
            model_name=self.model_name,
            model_type=self.model_type,
            provider=self.provider,
            metadata={"mode": "DEMO", "task": task},
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
        metadata = metadata or {}
        task = metadata.get("task", "structured")
        device = metadata.get("device_id", "device")
        payload = self._structured_for_task(task, device, prompt, metadata)
        text = json.dumps(payload, indent=2)
        latency = self._latency_ms(prompt, task)
        conf = self._confidence(prompt, {**metadata, "task": task})
        usage = self._build_usage((system or "") + prompt, text, latency)
        return GenerationResult(
            text=text,
            structured=payload,
            confidence=round(conf, 3),
            usage=usage,
            model_name=self.model_name,
            model_type=self.model_type,
            provider=self.provider,
            metadata={"mode": "DEMO", "schema_keys": list(schema.keys())},
        )

    def classify(
        self,
        text: str,
        labels: list[str],
        *,
        metadata: dict[str, Any] | None = None,
    ) -> GenerationResult:
        metadata = metadata or {}
        label = labels[0]
        lowered = text.lower()
        for candidate in labels:
            if candidate.lower().replace("_", " ") in lowered:
                label = candidate
                break
        if "rca" in lowered or "ambiguous" in lowered or "cross-domain" in lowered:
            for candidate in labels:
                if "complex" in candidate.lower() or "frontier" in candidate.lower():
                    label = candidate
                    break
        payload = {"label": label, "labels": labels}
        prompt = f"Classify: {text} labels={labels}"
        latency = self._latency_ms(prompt, "classify")
        usage = self._build_usage(prompt, json.dumps(payload), latency)
        return GenerationResult(
            text=label,
            structured=payload,
            confidence=0.9 if metadata.get("complexity") != "complex" else 0.62,
            usage=usage,
            model_name=self.model_name,
            model_type=self.model_type,
            provider=self.provider,
        )

    def summarize(
        self,
        text: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> GenerationResult:
        summary = " ".join(text.split()[:40])
        if len(text.split()) > 40:
            summary += " ..."
        prompt = f"Summarize: {text}"
        latency = self._latency_ms(prompt, "summarize")
        usage = self._build_usage(prompt, summary, latency)
        return GenerationResult(
            text=summary,
            confidence=0.9,
            usage=usage,
            model_name=self.model_name,
            model_type=self.model_type,
            provider=self.provider,
        )

    def _text_for_task(
        self, task: str, device: str, prompt: str, metadata: dict[str, Any]
    ) -> str:
        if task in {"cpu", "cpu_memory"}:
            return (
                f"[SIMULATED SLM] {device}: CPU/memory pressure detected. "
                "Top consumers likely include browser and collaboration clients. "
                "Recommend closing idle apps and collecting process snapshot."
            )
        if task == "teams":
            return (
                f"[SIMULATED SLM] {device}: Teams crash count elevated. "
                "Correlate with GPU/driver and overlay conflicts; clear Teams cache."
            )
        if task in {"network", "vpn"}:
            return (
                f"[SIMULATED SLM] {device}: VPN disconnects and latency above threshold. "
                "Check Wi-Fi signal, split-tunnel policy, and gateway health."
            )
        if task == "compliance":
            return (
                f"[SIMULATED SLM] {device}: Compliance checks completed against policy rules. "
                "Flag encryption, patch age, and antivirus deviations."
            )
        if task in {"history", "incidents"}:
            return (
                f"[SIMULATED SLM] {device}: Historical incidents summarized. "
                "Recurring collaboration/network symptoms observed in prior tickets."
            )
        if task in {"initial_diagnosis", "diagnose", "cascade"}:
            return (
                f"[SIMULATED SLM] {device}: Possible Wi-Fi instability affecting Teams/VPN, "
                "but telemetry conflicts prevent a high-confidence root cause."
            )
        if task == "rag_generation":
            return (
                f"[SIMULATED SLM] Approved remediation for {device}: free disk space to >15% "
                "by clearing temp/OneDrive known folders, repair OneDrive sync, then re-check "
                "DEX score. Citations included from retrieved SOPs."
            )
        if task == "fallback":
            return (
                f"[SIMULATED SLM FALLBACK] Degraded RCA for {device}: local model continued "
                "service after Frontier unavailability. Confidence reduced."
            )
        if task == "health_classification":
            return f"[SIMULATED SLM] Routine health classification for request: {prompt[:120]}"
        return f"[SIMULATED SLM] Completed task '{task}' for {device}."

    def _structured_for_task(
        self, task: str, device: str, prompt: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        if task in {"initial_diagnosis", "diagnose", "cascade"}:
            return {
                "device_id": device,
                "hypothesis": "Intermittent Wi-Fi/packet-loss impacting Teams and VPN",
                "confidence": self._confidence(prompt, metadata),
                "conflicting_signals": [
                    "CPU normal",
                    "Memory normal",
                    "Variable Wi-Fi",
                    "Packet loss present",
                    "Multiple historical incidents",
                ],
                "recommended_next_step": "Escalate for cross-domain reasoning",
            }
        if task == "health_classification":
            return {
                "request_type": metadata.get("request_type", "cpu_status"),
                "severity": metadata.get("severity", "healthy"),
                "action": "informational",
            }
        return {"task": task, "device_id": device, "status": "ok"}


class DemoFrontierClient(_DemoBase):
    def __init__(self, model_name: str = "demo-frontier"):
        super().__init__(
            model_name=model_name, provider="demo", model_type=ModelType.FRONTIER
        )
        self._fail_mode: str | None = None

    def set_failure_mode(self, mode: str | None) -> None:
        self._fail_mode = mode

    def _maybe_fail(self) -> None:
        if not self._fail_mode:
            return
        mapping = {
            "http_503": ("Frontier service unavailable (HTTP 503)", 503),
            "timeout": ("Frontier request timed out", 408),
            "rate_limit": ("Frontier rate limit exceeded", 429),
            "auth_error": ("Frontier authentication/service error", 401),
            "offline": ("Frontier offline mode engaged", 503),
            "cost_guard": ("Frontier blocked by cost guard", 402),
        }
        message, code = mapping.get(
            self._fail_mode, ("Frontier failure", 500)
        )
        raise FrontierUnavailableError(message, code=code, failure_type=self._fail_mode)

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 800,
        metadata: dict[str, Any] | None = None,
    ) -> GenerationResult:
        self._maybe_fail()
        metadata = metadata or {}
        task = metadata.get("task", "reasoning")
        device = metadata.get("device_id", "device")
        text = self._text_for_task(task, device, prompt, metadata)
        latency = self._latency_ms(prompt, task)
        conf = self._confidence(prompt, metadata)
        usage = self._build_usage((system or "") + prompt, text, latency)
        return GenerationResult(
            text=text,
            confidence=round(conf, 3),
            usage=usage,
            model_name=self.model_name,
            model_type=self.model_type,
            provider=self.provider,
            metadata={"mode": "DEMO", "task": task},
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
        self._maybe_fail()
        metadata = metadata or {}
        task = metadata.get("task", "structured")
        device = metadata.get("device_id", "device")
        payload = self._structured_for_task(task, device, prompt, metadata)
        text = json.dumps(payload, indent=2)
        latency = self._latency_ms(prompt, task)
        usage = self._build_usage((system or "") + prompt, text, latency)
        return GenerationResult(
            text=text,
            structured=payload,
            confidence=0.94,
            usage=usage,
            model_name=self.model_name,
            model_type=self.model_type,
            provider=self.provider,
            metadata={"mode": "DEMO"},
        )

    def classify(
        self,
        text: str,
        labels: list[str],
        *,
        metadata: dict[str, Any] | None = None,
    ) -> GenerationResult:
        self._maybe_fail()
        label = labels[-1] if labels else "unknown"
        for candidate in labels:
            if "complex" in candidate.lower():
                label = candidate
                break
        prompt = f"Classify: {text}"
        payload = {"label": label}
        latency = self._latency_ms(prompt, "classify")
        usage = self._build_usage(prompt, json.dumps(payload), latency)
        return GenerationResult(
            text=label,
            structured=payload,
            confidence=0.93,
            usage=usage,
            model_name=self.model_name,
            model_type=self.model_type,
            provider=self.provider,
        )

    def summarize(
        self,
        text: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> GenerationResult:
        self._maybe_fail()
        summary = (
            "[SIMULATED FRONTIER] Synthesized summary with cross-domain correlation: "
            + " ".join(text.split()[:60])
        )
        prompt = f"Summarize: {text}"
        latency = self._latency_ms(prompt, "summarize")
        usage = self._build_usage(prompt, summary, latency)
        return GenerationResult(
            text=summary,
            confidence=0.95,
            usage=usage,
            model_name=self.model_name,
            model_type=self.model_type,
            provider=self.provider,
        )

    def _text_for_task(
        self, task: str, device: str, prompt: str, metadata: dict[str, Any]
    ) -> str:
        if task in {"planner", "planning"}:
            return (
                f"[SIMULATED FRONTIER PLANNER] Investigation plan for {device}: "
                "1) CPU/memory worker 2) Teams worker 3) Network/VPN worker "
                "4) Compliance worker 5) History worker 6) Cross-domain RCA synthesis."
            )
        if task in {"rca_synthesis", "synthesis", "complex_rca"}:
            return (
                f"[SIMULATED FRONTIER RCA] {device}: Root cause is compounded resource "
                "contention plus unstable VPN path amplifying Teams instability. "
                "Prioritize process remediation, network path repair, then validate UX."
            )
        if task in {"cascade", "escalated_rca"}:
            return (
                f"[SIMULATED FRONTIER ESCALATION] {device}: Conflicting telemetry resolved. "
                "Primary cause is intermittent packet loss on Wi-Fi roaming events that "
                "destabilize VPN tunnels and trigger Teams media failures."
            )
        return f"[SIMULATED FRONTIER] Advanced reasoning completed for task '{task}' on {device}."

    def _structured_for_task(
        self, task: str, device: str, prompt: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        if task in {"planner", "planning"}:
            return {
                "device_id": device,
                "objective": "Complete multi-domain RCA",
                "workers": ["cpu", "teams", "network", "compliance", "history"],
                "synthesis_required": True,
            }
        if task in {"rca_synthesis", "synthesis", "complex_rca", "cascade", "escalated_rca"}:
            return {
                "device_id": device,
                "root_cause": "Cross-domain resource and network interaction",
                "confidence": 0.94,
                "actions": [
                    "Collect process dump during CPU spike",
                    "Reset VPN profile and validate gateway",
                    "Clear Teams cache and update client",
                    "Review historical recurrence pattern",
                ],
            }
        return {"task": task, "device_id": device, "status": "ok"}


class FrontierUnavailableError(RuntimeError):
    def __init__(self, message: str, *, code: int, failure_type: str):
        super().__init__(message)
        self.code = code
        self.failure_type = failure_type
