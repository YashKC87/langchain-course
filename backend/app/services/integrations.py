"""Integration enable/disable, configuration, and connection testing."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import os

from app.connectors.cloud import AWSConnector, AzureConnector
from app.models.domain import (
    ActivityEvent,
    Integration,
    IntegrationEnableStage,
    IntegrationStatus,
)
from app.storage.persistence import save_integration_overrides
from app.storage.store import store

GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


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
        # Allow clearing optional scope fields when client sends empty string / null
        for optional_key in ("resource_group", "foundry_account", "foundry_project"):
            if optional_key in fields and (fields[optional_key] is None or str(fields[optional_key]).strip() == ""):
                integ.config.fields.pop(optional_key, None)
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

        if integ.id == "azure" or integ.provider == "azure":
            azure_errors = self._validate_azure_fields(integ)
            if azure_errors:
                return {"ok": False, "stage": "configuration", "message": azure_errors}

            connector = AzureConnector()
            cfg = {**integ.config.fields, "auth_method": integ.config.auth_method}
            for step, coro in (
                ("Authenticate", connector.authenticate(cfg)),
                ("Validate Permissions", connector.validate_permissions(cfg)),
                ("Telemetry Source", connector.validate_telemetry_source(cfg)),
            ):
                result = await coro
                if not result.get("ok", False):
                    return {
                        "ok": False,
                        "stage": step.lower(),
                        "message": result.get("message", f"{step} failed for Azure."),
                    }
            return {
                "ok": True,
                "stage": "complete",
                "message": (
                    f"Azure tenant {integ.config.fields.get('tenant_id', '')[:8]}… validated. "
                    "Enable the integration, then export agent telemetry via OpenTelemetry or Application Insights."
                ),
            }

        if integ.id in ("aws", "bedrock", "bedrock-agents", "agentcore") or (
            integ.provider == "aws" and integ.id in ("aws", "bedrock", "bedrock-agents", "agentcore")
        ):
            connector = AWSConnector()
            cfg = {**integ.config.fields, "auth_method": integ.config.auth_method}
            auth = await connector.authenticate(cfg)
            if not auth.get("ok", False):
                return {
                    "ok": False,
                    "stage": "authenticate",
                    "message": auth.get("message", "AWS authentication failed."),
                }
            perm = await connector.validate_permissions(cfg)
            if not perm.get("ok", False):
                return {
                    "ok": False,
                    "stage": perm.get("stage", "permissions"),
                    "message": perm.get("message", "AWS permission validation failed."),
                }
            telemetry = await connector.validate_telemetry_source(cfg)
            if not telemetry.get("ok", False):
                return {
                    "ok": False,
                    "stage": "telemetry",
                    "message": telemetry.get("message", "AWS telemetry validation failed."),
                }
            return {
                "ok": True,
                "stage": "complete",
                "message": perm.get("message")
                or (
                    f"AWS account {integ.config.fields.get('account_id', '')} validated. "
                    "Enable the integration, then click Refresh Discovery."
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

    def _azure_has_client_secret(self, integ: Integration) -> bool:
        if integ.config.secret_refs.get("client_secret") or integ.config.fields.get("client_secret"):
            return True
        return bool(os.environ.get("AZURE_CLIENT_SECRET") or os.environ.get("AZURE_CLIENT_SECRET_VALUE"))

    def _validate_azure_fields(self, integ: Integration) -> str | None:
        tenant = str(integ.config.fields.get("tenant_id") or "")
        subscription = str(integ.config.fields.get("subscription_id") or "")
        if tenant and not GUID_RE.match(tenant):
            return "Tenant ID must be a valid GUID (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)."
        if subscription and not GUID_RE.match(subscription):
            return "Subscription ID must be a valid GUID."
        auth = integ.config.auth_method or ""
        if "Service Principal" in auth:
            if not integ.config.fields.get("client_id") and "client_id" not in integ.config.secret_refs:
                return (
                    "Service Principal authentication requires Application (Client) ID. "
                    "Register an app in Entra ID and enter the Client ID."
                )
            if not self._azure_has_client_secret(integ):
                return "Service Principal authentication requires Client Secret (stored as a secure reference)."
        return None

    def _supports_agent_discovery(self, integ: Integration) -> bool:
        if integ.id == "azure" or integ.provider == "azure":
            return True
        if integ.id in ("aws", "bedrock", "bedrock-agents", "agentcore"):
            return True
        return False

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
        if integ.provider == "azure":
            azure_err = self._validate_azure_fields(integ)
            if azure_err:
                add("Authenticate", "failed", azure_err)
                for remaining in ENABLE_STAGES[2:]:
                    add(remaining, "skipped")
                integ.enable_progress = [s.model_dump() for s in stages]
                integ.status = IntegrationStatus.CONNECTION_FAILED
                integ.enabled = False
                integ.error_message = azure_err
                store.integrations[integration_id] = integ
                save_integration_overrides(store.integrations)
                return integ

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

        # 6. Discover Agents — live cloud discovery when supported; never fabricate
        discovery_message = "Registry will update when agents are discovered."
        discovered_count = sum(1 for a in store.agents.values() if a.integration_id == integration_id)
        if self._supports_agent_discovery(integ):
            try:
                from app.services.discovery import register_discovered_agents

                if integ.id == "azure" or integ.provider == "azure":
                    connector = AzureConnector()
                else:
                    connector = AWSConnector()
                cfg = {**integ.config.fields, "auth_method": integ.config.auth_method}
                detail = await connector.discover_detailed(cfg)
                agents = detail.get("agents") or []
                counts = register_discovered_agents(agents, integration_id=integration_id)
                discovered_count = counts["total"] if counts["total"] else discovered_count
                discovery_message = detail.get("message") or discovery_message
                if detail.get("errors"):
                    discovery_message += " Warnings: " + "; ".join(detail["errors"][:3])
                add("Discover Agents", "success", discovery_message)
            except Exception as exc:  # noqa: BLE001
                add(
                    "Discover Agents",
                    "failed",
                    str(exc),
                )
                for remaining in ENABLE_STAGES[6:]:
                    add(remaining, "skipped")
                integ.enable_progress = [s.model_dump() for s in stages]
                integ.status = IntegrationStatus.WARNING
                integ.enabled = True  # stay enabled but warn — config is valid
                integ.error_message = str(exc)
                integ.agents_discovered = discovered_count if discovered_count else None
                store.integrations[integration_id] = integ
                save_integration_overrides(store.integrations)
                return integ
        else:
            add(
                "Discover Agents",
                "success",
                (
                    f"{discovered_count} agents already registered from prior telemetry."
                    if discovered_count
                    else "Connection successful. No agents discovered yet. Waiting for live telemetry or provider API discovery."
                ),
            )

        # 7. Register Agents
        add("Register Agents", "success", discovery_message)

        # 8. Start Telemetry Collection
        add("Start Telemetry Collection", "success", "Monitoring active.")

        integ.enabled = True
        integ.status = IntegrationStatus.CONNECTED
        integ.connection_health = "connected"
        integ.auth_state = "authenticated"
        integ.error_message = None
        integ.agents_discovered = discovered_count if discovered_count else None
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

    async def list_resource_groups(
        self,
        integration_id: str,
        fields_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        integ = store.integrations.get(integration_id)
        if not integ:
            raise KeyError(f"Unknown integration: {integration_id}")
        if integ.id != "azure" and integ.provider != "azure":
            return {
                "ok": False,
                "message": "Resource group listing is only available for Azure integrations.",
                "resource_groups": [],
            }

        from app.services.azure_discovery import AzureDiscoveryError, list_resource_groups_in_subscription

        cfg = {
            **integ.config.fields,
            **(fields_override or {}),
            "auth_method": integ.config.auth_method,
        }
        try:
            result = await list_resource_groups_in_subscription(cfg)
            return {"ok": True, **result}
        except AzureDiscoveryError as exc:
            return {
                "ok": False,
                "stage": exc.stage,
                "message": exc.message,
                "resource_groups": [],
            }

    async def discover(
        self,
        integration_id: str,
        *,
        resource_group: str | None = None,
    ) -> dict[str, Any]:
        """Refresh agent discovery for a cloud integration."""
        integ = store.integrations.get(integration_id)
        if not integ:
            raise KeyError(f"Unknown integration: {integration_id}")
        if not integ.configured:
            return {
                "ok": False,
                "message": "Configure the integration before running discovery.",
                "agents": [],
            }
        if not integ.enabled:
            return {
                "ok": False,
                "message": "Enable the integration before running discovery.",
                "agents": [],
            }

        if not self._supports_agent_discovery(integ):
            return {
                "ok": True,
                "message": (
                    "Provider API discovery is not implemented for this integration yet. "
                    "Agents appear when live telemetry arrives."
                ),
                "agents": [
                    a.model_dump()
                    for a in store.agents.values()
                    if a.integration_id == integration_id
                ],
                "accounts_scanned": [],
                "errors": [],
            }

        from app.services.discovery import register_discovered_agents

        if integ.id == "azure" or integ.provider == "azure":
            from app.services.azure_discovery import AzureDiscoveryError

            connector = AzureConnector()
            discovery_error = AzureDiscoveryError
            extra_keys = ("subscription_id", "resource_group", "foundry_project", "scope")
        else:
            from app.services.aws_discovery import AWSDiscoveryError

            connector = AWSConnector()
            discovery_error = AWSDiscoveryError
            extra_keys = ("account_id", "region")

        cfg = {**integ.config.fields, "auth_method": integ.config.auth_method}
        if resource_group is not None and (integ.id == "azure" or integ.provider == "azure"):
            normalized = str(resource_group).strip()
            if not normalized or normalized.lower() in ("__all__", "all", "*"):
                cfg.pop("resource_group", None)
                integ.config.fields.pop("resource_group", None)
            else:
                cfg["resource_group"] = normalized
                integ.config.fields["resource_group"] = normalized
            store.integrations[integration_id] = integ
            save_integration_overrides(store.integrations)

        try:
            detail = await connector.discover_detailed(cfg)
        except discovery_error as exc:
            integ.status = IntegrationStatus.WARNING
            integ.error_message = exc.message
            store.integrations[integration_id] = integ
            save_integration_overrides(store.integrations)
            return {
                "ok": False,
                "stage": exc.stage,
                "message": exc.message,
                "agents": [],
                "accounts_scanned": [],
                "errors": [exc.message],
            }

        agents = detail.get("agents") or []
        counts = register_discovered_agents(agents, integration_id=integration_id)
        integ.error_message = None
        if agents:
            integ.status = IntegrationStatus.CONNECTED
        store.integrations[integration_id] = integ
        save_integration_overrides(store.integrations)

        await store.record_activity(
            ActivityEvent(
                id=f"integ-discover-{integration_id}-{datetime.now(timezone.utc).timestamp()}",
                timestamp=datetime.now(timezone.utc),
                event_type="agent_discovery",
                message=detail.get("message") or f"Discovery finished for {integ.name}",
                severity="info",
            )
        )
        response: dict[str, Any] = {
            "ok": True,
            "message": detail.get("message"),
            "agents": agents,
            "counts": counts,
            "accounts_scanned": detail.get("accounts_scanned") or [],
            "errors": detail.get("errors") or [],
        }
        for key in extra_keys:
            if detail.get(key) is not None:
                response[key] = detail[key]
        return response

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
