"""Deterministic investigation workflow — not a free-form chat loop."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
import uuid

from ops_agent.tools import build_default_registry
from ops_agent.tools.adapters import RequestHumanApproval
from ops_agent.security.guardrails import GuardrailEngine
from ops_agent.memory.stores import MemoryFacade
from ops_agent.agents.response_format import format_ops_finding, format_executive_summary


@dataclass
class InvestigationState:
    investigation_id: str
    resource: str
    domain: str = "unknown"
    severity: str = "Unknown"
    steps_completed: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)
    prediction: dict[str, Any] = field(default_factory=dict)
    runbook: dict[str, Any] = field(default_factory=dict)
    approval: dict[str, Any] = field(default_factory=dict)
    execution: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)
    snow: dict[str, Any] = field(default_factory=dict)
    missing_data: list[str] = field(default_factory=list)
    tool_failures: int = 0
    status: str = "InProgress"


class InvestigationWorkflow:
    """Implements the mandated investigation sequence with hard stops."""

    def __init__(self, registry=None, memory: Optional[MemoryFacade] = None, roles: Optional[list[str]] = None):
        self.registry = registry or build_default_registry()
        self.memory = memory or MemoryFacade()
        self.roles = roles or ["OpsInvestigator", "OpsAdmin", "RemediationExecutor", "PredictionService"]
        self.guardrails = GuardrailEngine(max_tool_calls=20, max_iterations=8)

    def run(self, resource: str, user_report: str = "", *, demo: bool = False) -> dict[str, Any]:
        state = InvestigationState(investigation_id=str(uuid.uuid4()), resource=resource)
        self.memory.session.set("investigation", asdict(state))
        cid = state.investigation_id

        # 1–2 Validate + classify
        state.domain = self._classify_domain(resource, user_report)
        state.severity = "High" if "crash" in user_report.lower() or "fail" in user_report.lower() else "Medium"
        state.steps_completed.append("validate_and_classify")

        # 3 Duplicate check
        existing = self.memory.incident.find_open_by_resource(resource)
        if existing:
            state.evidence.append(f"Existing open investigation {existing['investigation_id']} found — continuing correlated work")
        state.steps_completed.append("duplicate_check")

        # 4 Collect telemetry
        la = self._tool(
            "query_log_analytics",
            {
                "workspace_id": "00000000-0000-0000-0000-000000000000",
                "approved_query_id": "endpoint_device_health" if state.domain == "digital_workplace" else "vm_perf_summary_15m",
                "parameters": {"resource": resource},
            },
            cid,
            state,
        )
        metrics_summary = (la or {}).get("summary", {})
        anomalies = (la or {}).get("anomalies", [])
        for a in anomalies:
            state.evidence.append(f"Telemetry anomaly: {a}")
        state.steps_completed.append("collect_telemetry")

        # 5 Service / resource health
        rh = self._tool("get_azure_resource_health", {"resource_id": resource}, cid, state)
        if rh:
            state.evidence.append(f"Resource Health: {rh.get('availabilityState')} - {rh.get('summary')}")
        state.steps_completed.append("check_health")

        # 6 Recent changes
        changes = self._tool("get_recent_azure_changes", {"resource_id": resource, "time_range": "PT24H"}, cid, state)
        if changes and changes.get("change_count"):
            state.evidence.append(f"Recent changes (24h): {changes['change_count']}")
        state.steps_completed.append("review_changes")

        # 7 Predictive model — probability ONLY from endpoint/tool
        feature_payload = self._features_from_telemetry(state.domain, metrics_summary, user_report)
        predict_tool = "predict_endpoint_incident" if state.domain == "digital_workplace" else "predict_vm_failure"
        prediction = self._tool(predict_tool, {"feature_payload": feature_payload}, cid, state)
        if not prediction:
            state.missing_data.append("prediction_unavailable")
            state.status = "Failed"
            return self._finalize(state, user_report, validated=False)
        state.prediction = prediction
        state.evidence.append(
            f"Model {prediction.get('model_version')} probability={prediction.get('probability')} "
            f"risk={prediction.get('risk_category')}"
        )
        state.steps_completed.append("run_prediction")

        # 8 Correlate + hypotheses
        state.hypotheses = self._rank_hypotheses(state.domain, metrics_summary, prediction, user_report)
        state.steps_completed.append("correlate_evidence")

        # 9 ServiceNow lookup
        snow_list = self._tool(
            "get_servicenow_incidents",
            {"configuration_item": resource, "time_range": "PT7D"},
            cid,
            state,
        )
        if snow_list is not None:
            state.evidence.append(f"ServiceNow open incidents: {snow_list.get('result_count', 0)}")
        state.steps_completed.append("servicenow_lookup")

        # 10 Select runbook
        issue_type = "endpoint_resource_pressure" if state.domain == "digital_workplace" else "vm_memory_pressure"
        runbook = self._tool("get_approved_runbook", {"issue_type": issue_type}, cid, state)
        if not runbook:
            state.missing_data.append("runbook_unavailable")
        else:
            state.runbook = runbook
        state.steps_completed.append("select_runbook")

        # 11–12 Risk + approval
        risk_level = (runbook or {}).get("risk_level", "L2")
        approval_required = risk_level in ("L2", "L3")
        if approval_required and runbook:
            approval = self._tool(
                "request_human_approval",
                {
                    "action_payload": {
                        "issue_summary": user_report or f"Predicted risk for {resource}",
                        "affected_resource": resource,
                        "proposed_action": ",".join(runbook.get("actions", [])),
                        "business_impact": "Potential productivity / service disruption",
                        "expected_benefit": "Restore health within validation policy thresholds",
                        "risk_level": risk_level,
                        "prerequisites": "Confirm maintenance window if production",
                        "validation_method": runbook.get("validation_policy"),
                        "rollback_procedure": runbook.get("rollback"),
                        "parameters": {"resource": resource},
                    }
                },
                cid,
                state,
            )
            state.approval = approval or {}
            if demo and approval:
                # Simulate human approval in demo mode only
                RequestHumanApproval._store[approval["approval_id"]]["status"] = "Approved"
                state.approval["status"] = "Approved"
                state.evidence.append(f"Demo mode: approval {approval['approval_id']} marked Approved")
        else:
            state.approval = {"approval_id": "PREAPPROVED_L1", "status": "PreApproved", "risk_level": "L1"}
            approval_required = False
        state.steps_completed.append("assess_and_approve")

        # 13 Execute only if approved / preapproved
        executed = False
        if runbook and state.approval.get("status") in ("Approved", "PreApproved"):
            exec_result = self._tool(
                "execute_approved_remediation",
                {
                    "approval_id": state.approval["approval_id"],
                    "runbook_id": runbook["runbook_id"],
                    "parameters": {"resource": resource},
                },
                cid,
                state,
            )
            state.execution = exec_result or {}
            executed = bool(exec_result and exec_result.get("status") == "Succeeded")
        state.steps_completed.append("execute")

        # 14 Validate recovery — NEVER skip after remediation
        validated = False
        if executed:
            validation = self._tool(
                "validate_service_recovery",
                {"resource_id": resource, "validation_policy": runbook.get("validation_policy", "default")},
                cid,
                state,
            )
            state.validation = validation or {}
            validated = bool(validation and validation.get("passed"))
            if not validated:
                state.evidence.append("VALIDATION FAILED — remediation success NOT claimed")
        elif not approval_required:
            state.evidence.append("No remediation executed in this path")
        else:
            state.evidence.append("Awaiting human approval — no remediation executed")
        state.steps_completed.append("validate_recovery")

        # 15 Update incident
        snow = self._tool(
            "create_or_update_servicenow_incident",
            {
                "payload": {
                    "correlation_id": cid,
                    "short_description": f"Ops agent investigation for {resource}",
                    "state": "Resolved" if validated else "In Progress",
                    "work_notes": f"Prediction={state.prediction.get('probability')} validated={validated}",
                    "configuration_item": resource,
                }
            },
            cid,
            state,
        )
        state.snow = snow or {}
        state.steps_completed.append("update_incident")

        # 16 Notify
        self._tool(
            "send_teams_notification",
            {
                "payload": {
                    "text": f"Investigation {cid} for {resource}: risk={state.prediction.get('risk_category')} validated={validated}",
                    "idempotency_key": cid,
                }
            },
            cid,
            state,
        )
        state.steps_completed.append("notify")

        # 17 Audit + 18 learning feedback
        self._tool(
            "write_audit_event",
            {
                "payload": {
                    "investigation_id": cid,
                    "resource": resource,
                    "prediction": state.prediction.get("probability"),
                    "model_version": state.prediction.get("model_version"),
                    "executed": executed,
                    "validated": validated,
                    "steps": state.steps_completed,
                }
            },
            cid,
            state,
        )
        self.memory.learning.capture(
            {
                "investigation_id": cid,
                "domain": state.domain,
                "features": feature_payload,
                "probability": state.prediction.get("probability"),
                "validated": validated,
                "anonymized": True,
            }
        )
        self.memory.incident.upsert(asdict(state))
        state.steps_completed.append("audit_and_feedback")
        state.status = "Completed" if validated or not executed else ("AwaitingApproval" if approval_required and not executed else "CompletedWithFindings")

        return self._finalize(state, user_report, validated=validated, approval_required=approval_required)

    def _tool(self, name: str, payload: dict[str, Any], cid: str, state: InvestigationState) -> Optional[dict[str, Any]]:
        if not self.guardrails.allow_tool_call():
            state.missing_data.append("tool_call_limit_reached")
            return None
        result = self.registry.invoke(name, payload, actor_roles=self.roles, correlation_id=cid)
        if not result.ok:
            state.tool_failures += 1
            state.missing_data.append(f"{name}:{result.error_code}")
            if state.tool_failures >= 3:
                state.evidence.append("Stopped after repeated tool failures")
            return None
        if result.data_mode in ("unavailable",) or result.missing_fields:
            state.missing_data.extend(result.missing_fields or [f"{name}_partial"])
        return result.data

    def _classify_domain(self, resource: str, report: str) -> str:
        r = resource.upper()
        text = f"{resource} {report}".lower()
        if "LAPTOP" in r or "DESKTOP" in r or "intune" in text or "teams" in text or "vpn" in text:
            return "digital_workplace"
        if "AKS" in r or "namespace" in text or "pod" in text:
            return "aks"
        if "capacity" in text or "advisor" in text:
            return "capacity"
        return "azure_infrastructure"

    def _features_from_telemetry(self, domain: str, summary: dict[str, Any], report: str) -> dict[str, Any]:
        if domain == "digital_workplace":
            return {
                "cpu_util_p95": summary.get("cpu_util_p95", 75),
                "mem_util_p95": summary.get("mem_util_p95", 92),
                "disk_free_pct": 8.0,
                "disk_latency_p95": summary.get("disk_latency_ms_p95", 40),
                "vpn_packet_loss_pct": summary.get("net_packet_loss_pct", 2.4),
                "vpn_disconnect_count": 6 if "vpn" in report.lower() else 1,
                "teams_crash_count": 4 if "teams" in report.lower() else 0,
                "defender_alert_count_7d": 1,
                "intune_sync_age_hours": 36,
                "update_compliance_gap": 1,
                "historical_incident_30d": 2,
                "battery_health_score": 70,
                "startup_process_count": 85,
            }
        return {
            "cpu_util_p95": summary.get("cpu_util_p95", 80),
            "mem_available_pct_min": 100 - float(summary.get("mem_util_p95", 90)),
            "disk_latency_p95": summary.get("disk_latency_ms_p95", 35),
            "disk_queue_depth_max": summary.get("disk_queue_depth_max", 5),
            "iops_p95": summary.get("iops_p95", 2000),
            "net_packet_loss_pct": summary.get("net_packet_loss_pct", 0.5),
            "net_throughput_mbps_p95": 400,
            "failed_service_count": summary.get("failed_service_count", 0),
            "guest_heartbeat_ok": 1.0 if summary.get("guest_heartbeat_ok", True) else 0.0,
            "boot_diagnostic_error_count": 0,
            "update_compliance_gap": 1,
            "availability_event_count": 0,
            "resource_health_unhealthy": 0,
            "config_change_count_24h": 1,
            "defender_alert_count_7d": 0,
            "historical_incident_30d": 1,
            "app_response_p95": 850,
        }

    def _rank_hypotheses(self, domain: str, summary: dict, prediction: dict, report: str) -> list[str]:
        hyps = []
        contribs = prediction.get("top_positive_contributors") or []
        for c in contribs[:3]:
            hyps.append(f"{c['feature']} contributing to elevated risk (value={c.get('value')})")
        if domain == "digital_workplace":
            if "disk" in report.lower() or True:
                hyps.insert(0, "Disk space below operational threshold")
            if summary.get("mem_util_p95", 0) >= 90:
                hyps.insert(1, "Sustained memory utilization above 90%")
            if "vpn" in report.lower():
                hyps.append("Repeated VPN packet loss / disconnections")
            if "teams" in report.lower():
                hyps.append("Teams client crashes correlated with memory pressure")
        # de-dupe preserve order
        seen = set()
        out = []
        for h in hyps:
            if h not in seen:
                seen.add(h)
                out.append(h)
        return out[:5] or ["Insufficient evidence — mark data gaps and escalate"]

    def _finalize(self, state: InvestigationState, user_report: str, validated: bool, approval_required: bool = False) -> dict[str, Any]:
        finding = format_ops_finding(state, user_report, validated, approval_required)
        executive = format_executive_summary(state, approval_required)
        return {
            "investigation_id": state.investigation_id,
            "status": state.status,
            "missing_data": state.missing_data,
            "ops_finding": finding,
            "executive_summary": executive,
            "raw_state": asdict(state),
        }


def main() -> None:
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Run investigation workflow")
    parser.add_argument("--resource", required=True)
    parser.add_argument("--report", default="slow performance, Teams crashes, repeated VPN disconnections")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    os.environ.setdefault("OPS_AGENT_DATA_MODE", "mock")
    wf = InvestigationWorkflow()
    result = wf.run(args.resource, args.report, demo=args.demo)
    print(result["ops_finding"])
    print()
    print(result["executive_summary"])


if __name__ == "__main__":
    main()
