"""Generic OpenTelemetry connector."""

from __future__ import annotations

from typing import Any

from app.connectors.base import BaseConnector


class OpenTelemetryConnector(BaseConnector):
    id = "otel"
    name = "OpenTelemetry"
    provider = "otel"

    async def authenticate(self, config: dict[str, Any]) -> dict[str, Any]:
        # OTel often needs no auth; headers optional
        return {"ok": True, "message": "OpenTelemetry authentication configuration accepted."}

    async def validate_permissions(self, config: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "message": "No provider ACL check required for push-based OTLP."}

    async def validate_telemetry_source(self, config: dict[str, Any]) -> dict[str, Any]:
        endpoint = config.get("collector_endpoint") or config.get("otel_endpoint")
        if not endpoint:
            return {
                "ok": False,
                "message": (
                    "Unable to access OpenTelemetry endpoint. "
                    "Configure a collector endpoint and verify network reachability."
                ),
            }
        return {"ok": True, "message": f"Endpoint configured: {endpoint}"}

    async def discover_agents(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        # Agents are discovered from ingested telemetry, not invented here.
        return []

    async def fetch_telemetry(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        # Push model — Control Center receives OTLP; nothing to poll by default.
        return []
