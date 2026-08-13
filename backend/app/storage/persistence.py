"""Persist integration configuration to disk (secrets as refs only)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.models.domain import Integration, IntegrationConfig, IntegrationStatus


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _data_dir() -> Path:
    path = Path(os.environ.get("CONTROL_CENTER_DATA_DIR", "./data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _config_path() -> Path:
    return _data_dir() / "integrations.json"


def load_integration_overrides() -> dict[str, dict[str, Any]]:
    path = _config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_integration_overrides(integrations: dict[str, Integration]) -> None:
    payload: dict[str, Any] = {}
    for iid, integ in integrations.items():
        payload[iid] = {
            "enabled": integ.enabled,
            "configured": integ.configured,
            "status": integ.status.value,
            "config": {
                "fields": integ.config.fields,
                "secret_refs": {k: "••••••••" for k in integ.config.secret_refs},
                "auth_method": integ.config.auth_method,
            },
            "error_message": integ.error_message,
            "agents_discovered": integ.agents_discovered,
        }
    _config_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")


def apply_saved_config(integrations: dict[str, Integration]) -> None:
    saved = load_integration_overrides()
    for iid, data in saved.items():
        integ = integrations.get(iid)
        if not integ or not isinstance(data, dict):
            continue
        cfg = data.get("config") or {}
        integ.config = IntegrationConfig(
            fields=dict(cfg.get("fields") or {}),
            secret_refs={},  # refs re-created on save; never reload secrets from disk
            auth_method=cfg.get("auth_method"),
        )
        integ.configured = bool(data.get("configured"))
        integ.enabled = bool(data.get("enabled"))
        try:
            integ.status = IntegrationStatus(data.get("status", "not_configured"))
        except ValueError:
            integ.status = IntegrationStatus.NOT_CONFIGURED
        integ.error_message = data.get("error_message")
        agents = data.get("agents_discovered")
        integ.agents_discovered = agents if agents is not None else None


def _azure_resource_fields_from_env() -> dict[str, str]:
    mapping = {
        "resource_group": "AZURE_RESOURCE_GROUP",
        "foundry_project": "AZURE_FOUNDRY_PROJECT",
        "app_insights": "AZURE_APP_INSIGHTS",
        "log_analytics": "AZURE_LOG_ANALYTICS",
        "client_id": "AZURE_CLIENT_ID",
        "otel_endpoint": "OTEL_EXPORTER_OTLP_ENDPOINT",
    }
    out: dict[str, str] = {}
    for field, env_key in mapping.items():
        val = os.environ.get(env_key)
        if val:
            out[field] = val
    return out


def _apply_azure_secret_refs_from_env(azure: Integration) -> None:
    """Restore Service Principal secret refs from env — secrets are never persisted to disk."""
    if not os.environ.get("AZURE_CLIENT_SECRET") and not os.environ.get("AZURE_CLIENT_SECRET_VALUE"):
        return
    auth = (azure.config.auth_method or os.environ.get("AZURE_AUTH_METHOD") or "").lower()
    if "service principal" in auth or azure.config.fields.get("client_id"):
        azure.config.secret_refs.setdefault("client_secret", "ref:azure:client_secret")


def apply_env_defaults(integrations: dict[str, Integration]) -> None:
    """Pre-fill Azure/AWS/GCP from environment when not already configured.

    Azure resource names from env are always merged when present so local
    .env can set rg/project/App Insights without wiping tenant/subscription.
    """
    azure = integrations.get("azure")
    if azure:
        resource_fields = _azure_resource_fields_from_env()
        tenant = os.environ.get("AZURE_TENANT_ID")
        subscription = os.environ.get("AZURE_SUBSCRIPTION_ID")
        if tenant and subscription and not azure.configured:
            azure.config.fields = {
                "tenant_id": tenant,
                "subscription_id": subscription,
                **resource_fields,
            }
            azure.config.auth_method = os.environ.get("AZURE_AUTH_METHOD", "Managed Identity")
            if os.environ.get("AZURE_CLIENT_SECRET") or os.environ.get("AZURE_CLIENT_SECRET_VALUE"):
                azure.config.secret_refs["client_secret"] = "ref:azure:client_secret"
            azure.configured = True
            azure.status = IntegrationStatus.DISABLED
            azure.auth_state = "configured_from_env"
        elif resource_fields:
            # Merge resource names without clearing existing tenant/subscription.
            # Saved resource_group from disk/UI wins over .env on restart.
            saved_azure = load_integration_overrides().get("azure") or {}
            saved_fields = (saved_azure.get("config") or {}).get("fields") or {}
            merged = dict(azure.config.fields)
            for key, val in resource_fields.items():
                if key == "resource_group":
                    if merged.get("resource_group"):
                        continue
                    # User cleared RG in UI — do not re-inject from .env on restart.
                    if azure.configured and "resource_group" not in saved_fields:
                        continue
                merged[key] = val
            azure.config.fields = merged
            if os.environ.get("AZURE_AUTH_METHOD") and not azure.config.auth_method:
                azure.config.auth_method = os.environ["AZURE_AUTH_METHOD"]
            if azure.config.fields.get("tenant_id") and azure.config.fields.get("subscription_id"):
                azure.configured = True
                if azure.status == IntegrationStatus.NOT_CONFIGURED:
                    azure.status = IntegrationStatus.DISABLED
                azure.auth_state = azure.auth_state or "configured_from_env"

        _apply_azure_secret_refs_from_env(azure)

    aws = integrations.get("aws")
    if aws and not aws.configured:
        account = os.environ.get("AWS_ACCOUNT_ID")
        region = os.environ.get("AWS_REGION")
        if account and region:
            aws.config.fields = {"account_id": account, "region": region}
            aws.config.auth_method = os.environ.get("AWS_AUTH_METHOD", "IAM Role")
            aws.configured = True
            aws.status = IntegrationStatus.DISABLED

    gcp = integrations.get("gcp")
    if gcp and not gcp.configured:
        project = os.environ.get("GCP_PROJECT_ID")
        if project:
            gcp.config.fields = {
                "project_id": project,
                "region": os.environ.get("GCP_REGION", "us-central1"),
            }
            gcp.config.auth_method = os.environ.get("GCP_AUTH_METHOD", "Workload Identity")
            gcp.configured = True
            gcp.status = IntegrationStatus.DISABLED

    ingest_url = os.environ.get("CONTROL_CENTER_INGEST_URL")
    if ingest_url and azure:
        merged = dict(azure.config.fields)
        merged["otel_endpoint"] = ingest_url
        azure.config.fields = merged

    otel = integrations.get("otel")
    if otel and not otel.configured:
        auto = _truthy_env("TELEMETRY_AUTO_ENABLE")
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        if not endpoint and auto:
            endpoint = os.environ.get(
                "OTEL_COLLECTOR_ENDPOINT", "http://localhost:4318"
            )
        if endpoint:
            otel.config.fields = {
                "collector_endpoint": endpoint,
                "protocol": os.environ.get(
                    "OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf"
                ),
            }
            otel.config.auth_method = "None"
            otel.configured = True
            otel.status = IntegrationStatus.DISABLED


def auto_enable_integrations(integrations: dict[str, Integration]) -> list[str]:
    """Enable configured telemetry integrations when env flags request it."""
    enabled: list[str] = []

    if _truthy_env("TELEMETRY_AUTO_ENABLE"):
        otel = integrations.get("otel")
        if otel and otel.configured and not otel.enabled:
            otel.enabled = True
            otel.status = IntegrationStatus.CONNECTED
            otel.connection_health = "connected"
            otel.error_message = None
            integrations["otel"] = otel
            enabled.append("otel")

    if enabled:
        save_integration_overrides(integrations)
    return enabled
