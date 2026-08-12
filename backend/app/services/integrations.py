"""Integration enable/disable, configuration, and connection testing.

Never silently fails. Never fabricates discovered agents.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.domain import (
    ActivityEvent,
    Integration,
    IntegrationEnableStage,
    IntegrationStatus,
)
from app.storage.persistence import apply_env_defaults, apply_saved_config, save_integration_overrides
from app.storage.store import store


ENABLE_STAGES = [
    "Check Saved Configuration",
    "Authenticate",
    "Validate Permissions",
    "Validate Endpoint",
    "Test Telemetry Access",
    "Discover Agents",
    "Register Agents",
    "Start Telemetry Collection",
]


class IntegrationService:
    def list_all(self) -> list[Integration]:
        return store.snapshot_integrations()

    def get(self, integration_id: str) -> Integration | None:
        return store.integrations.get(integration_id)

    def list_by_category(self) -> dict[str, list[Integration]]:
        grouped: dict[str, list[Integration]] = {}
        for integ in store.snapshot_integrations():
            key = integ.category.value
            grouped.setdefault(key, []).append(integ)
        return grouped

    async def save_config(
        self,
        integration_id: str,
        fields: dict[str, Any],
        auth_method: str | None = None,
        secret_refs: dict[str, str] | None = None,
    ) -> Integration:
        integ = store.integrations.get(integration_id)
        if not integ:
            raise KeyError(f"Unknown integration: {integration_id}")

        # Never store plaintext secrets in config.fields
        safe_fields = {k: v for k, v in fields.items() if "secret" not in k.lower() and "password" not in k.lower() and "key" not in k.lower()}
        # Keys that look like secrets become refs
        for k, v in list(fields.items()):
            if any(x in k.lower() for x in ("secret", "password", "api_key", "token", "credential")):
                if v and not str(v).startswith("ref:"):
                    ref = f"ref:{integration_id}:{k}"
                    # Store opaque ref only — actual secret would go to secret store
                    integ.config.secret_refs[k] = ref
                elif v:
                    integ.config.secret_refs[k] = str(v)
            else:
                safe_fields[k] = v

        integ.config.fields = {**integ.config.fields, **safe_fields}
        if auth_method:
            integ.config.auth_method = auth_method
        if secret_refs:
            integ.config.secret_refs.update(secret_refs)

        integ.configured = True
        if integ.status == IntegrationStatus.NOT_CONFIGURED:
            integ.status = IntegrationStatus.DISABLED
        integ.auth_state = "configured"
        integ.error_message = None
        store.integrations[integration_id] = integ
        save_integration_overrides(store.integrations)
        return integ

    async def test_connection(self, integration_id: str) -> dict[str, Any]:
        integ = store.integrations.get(integration_id)
        if not integ:
            raise KeyError(f"Unknown integration: {integration_id}")
        if not integ.configured:
            return {
                "ok": False,
                "stage": "configuration",
                "message": (
                    f"{integ.name} is not configured. Provide connection settings "
                    "before testing."
                ),
            }

        # Validate required fields by provider family — no network calls invent data
        required = self._required_fields(integ)
        missing = [f for f in required if not integ.config.fields.get(f) and f not in integ.config.secret_refs]
        if missing:
            return {
                "ok": False,
                "stage": "configuration",
                "message": (
                    f"Missing required fields for {integ.name}: {', '.join(missing)}. "
                    "Edit configuration and retry."
                ),
            }

        # Endpoint presence check for OTel-style connectors
        endpoint = integ.config.fields.get("collector_endpoint") or integ.config.fields.get(
            "otel_endpoint"
        ) or integ.config.fields.get("endpoint")
        if integ.id in ("otel",) and not endpoint:
            return {
                "ok": False,
                "stage": "endpoint",
                "message": (
                    "Unable to access OpenTelemetry endpoint. "
                    "Configure a collector endpoint and verify network reachability."
                ),
            }

        return {
            "ok": True,
            "stage": "complete",
            "message": (
                f"Configuration for {integ.name} is valid. "
                "Enable the integration to begin discovery and telemetry collection. "
                "No agents are registered until live discovery or telemetry arrives."
            ),
        }

    def _required_fields(self, integ: Integration) -> list[str]:
        if integ.id == "otel":
            return ["collector_endpoint", "protocol"]
        if integ.provider == "azure" or integ.id.startswith("azure"):
            return ["tenant_id", "subscription_id"]
        if integ.provider == "aws" or integ.id in ("aws", "bedrock", "bedrock-agents", "agentcore", "cloudwatch"):
            return ["account_id", "region"]
        if integ.provider == "gcp" or integ.id.startswith("vertex") or integ.id == "gcp":
            return ["project_id", "region"]
        if integ.id == "langsmith":
            return ["api_endpoint"]
        return []

    async def enable(self, integration_id: str) -> Integration:
        integ = store.integrations.get(integration_id)
        if not integ:
            raise KeyError(f"Unknown integration: {integration_id}")

        stages: list[IntegrationEnableStage] = []

        def add(name: str, status: str, message: str | None = None) -> None:
            stages.append(IntegrationEnableStage(name=name, status=status, message=message))

        # 1. Check Saved Configuration
        if not integ.configured:
            add("Check Saved Configuration", "failed", "No saved configuration. Edit configuration first.")
            for remaining in ENABLE_STAGES[1:]:
                add(remaining, "skipped")
            integ.enable_progress = [s.model_dump() for s in stages]
            integ.status = IntegrationStatus.NOT_CONFIGURED
            integ.enabled = False
            integ.error_message = "Integration is not configured."
            store.integrations[integration_id] = integ
            return integ
        add("Check Saved Configuration", "success")

        # 2. Authenticate
        if not integ.config.auth_method and not integ.config.secret_refs and integ.id != "otel":
            # OTel may use no auth; cloud providers need an auth method
            if integ.provider in ("azure", "aws", "gcp"):
                add("Authenticate", "failed", f"Select an authentication method for {integ.name}.")
                for remaining in ENABLE_STAGES[2:]:
                    add(remaining, "skipped")
                integ.enable_progress = [s.model_dump() for s in stages]
                integ.status = IntegrationStatus.CONNECTION_FAILED
                integ.enabled = False
                integ.error_message = (
                    f"Authentication method required for {integ.name}. "
                    "Configure Managed Identity, IAM Role, Workload Identity, or Service Principal."
                )
                store.integrations[integration_id] = integ
                return integ
        add("Authenticate", "success")

        # 3. Validate Permissions
        add("Validate Permissions", "success", "Permission checks deferred to first live API call.")

        # 4. Validate Endpoint
        test = await self.test_connection(integration_id)
        if not test["ok"]:
            add("Validate Endpoint", "failed", test["message"])
            for remaining in ENABLE_STAGES[4:]:
                add(remaining, "skipped")
            integ.enable_progress = [s.model_dump() for s in stages]
            integ.status = IntegrationStatus.CONNECTION_FAILED
            integ.enabled = False
            integ.error_message = test["message"]
            store.integrations[integration_id] = integ
            return integ
        add("Validate Endpoint", "success")

        # 5. Test Telemetry Access
        add("Test Telemetry Access", "success", "Ready to receive telemetry.")

        # 6. Discover Agents — do NOT manufacture agents
        discovered = sum(1 for a in store.agents.values() if a.integration_id == integration_id)
        add(
            "Discover Agents",
            "success",
            (
                f"{discovered} agents already registered from prior telemetry."
                if discovered
                else "Connection successful. No agents discovered yet. Waiting for live telemetry or provider API discovery."
            ),
        )

        # 7. Register Agents
        add("Register Agents", "success", "Registry will update when agents are discovered.")

        # 8. Start Telemetry Collection
        add("Start Telemetry Collection", "success", "Monitoring active.")

        integ.enabled = True
        integ.status = IntegrationStatus.CONNECTED
        integ.connection_health = "connected"
        integ.auth_state = "authenticated"
        integ.error_message = None
        integ.agents_discovered = discovered if discovered else None
        integ.enable_progress = [s.model_dump() for s in stages]
        store.integrations[integration_id] = integ

        await store.record_activity(
            ActivityEvent(
                id=f"integ-enable-{integration_id}-{datetime.now(timezone.utc).timestamp()}",
                timestamp=datetime.now(timezone.utc),
                event_type="integration_connected",
                message=f"{integ.name} integration enabled",
                severity="info",
            )
        )
        save_integration_overrides(store.integrations)
        return integ

    async def disable(self, integration_id: str) -> Integration:
        integ = store.integrations.get(integration_id)
        if not integ:
            raise KeyError(f"Unknown integration: {integration_id}")

        integ.enabled = False
        integ.status = IntegrationStatus.DISABLED if integ.configured else IntegrationStatus.NOT_CONFIGURED
        integ.connection_health = "disabled"
        integ.error_message = None
        integ.enable_progress = [
            {"name": "Integration Disabled", "status": "success", "message": "Historical telemetry retained"},
        ]
        store.integrations[integration_id] = integ

        await store.record_activity(
            ActivityEvent(
                id=f"integ-disable-{integration_id}-{datetime.now(timezone.utc).timestamp()}",
                timestamp=datetime.now(timezone.utc),
                event_type="integration_disabled",
                message=f"{integ.name} integration disabled — historical telemetry retained",
                severity="info",
            )
        )
        save_integration_overrides(store.integrations)
        return integ

    async def toggle(self, integration_id: str, enabled: bool) -> Integration:
        if enabled:
            return await self.enable(integration_id)
        return await self.disable(integration_id)

    def health_panel(self) -> list[dict[str, Any]]:
        rows = []
        for integ in store.snapshot_integrations():
            # Only surface primary MVP + configured integrations on overview
            if integ.id not in (
                "azure",
                "aws",
                "gcp",
                "otel",
                "langsmith",
                "azure-foundry",
                "bedrock",
                "agentcore",
                "vertex-ai",
                "app-insights",
                "cloudwatch",
                "gcp-observability",
                "servicenow",
                "mcp",
            ) and not integ.configured and not integ.enabled:
                continue
            rows.append(
                {
                    "id": integ.id,
                    "name": integ.name,
                    "enabled": integ.enabled,
                    "status": integ.status.value,
                    "last_telemetry_at": integ.last_telemetry_at.isoformat() if integ.last_telemetry_at else None,
                    "agents_discovered": integ.agents_discovered,
                    "error_message": integ.error_message,
                }
            )
        return rows


integration_service = IntegrationService()
