"""Tool plugin/adapter layer — contracts enforced for every production tool."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional
import hashlib
import json
import time
import uuid


class AuthMethod(str, Enum):
    MANAGED_IDENTITY = "managed_identity"
    OAUTH_CLIENT_CREDENTIALS = "oauth_client_credentials"
    KEY_VAULT_SECRET = "key_vault_secret"
    NONE_LOCAL = "none_local"


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    backoff_seconds: float = 1.0
    retry_on: tuple[str, ...] = ("TIMEOUT", "THROTTLED", "TRANSIENT")


@dataclass
class ToolContract:
    name: str
    purpose: str
    required_input: list[str]
    optional_input: list[str]
    authentication: AuthMethod
    timeout_seconds: int
    retry_policy: RetryPolicy
    allowed_roles: list[str]
    expected_output: str
    error_response: str
    audit_requirements: str
    idempotency: str
    production_restrictions: str


@dataclass
class ToolResult:
    ok: bool
    tool: str
    data: dict[str, Any] = field(default_factory=dict)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: int = 0
    correlation_id: str = ""
    data_mode: str = "live"  # live | mock | unavailable
    missing_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BaseTool(ABC):
    contract: ToolContract

    def __init__(self, audit_sink: Optional[Callable[[dict], None]] = None):
        self._audit_sink = audit_sink or (lambda _: None)

    def validate_input(self, payload: dict[str, Any]) -> None:
        missing = [k for k in self.contract.required_input if k not in payload or payload[k] in (None, "")]
        if missing:
            raise ValueError(f"{self.contract.name}: missing required input: {missing}")

    def run(self, payload: dict[str, Any], *, actor_roles: list[str], correlation_id: str) -> ToolResult:
        started = time.perf_counter()
        if not set(actor_roles) & set(self.contract.allowed_roles):
            result = ToolResult(
                ok=False,
                tool=self.contract.name,
                error_code="FORBIDDEN",
                error_message="Caller role not authorized for this tool",
                correlation_id=correlation_id,
            )
            self._emit_audit(payload, result, actor_roles)
            return result

        try:
            self.validate_input(payload)
            result = self.execute(payload, correlation_id=correlation_id)
        except ValueError as exc:
            result = ToolResult(
                ok=False,
                tool=self.contract.name,
                error_code="INVALID_INPUT",
                error_message=str(exc),
                correlation_id=correlation_id,
            )
        except TimeoutError as exc:
            result = ToolResult(
                ok=False,
                tool=self.contract.name,
                error_code="TIMEOUT",
                error_message=str(exc),
                correlation_id=correlation_id,
            )
        except Exception as exc:  # noqa: BLE001 — surfaced as structured tool error
            result = ToolResult(
                ok=False,
                tool=self.contract.name,
                error_code="TOOL_FAILURE",
                error_message=str(exc),
                correlation_id=correlation_id,
            )

        result.duration_ms = int((time.perf_counter() - started) * 1000)
        result.correlation_id = correlation_id
        self._emit_audit(payload, result, actor_roles)
        return result

    @abstractmethod
    def execute(self, payload: dict[str, Any], *, correlation_id: str) -> ToolResult:
        raise NotImplementedError

    def _emit_audit(self, payload: dict[str, Any], result: ToolResult, actor_roles: list[str]) -> None:
        safe_payload = {k: ("***" if "secret" in k.lower() or "password" in k.lower() else v) for k, v in payload.items()}
        self._audit_sink(
            {
                "event_type": "tool_invocation",
                "tool": self.contract.name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "correlation_id": result.correlation_id,
                "actor_roles": actor_roles,
                "ok": result.ok,
                "error_code": result.error_code,
                "duration_ms": result.duration_ms,
                "input_keys": list(safe_payload.keys()),
                "data_mode": result.data_mode,
            }
        )


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.contract.name] = tool

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"Tool not registered: {name}")
        return self._tools[name]

    def list_tools(self) -> list[str]:
        return sorted(self._tools)

    def invoke(
        self,
        name: str,
        payload: dict[str, Any],
        *,
        actor_roles: list[str],
        correlation_id: Optional[str] = None,
    ) -> ToolResult:
        cid = correlation_id or str(uuid.uuid4())
        return self.get(name).run(payload, actor_roles=actor_roles, correlation_id=cid)


def idempotency_key(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def compact_json(data: dict[str, Any]) -> str:
    return json.dumps(data, separators=(",", ":"), default=str)
