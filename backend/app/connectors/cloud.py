"""Cloud platform connector stubs — extend without redesigning the core."""

from __future__ import annotations

from typing import Any

from app.connectors.base import BaseConnector


class AzureConnector(BaseConnector):
    id = "azure"
    name = "Microsoft Azure"
    provider = "azure"

    async def authenticate(self, config: dict[str, Any]) -> dict[str, Any]:
        method = config.get("auth_method")
        if not method:
            return {
                "ok": False,
                "message": (
                    "Select Managed Identity, Entra ID, or Service Principal "
                    "before enabling Azure."
                ),
            }
        return {"ok": True, "message": f"Azure auth method '{method}' configured."}

    async def validate_permissions(self, config: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "message": (
                "Ensure Monitoring Reader on Application Insights / Log Analytics "
                "and appropriate Foundry project access."
            ),
        }

    async def validate_telemetry_source(self, config: dict[str, Any]) -> dict[str, Any]:
        if not config.get("subscription_id"):
            return {
                "ok": False,
                "message": (
                    "Azure authentication succeeded pattern requires a subscription. "
                    "Provide subscription_id and Application Insights or OTel endpoint."
                ),
            }
        return {"ok": True, "message": "Azure telemetry source configuration present."}

    async def discover_agents(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    async def fetch_telemetry(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        return []


class AWSConnector(BaseConnector):
    id = "aws"
    name = "AWS"
    provider = "aws"

    async def authenticate(self, config: dict[str, Any]) -> dict[str, Any]:
        method = config.get("auth_method")
        if not method:
            return {
                "ok": False,
                "message": "Select IAM Role or Workload Identity before enabling AWS.",
            }
        return {"ok": True, "message": f"AWS auth method '{method}' configured."}

    async def validate_permissions(self, config: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "message": "Ensure CloudWatch and Bedrock/AgentCore read permissions.",
        }

    async def validate_telemetry_source(self, config: dict[str, Any]) -> dict[str, Any]:
        if not config.get("account_id") or not config.get("region"):
            return {
                "ok": False,
                "message": "AWS account_id and region are required.",
            }
        return {"ok": True, "message": "AWS telemetry source configuration present."}

    async def discover_agents(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    async def fetch_telemetry(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        return []


class GCPConnector(BaseConnector):
    id = "gcp"
    name = "Google Cloud"
    provider = "gcp"

    async def authenticate(self, config: dict[str, Any]) -> dict[str, Any]:
        method = config.get("auth_method")
        if not method:
            return {
                "ok": False,
                "message": "Select Workload Identity or Service Account before enabling Google Cloud.",
            }
        return {"ok": True, "message": f"GCP auth method '{method}' configured."}

    async def validate_permissions(self, config: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "message": "Ensure Cloud Observability and Vertex AI read permissions.",
        }

    async def validate_telemetry_source(self, config: dict[str, Any]) -> dict[str, Any]:
        if not config.get("project_id"):
            return {"ok": False, "message": "GCP project_id is required."}
        return {"ok": True, "message": "GCP telemetry source configuration present."}

    async def discover_agents(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    async def fetch_telemetry(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        return []


class LangSmithConnector(BaseConnector):
    id = "langsmith"
    name = "LangSmith"
    provider = "langsmith"

    async def authenticate(self, config: dict[str, Any]) -> dict[str, Any]:
        if "api_key" not in config and not config.get("api_key_ref"):
            return {
                "ok": False,
                "message": "LangSmith API key reference is required (stored as secret ref).",
            }
        return {"ok": True, "message": "LangSmith credentials referenced."}

    async def validate_permissions(self, config: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "message": "LangSmith workspace read access required."}

    async def validate_telemetry_source(self, config: dict[str, Any]) -> dict[str, Any]:
        if not config.get("api_endpoint"):
            return {"ok": False, "message": "LangSmith api_endpoint is required."}
        return {"ok": True, "message": "LangSmith endpoint configured."}

    async def discover_agents(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    async def fetch_telemetry(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        return []
