"""Foundry @tool wrappers over the ops_agent tool registry and workflow."""

from __future__ import annotations

import json
import os
from typing import Annotated, Any

from pydantic import Field

from ops_agent.tools import build_default_registry
from ops_agent.tools.base import compact_json
from ops_agent.workflows.investigate import InvestigationWorkflow

_REGISTRY = build_default_registry()
_ROLES = ["OpsInvestigator", "OpsAdmin", "RemediationExecutor", "PredictionService"]


def _invoke(tool: str, payload: dict[str, Any]) -> str:
    result = _REGISTRY.invoke(tool, payload, actor_roles=_ROLES)
    return compact_json(result.to_dict())


def investigate_incident(
    resource: Annotated[str, Field(description="Affected device, VM, or resource identifier e.g. LAPTOP-1204")],
    user_report: Annotated[str, Field(description="User or alert description of the issue")] = "",
    demo_mode: Annotated[bool, Field(description="Use demo approval path for L2 actions")] = False,
) -> str:
    """Run the full governed SRE investigation workflow with predictions, evidence, and validation."""
    os.environ.setdefault("OPS_AGENT_DATA_MODE", os.getenv("OPS_AGENT_DATA_MODE", "mock"))
    wf = InvestigationWorkflow(registry=_REGISTRY)
    result = wf.run(resource, user_report, demo=demo_mode)
    return compact_json(
        {
            "investigation_id": result["investigation_id"],
            "status": result["status"],
            "ops_finding": result["ops_finding"],
            "executive_summary": result["executive_summary"],
            "missing_data": result.get("missing_data", []),
        }
    )


def get_azure_resource_health(
    resource_id: Annotated[str, Field(description="Azure resource ID or resource name")],
) -> str:
    """Get Azure Resource Health state for a resource."""
    return _invoke("get_azure_resource_health", {"resource_id": resource_id})


def query_log_analytics(
    workspace_id: Annotated[str, Field(description="Log Analytics workspace ID")],
    approved_query_id: Annotated[str, Field(description="Allow-listed query template ID")],
) -> str:
    """Run an approved Log Analytics query template (no free-form KQL)."""
    return _invoke(
        "query_log_analytics",
        {"workspace_id": workspace_id, "approved_query_id": approved_query_id, "parameters": {}},
    )


def predict_vm_failure(
    feature_payload: Annotated[dict[str, Any], Field(description="VM feature dictionary for ML endpoint")],
) -> str:
    """Predict Azure VM failure within 1 hour using logistic regression (never invent probability)."""
    return _invoke("predict_vm_failure", {"feature_payload": feature_payload})


def predict_endpoint_incident(
    feature_payload: Annotated[dict[str, Any], Field(description="Endpoint feature dictionary for ML endpoint")],
) -> str:
    """Predict endpoint incident within 24 hours using logistic regression."""
    return _invoke("predict_endpoint_incident", {"feature_payload": feature_payload})


def get_approved_runbook(
    issue_type: Annotated[str, Field(description="Issue type e.g. endpoint_resource_pressure")],
) -> str:
    """Resolve allow-listed remediation runbook for an issue type."""
    return _invoke("get_approved_runbook", {"issue_type": issue_type})


def list_registered_tools() -> str:
    """List all registered ops tool names available to this agent."""
    return json.dumps({"tools": _REGISTRY.list_tools()})
