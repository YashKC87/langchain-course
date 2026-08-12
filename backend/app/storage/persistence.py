"""Persist integration configuration to disk (secrets as refs only)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.models.domain import Integration, IntegrationConfig, IntegrationStatus


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


def apply_env_defaults(integrations: dict[str, Integration]) -> None:
    """Pre-fill Azure/AWS/GCP from environment when not already configured."""
    azure = integrations.get("azure")
    if azure and not azure.configured:
        tenant = os.environ.get("AZURE_TENANT_ID")
        subscription = os.environ.get("AZURE_SUBSCRIPTION_ID")
        if tenant and subscription:
            azure.config.fields = {
                "tenant_id": tenant,
                "subscription_id": subscription,
                "resource_group": os.environ.get("AZURE_RESOURCE_GROUP", ""),
                "foundry_project": os.environ.get("AZURE_FOUNDRY_PROJECT", ""),
                "app_insights": os.environ.get("AZURE_APP_INSIGHTS", ""),
                "log_analytics": os.environ.get("AZURE_LOG_ANALYTICS", ""),
                "otel_endpoint": os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", ""),
            }
            azure.config.auth_method = os.environ.get("AZURE_AUTH_METHOD", "Managed Identity")
            azure.configured = True
            azure.status = IntegrationStatus.DISABLED
            azure.auth_state = "configured_from_env"

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

    otel = integrations.get("otel")
    if otel and not otel.configured:
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        if endpoint:
            otel.config.fields = {
                "collector_endpoint": endpoint,
                "protocol": os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf"),
            }
            otel.config.auth_method = "None"
            otel.configured = True
            otel.status = IntegrationStatus.DISABLED
