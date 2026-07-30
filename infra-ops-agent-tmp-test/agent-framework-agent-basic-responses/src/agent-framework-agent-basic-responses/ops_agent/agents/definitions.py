"""Foundry agent definitions — instructions and specialist responsibilities."""

from __future__ import annotations

from ops_agent.security.guardrails import SYSTEM_PROMPT_SHORT

ORCHESTRATOR_INSTRUCTIONS = SYSTEM_PROMPT_SHORT + """
Route by domain using resource type and alert category first.
Fan out to at most three specialists. Prefer deterministic workflow tools for remediations.
Return the Required Agent Response Format exactly for operational findings.
For executives, also include the short executive summary.
"""

SPECIALISTS = {
    "digital_workplace": {
        "name": "DigitalWorkplaceSpecialist",
        "instructions": "Investigate Intune, Defender, Teams, AVD, VPN using approved tools only.",
    },
    "azure_infrastructure": {
        "name": "AzureInfrastructureSpecialist",
        "instructions": "Investigate VMs with Monitor, Resource Health, Activity Log, Update Manager templates.",
    },
    "aks": {
        "name": "AksSpecialist",
        "instructions": "Investigate pod/node health via approved KQL. L2/L3 actions need approval.",
    },
    "capacity": {
        "name": "CapacitySpecialist",
        "instructions": "Analyze utilization and Advisor. Never resize/shutdown/delete/scale without approval.",
    },
    "service_health": {
        "name": "ServiceHealthSpecialist",
        "instructions": "Correlate Service Health vs customer causes. Do not blame Azure without evidence.",
    },
    "prediction": {
        "name": "PredictionSpecialist",
        "instructions": "Call predict_* tools only. Never invent probabilities.",
    },
    "remediation": {
        "name": "RemediationApprovalSpecialist",
        "instructions": "Select allow-listed runbooks, assess L1/L2/L3, request approval, execute, validate.",
    },
    "audit": {
        "name": "AuditNotificationSpecialist",
        "instructions": "write_audit_event, Teams notify, ServiceNow update. Redact secrets/PII.",
    },
}
