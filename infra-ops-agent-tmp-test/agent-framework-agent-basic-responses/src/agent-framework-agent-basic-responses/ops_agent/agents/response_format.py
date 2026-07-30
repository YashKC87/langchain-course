"""Required agent response formatting."""

from __future__ import annotations

from typing import Any


def format_ops_finding(state: Any, user_report: str, validated: bool, approval_required: bool) -> str:
    pred = state.prediction or {}
    hyps = state.hypotheses or ["Insufficient evidence"]
    evidence = state.evidence or ["No evidence collected"]
    runbook = state.runbook or {}
    actions = ", ".join(runbook.get("actions", [])) or "Investigate further / escalate"
    risk = runbook.get("risk_level", "Unknown")
    snow = state.snow or {}
    snow_status = snow.get("number", "Not created") + f" ({snow.get('state', 'n/a')})" if snow else "Unavailable / not created"

    hyp_lines = "\n".join(f"{i}. {h}" for i, h in enumerate(hyps, 1))
    ev_lines = "\n".join(f"{i}. {e}" for i, e in enumerate(evidence[:8], 1))
    missing = ", ".join(state.missing_data) if state.missing_data else "None marked"

    approval_text = "Yes" if approval_required and state.approval.get("status") not in ("Approved", "PreApproved") else (
        "Yes (approved)" if approval_required else "No, provided actions are in the approved automation policy"
    )

    summary = "Investigation completed with grounded telemetry and model output."
    if state.domain == "digital_workplace":
        summary = "The endpoint is experiencing sustained resource pressure and network instability."
    health = "Degraded" if float(pred.get("probability") or 0) >= 0.4 else "Stable"
    if validated:
        health = "Recovering / Validated"

    return f"""Incident Summary:
{summary}

Affected User or Resource:
{state.resource}
Domain:
{state.domain}
Current Health:
{health}
Severity:
{state.severity}

Prediction:
Failure Probability:
{pred.get('probability', 'UNAVAILABLE - model not called')}
Risk Category:
{pred.get('risk_category', 'UNAVAILABLE')}
Model Version:
{pred.get('model_version', 'UNAVAILABLE')}
Prediction Window:
{pred.get('prediction_window', 'UNAVAILABLE')}

Likely Root Cause:
{hyp_lines}

Supporting Evidence:
{ev_lines}

Recommended Action:
{actions}
Expected Result:
Return disk, memory, client stability, and network quality to policy thresholds.
Risk Level:
{risk}
Approval Required: {approval_text}

Rollback Plan:
{runbook.get('rollback', 'Escalate; do not perform unapproved destructive actions')}
Validation Method:
{runbook.get('validation_policy', 'validate_service_recovery')} - passed={validated}
ServiceNow Status:
{snow_status}
Next Review Time:
15 minutes
Missing or Unavailable Data:
{missing}
"""


def format_executive_summary(state: Any, approval_required: bool) -> str:
    pred = state.prediction or {}
    cause = (state.hypotheses or ["unconfirmed factors"])[0]
    action = ", ".join((state.runbook or {}).get("actions", [])[:3]) or "further investigation"
    impact = "elevated probability of service disruption" if float(pred.get("probability") or 0) >= 0.7 else "moderate operational risk"
    approval = "required" if approval_required and state.approval.get("status") not in ("Approved", "PreApproved") else (
        "obtained" if approval_required else "not required"
    )
    return (
        f"The agent detected a {str(pred.get('risk_category', 'Unknown')).lower()} probability of service impact caused by {cause}.\n"
        f"The recommended action is {action}.\n"
        f"The expected business impact is {impact}.\n"
        f"Human approval is {approval}."
    )
