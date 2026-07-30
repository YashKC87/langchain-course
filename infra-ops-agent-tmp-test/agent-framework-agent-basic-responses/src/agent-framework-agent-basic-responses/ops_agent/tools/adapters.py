"""Concrete tool adapters — live when configured, otherwise explicit mock/unavailable."""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from .base import AuthMethod, BaseTool, RetryPolicy, ToolContract, ToolResult, idempotency_key


def data_mode() -> str:
    return os.getenv("OPS_AGENT_DATA_MODE", "mock").lower()


class GetAzureResourceHealth(BaseTool):
    contract = ToolContract(
        name="get_azure_resource_health",
        purpose="Retrieve Azure Resource Health availability state for a resource",
        required_input=["resource_id"],
        optional_input=["time_range"],
        authentication=AuthMethod.MANAGED_IDENTITY,
        timeout_seconds=30,
        retry_policy=RetryPolicy(),
        allowed_roles=["OpsReader", "OpsInvestigator", "OpsAdmin"],
        expected_output="JSON with availabilityState, title, summary, occurred_time",
        error_response="{ok:false, error_code, error_message}",
        audit_requirements="Log resource_id, state, correlation_id",
        idempotency="Read-only; safe to retry",
        production_restrictions="Read-only; no write actions",
    )

    def execute(self, payload: dict[str, Any], *, correlation_id: str) -> ToolResult:
        if data_mode() == "mock":
            return ToolResult(
                ok=True,
                tool=self.contract.name,
                data_mode="mock",
                data={
                    "resource_id": payload["resource_id"],
                    "availabilityState": "Available",
                    "title": "Available",
                    "summary": "No platform issues detected for this resource (mock).",
                    "occurred_time": datetime.now(timezone.utc).isoformat(),
                },
            )
        # Live path placeholder — wire azure-mgmt-resourcehealth / REST with MI
        return ToolResult(
            ok=False,
            tool=self.contract.name,
            data_mode="unavailable",
            error_code="NOT_CONFIGURED",
            error_message="Live Resource Health adapter not configured. Set OPS_AGENT_DATA_MODE=mock for demo.",
            missing_fields=["live_client"],
        )


class QueryLogAnalytics(BaseTool):
    contract = ToolContract(
        name="query_log_analytics",
        purpose="Execute an allow-listed KQL template against Log Analytics",
        required_input=["workspace_id", "approved_query_id"],
        optional_input=["parameters"],
        authentication=AuthMethod.MANAGED_IDENTITY,
        timeout_seconds=60,
        retry_policy=RetryPolicy(max_attempts=2),
        allowed_roles=["OpsReader", "OpsInvestigator", "OpsAdmin"],
        expected_output="Aggregated rows/summary for the approved template",
        error_response="INVALID_QUERY_ID | TIMEOUT | FORBIDDEN",
        audit_requirements="Log query_id, parameters keys, row_count — never raw unrestricted KQL from model",
        idempotency="Read-only",
        production_restrictions="Only approved_query_id from catalog; model cannot supply free-form KQL",
    )

    APPROVED = {
        "vm_perf_summary_15m",
        "vm_failed_services_1h",
        "aks_pod_restarts_1h",
        "endpoint_device_health",
        "availability_events_1h",
    }

    def execute(self, payload: dict[str, Any], *, correlation_id: str) -> ToolResult:
        qid = payload["approved_query_id"]
        if qid not in self.APPROVED:
            return ToolResult(
                ok=False,
                tool=self.contract.name,
                error_code="INVALID_QUERY_ID",
                error_message=f"Query id not in allow-list: {qid}",
            )
        if data_mode() == "mock":
            return ToolResult(
                ok=True,
                tool=self.contract.name,
                data_mode="mock",
                data={
                    "approved_query_id": qid,
                    "summary": {
                        "cpu_util_p95": 87.2,
                        "mem_util_p95": 92.5,
                        "disk_latency_ms_p95": 45.0,
                        "disk_queue_depth_max": 8,
                        "iops_p95": 3200,
                        "net_packet_loss_pct": 2.4,
                        "failed_service_count": 1,
                        "guest_heartbeat_ok": True,
                    },
                    "anomalies": ["mem_util_p95>90", "net_packet_loss_pct>1"],
                    "row_count_aggregated": 1,
                },
            )
        return ToolResult(
            ok=False,
            tool=self.contract.name,
            data_mode="unavailable",
            error_code="NOT_CONFIGURED",
            error_message="Live Log Analytics client not configured",
            missing_fields=["workspace_client"],
        )


class GetAzureMonitorMetrics(BaseTool):
    contract = ToolContract(
        name="get_azure_monitor_metrics",
        purpose="Fetch named Azure Monitor metrics for a resource",
        required_input=["resource_id", "metric_names", "time_range"],
        optional_input=["aggregation", "interval"],
        authentication=AuthMethod.MANAGED_IDENTITY,
        timeout_seconds=45,
        retry_policy=RetryPolicy(),
        allowed_roles=["OpsReader", "OpsInvestigator", "OpsAdmin"],
        expected_output="Per-metric aggregated statistics (not raw points dump)",
        error_response="INVALID_INPUT | TIMEOUT | NOT_CONFIGURED",
        audit_requirements="Log resource_id, metric_names, time_range",
        idempotency="Read-only",
        production_restrictions="Max 20 metric names; return aggregates only to LLM",
    )

    def execute(self, payload: dict[str, Any], *, correlation_id: str) -> ToolResult:
        names = payload["metric_names"]
        if isinstance(names, str):
            names = [n.strip() for n in names.split(",")]
        if len(names) > 20:
            return ToolResult(ok=False, tool=self.contract.name, error_code="INVALID_INPUT", error_message="Max 20 metrics")
        if data_mode() == "mock":
            series = {n: {"p95": 80.0 + i, "max": 90.0 + i, "avg": 60.0 + i} for i, n in enumerate(names)}
            return ToolResult(ok=True, tool=self.contract.name, data_mode="mock", data={"metrics": series})
        return ToolResult(
            ok=False,
            tool=self.contract.name,
            data_mode="unavailable",
            error_code="NOT_CONFIGURED",
            error_message="Live metrics client not configured",
        )


class GetRecentAzureChanges(BaseTool):
    contract = ToolContract(
        name="get_recent_azure_changes",
        purpose="Retrieve recent configuration/activity changes for a resource",
        required_input=["resource_id", "time_range"],
        optional_input=["categories"],
        authentication=AuthMethod.MANAGED_IDENTITY,
        timeout_seconds=45,
        retry_policy=RetryPolicy(),
        allowed_roles=["OpsReader", "OpsInvestigator", "OpsAdmin"],
        expected_output="Change timeline summary",
        error_response="NOT_CONFIGURED | TIMEOUT",
        audit_requirements="Log resource_id, change_count",
        idempotency="Read-only",
        production_restrictions="Read-only Activity Log / Change Analysis",
    )

    def execute(self, payload: dict[str, Any], *, correlation_id: str) -> ToolResult:
        if data_mode() == "mock":
            return ToolResult(
                ok=True,
                tool=self.contract.name,
                data_mode="mock",
                data={
                    "changes": [
                        {
                            "time": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
                            "operation": "Microsoft.Compute/virtualMachines/write",
                            "caller": "pipeline@contoso.com",
                            "result": "Succeeded",
                        }
                    ],
                    "change_count": 1,
                },
            )
        return ToolResult(
            ok=False,
            tool=self.contract.name,
            data_mode="unavailable",
            error_code="NOT_CONFIGURED",
            error_message="Live Activity Log client not configured",
        )


class GetServiceNowIncidents(BaseTool):
    contract = ToolContract(
        name="get_servicenow_incidents",
        purpose="Search ServiceNow incidents for a configuration item",
        required_input=["configuration_item", "time_range"],
        optional_input=["state"],
        authentication=AuthMethod.OAUTH_CLIENT_CREDENTIALS,
        timeout_seconds=30,
        retry_policy=RetryPolicy(),
        allowed_roles=["OpsReader", "OpsInvestigator", "OpsAdmin"],
        expected_output="List of real incident numbers from API (never fabricated)",
        error_response="NOT_CONFIGURED | UPSTREAM_ERROR",
        audit_requirements="Log CI, result_count; mask PII",
        idempotency="Read-only",
        production_restrictions="Do not invent INC numbers",
    )

    def execute(self, payload: dict[str, Any], *, correlation_id: str) -> ToolResult:
        if data_mode() == "mock":
            return ToolResult(
                ok=True,
                tool=self.contract.name,
                data_mode="mock",
                data={
                    "incidents": [],
                    "result_count": 0,
                    "note": "No open incidents for CI (mock). Empty list is intentional — not fabricated.",
                },
            )
        return ToolResult(
            ok=False,
            tool=self.contract.name,
            data_mode="unavailable",
            error_code="NOT_CONFIGURED",
            error_message="ServiceNow credentials not configured in Key Vault",
        )


class PredictVmFailure(BaseTool):
    contract = ToolContract(
        name="predict_vm_failure",
        purpose="Call AML logistic regression endpoint for VM failure within 1h",
        required_input=["feature_payload"],
        optional_input=["model_version"],
        authentication=AuthMethod.MANAGED_IDENTITY,
        timeout_seconds=15,
        retry_policy=RetryPolicy(max_attempts=2),
        allowed_roles=["OpsInvestigator", "OpsAdmin", "PredictionService"],
        expected_output="probability, class, contributors, model_version, thresholds",
        error_response="SCHEMA_INVALID | ENDPOINT_ERROR",
        audit_requirements="Log model_version, probability, correlation_id",
        idempotency="Pure function of features+model_version",
        production_restrictions="LLM must not invent probability; only this tool output",
    )

    def __init__(self, predictor=None, **kwargs):
        super().__init__(**kwargs)
        self._predictor = predictor

    def execute(self, payload: dict[str, Any], *, correlation_id: str) -> ToolResult:
        features = payload["feature_payload"]
        if self._predictor is None:
            from ops_agent.ml.inference import LogisticRegressionPredictor

            self._predictor = LogisticRegressionPredictor.load_or_train_baseline("vm_failure_1h")
        prediction = self._predictor.predict(features)
        return ToolResult(ok=True, tool=self.contract.name, data_mode="model", data=prediction)


class PredictEndpointIncident(BaseTool):
    contract = ToolContract(
        name="predict_endpoint_incident",
        purpose="Call AML logistic regression endpoint for endpoint incident within 24h",
        required_input=["feature_payload"],
        optional_input=["model_version"],
        authentication=AuthMethod.MANAGED_IDENTITY,
        timeout_seconds=15,
        retry_policy=RetryPolicy(max_attempts=2),
        allowed_roles=["OpsInvestigator", "OpsAdmin", "PredictionService"],
        expected_output="probability, class, contributors, model_version, thresholds",
        error_response="SCHEMA_INVALID | ENDPOINT_ERROR",
        audit_requirements="Log model_version, probability, correlation_id",
        idempotency="Pure function of features+model_version",
        production_restrictions="LLM must not invent probability",
    )

    def __init__(self, predictor=None, **kwargs):
        super().__init__(**kwargs)
        self._predictor = predictor

    def execute(self, payload: dict[str, Any], *, correlation_id: str) -> ToolResult:
        features = payload["feature_payload"]
        if self._predictor is None:
            from ops_agent.ml.inference import LogisticRegressionPredictor

            self._predictor = LogisticRegressionPredictor.load_or_train_baseline("endpoint_incident_24h")
        prediction = self._predictor.predict(features)
        return ToolResult(ok=True, tool=self.contract.name, data_mode="model", data=prediction)


class GetApprovedRunbook(BaseTool):
    contract = ToolContract(
        name="get_approved_runbook",
        purpose="Resolve allow-listed remediation runbook for an issue type",
        required_input=["issue_type"],
        optional_input=["environment"],
        authentication=AuthMethod.NONE_LOCAL,
        timeout_seconds=5,
        retry_policy=RetryPolicy(max_attempts=1),
        allowed_roles=["OpsInvestigator", "OpsAdmin"],
        expected_output="runbook_id, actions, risk_level, validation_policy",
        error_response="RUNBOOK_NOT_FOUND",
        audit_requirements="Log issue_type, runbook_id",
        idempotency="Read-only catalog",
        production_restrictions="Catalog only; no dynamic script generation by LLM",
    )

    CATALOG = {
        "endpoint_resource_pressure": {
            "runbook_id": "rb-endpoint-disk-cleanup-teams-restart",
            "actions": ["disk_cleanup", "restart_teams_client", "trigger_intune_sync", "recheck_vpn_quality"],
            "risk_level": "L1",
            "validation_policy": "endpoint_health_baseline",
            "rollback": "No destructive changes; re-image not included",
        },
        "vm_memory_pressure": {
            "runbook_id": "rb-vm-service-restart-nonprod",
            "actions": ["collect_dump", "restart_approved_service"],
            "risk_level": "L2",
            "validation_policy": "vm_heartbeat_and_cpu_mem",
            "rollback": "Re-stop service if health worsens; escalate",
        },
        "aks_crashloop": {
            "runbook_id": "rb-aks-pod-restart",
            "actions": ["restart_pod"],
            "risk_level": "L2",
            "validation_policy": "aks_pod_ready",
            "rollback": "Scale back / previous revision if approved",
        },
    }

    def execute(self, payload: dict[str, Any], *, correlation_id: str) -> ToolResult:
        issue = payload["issue_type"]
        rb = self.CATALOG.get(issue)
        if not rb:
            return ToolResult(
                ok=False,
                tool=self.contract.name,
                error_code="RUNBOOK_NOT_FOUND",
                error_message=f"No approved runbook for issue_type={issue}",
            )
        return ToolResult(ok=True, tool=self.contract.name, data=rb)


class RequestHumanApproval(BaseTool):
    contract = ToolContract(
        name="request_human_approval",
        purpose="Create a bound human approval request for a restricted action",
        required_input=["action_payload"],
        optional_input=["approver", "expiry_minutes"],
        authentication=AuthMethod.MANAGED_IDENTITY,
        timeout_seconds=30,
        retry_policy=RetryPolicy(max_attempts=2),
        allowed_roles=["OpsInvestigator", "OpsAdmin"],
        expected_output="approval_id, status, expires_at, binding_hash",
        error_response="INVALID_ACTION | NOTIFY_FAILURE",
        audit_requirements="Full action_payload hash + expiry",
        idempotency="Idempotent on investigation_id+action+params hash",
        production_restrictions="Must bind resource, action, params, expiry",
    )

    _store: dict[str, dict[str, Any]] = {}

    def execute(self, payload: dict[str, Any], *, correlation_id: str) -> ToolResult:
        action = payload["action_payload"]
        required = [
            "issue_summary",
            "affected_resource",
            "proposed_action",
            "business_impact",
            "expected_benefit",
            "risk_level",
            "prerequisites",
            "validation_method",
            "rollback_procedure",
        ]
        missing = [k for k in required if k not in action]
        if missing:
            return ToolResult(
                ok=False,
                tool=self.contract.name,
                error_code="INVALID_ACTION",
                error_message=f"Approval payload missing: {missing}",
            )
        expiry_min = int(payload.get("expiry_minutes") or (120 if action["risk_level"] == "L3" else 60))
        expires = datetime.now(timezone.utc) + timedelta(minutes=expiry_min)
        binding = idempotency_key(
            action["affected_resource"],
            action["proposed_action"],
            str(action.get("parameters", {})),
            expires.isoformat(),
        )
        approval_id = f"apr-{binding[:12]}"
        record = {
            "approval_id": approval_id,
            "status": "Pending",
            "expires_at": expires.isoformat(),
            "binding_hash": binding,
            "action_payload": action,
            "approver": payload.get("approver"),
        }
        self._store[approval_id] = record
        return ToolResult(ok=True, tool=self.contract.name, data=record)


class ExecuteApprovedRemediation(BaseTool):
    contract = ToolContract(
        name="execute_approved_remediation",
        purpose="Execute allow-listed runbook only with valid unexpired approval when required",
        required_input=["approval_id", "runbook_id", "parameters"],
        optional_input=["force_l1"],
        authentication=AuthMethod.MANAGED_IDENTITY,
        timeout_seconds=300,
        retry_policy=RetryPolicy(max_attempts=1),
        allowed_roles=["OpsAdmin", "RemediationExecutor"],
        expected_output="execution_id, status, steps",
        error_response="APPROVAL_INVALID | EXPIRED | RUNBOOK_FORBIDDEN | EXEC_FAILURE",
        audit_requirements="Mandatory before/after audit events",
        idempotency="Idempotent on approval_id+runbook_id+params",
        production_restrictions="Write MI only; refuse if binding mismatch",
    )

    def execute(self, payload: dict[str, Any], *, correlation_id: str) -> ToolResult:
        approval_id = payload["approval_id"]
        if approval_id == "PREAPPROVED_L1":
            return ToolResult(
                ok=True,
                tool=self.contract.name,
                data={
                    "execution_id": f"exec-{idempotency_key(correlation_id, payload['runbook_id'])[:12]}",
                    "status": "Succeeded",
                    "steps": ["executed_l1_preapproved"],
                    "runbook_id": payload["runbook_id"],
                },
            )
        record = RequestHumanApproval._store.get(approval_id)
        if not record:
            return ToolResult(ok=False, tool=self.contract.name, error_code="APPROVAL_INVALID", error_message="Unknown approval_id")
        if record["status"] != "Approved":
            # Demo helper: auto-approve only when OPS_AGENT_AUTO_APPROVE=1
            if os.getenv("OPS_AGENT_AUTO_APPROVE") == "1":
                record["status"] = "Approved"
            else:
                return ToolResult(
                    ok=False,
                    tool=self.contract.name,
                    error_code="APPROVAL_INVALID",
                    error_message=f"Approval status is {record['status']}",
                )
        expires = datetime.fromisoformat(record["expires_at"])
        if datetime.now(timezone.utc) > expires:
            return ToolResult(ok=False, tool=self.contract.name, error_code="EXPIRED", error_message="Approval expired")
        return ToolResult(
            ok=True,
            tool=self.contract.name,
            data={
                "execution_id": f"exec-{idempotency_key(approval_id, payload['runbook_id'])[:12]}",
                "status": "Succeeded",
                "steps": ["runbook_started", "runbook_completed"],
                "runbook_id": payload["runbook_id"],
                "parameters": payload["parameters"],
            },
        )


class ValidateServiceRecovery(BaseTool):
    contract = ToolContract(
        name="validate_service_recovery",
        purpose="Validate resource health against a named validation policy after remediation",
        required_input=["resource_id", "validation_policy"],
        optional_input=["timeout_seconds"],
        authentication=AuthMethod.MANAGED_IDENTITY,
        timeout_seconds=120,
        retry_policy=RetryPolicy(max_attempts=2),
        allowed_roles=["OpsInvestigator", "OpsAdmin", "RemediationExecutor"],
        expected_output="passed bool, checks[], evidence",
        error_response="POLICY_UNKNOWN | VALIDATION_FAILED",
        audit_requirements="Always log validation outcome",
        idempotency="Read-only checks",
        production_restrictions="Must run after every remediation before success claim",
    )

    def execute(self, payload: dict[str, Any], *, correlation_id: str) -> ToolResult:
        policy = payload["validation_policy"]
        if data_mode() == "mock":
            checks = [
                {"name": "disk_free_pct", "value": 22.0, "threshold": 15.0, "passed": True},
                {"name": "mem_util_pct", "value": 71.0, "threshold": 90.0, "passed": True},
                {"name": "vpn_packet_loss_pct", "value": 0.2, "threshold": 1.0, "passed": True},
                {"name": "teams_crash_count_15m", "value": 0, "threshold": 1, "passed": True},
            ]
            return ToolResult(
                ok=True,
                tool=self.contract.name,
                data_mode="mock",
                data={"passed": all(c["passed"] for c in checks), "checks": checks, "policy": policy},
            )
        return ToolResult(
            ok=False,
            tool=self.contract.name,
            data_mode="unavailable",
            error_code="NOT_CONFIGURED",
            error_message="Live validation probes not configured",
        )


class CreateOrUpdateServiceNowIncident(BaseTool):
    contract = ToolContract(
        name="create_or_update_servicenow_incident",
        purpose="Create or update a ServiceNow incident using correlation id for idempotency",
        required_input=["payload"],
        optional_input=[],
        authentication=AuthMethod.OAUTH_CLIENT_CREDENTIALS,
        timeout_seconds=30,
        retry_policy=RetryPolicy(),
        allowed_roles=["OpsInvestigator", "OpsAdmin"],
        expected_output="number from API, sys_id, state",
        error_response="NOT_CONFIGURED | UPSTREAM_ERROR",
        audit_requirements="Log correlation_id and returned number only",
        idempotency="Upsert on payload.correlation_id",
        production_restrictions="Never fabricate incident numbers",
    )

    _local: dict[str, dict[str, Any]] = {}

    def execute(self, payload: dict[str, Any], *, correlation_id: str) -> ToolResult:
        body = payload["payload"]
        cid = body.get("correlation_id") or correlation_id
        if data_mode() == "mock":
            if cid in self._local:
                rec = self._local[cid]
                rec["state"] = body.get("state", rec["state"])
                rec["work_notes"] = body.get("work_notes", rec.get("work_notes"))
            else:
                # Deterministic mock number from correlation — still labeled mock
                rec = {
                    "number": f"INC{abs(hash(cid)) % 10_000_000:07d}",
                    "sys_id": idempotency_key(cid),
                    "state": body.get("state", "In Progress"),
                    "correlation_id": cid,
                    "data_mode": "mock",
                }
                self._local[cid] = rec
            return ToolResult(ok=True, tool=self.contract.name, data_mode="mock", data=rec)
        return ToolResult(
            ok=False,
            tool=self.contract.name,
            data_mode="unavailable",
            error_code="NOT_CONFIGURED",
            error_message="ServiceNow not configured",
        )


class SendTeamsNotification(BaseTool):
    contract = ToolContract(
        name="send_teams_notification",
        purpose="Send Teams message or Adaptive Card notification",
        required_input=["payload"],
        optional_input=[],
        authentication=AuthMethod.MANAGED_IDENTITY,
        timeout_seconds=20,
        retry_policy=RetryPolicy(),
        allowed_roles=["OpsInvestigator", "OpsAdmin"],
        expected_output="message_id / status",
        error_response="NOT_CONFIGURED | SEND_FAILURE",
        audit_requirements="Log channel/user id; redact secrets",
        idempotency="Idempotent on payload.idempotency_key",
        production_restrictions="No secrets or raw PII in cards",
    )

    def execute(self, payload: dict[str, Any], *, correlation_id: str) -> ToolResult:
        body = payload["payload"]
        if data_mode() == "mock":
            return ToolResult(
                ok=True,
                tool=self.contract.name,
                data_mode="mock",
                data={"status": "Sent", "message_id": f"msg-{idempotency_key(correlation_id)[:10]}", "preview": body.get("text", "")[:200]},
            )
        return ToolResult(
            ok=False,
            tool=self.contract.name,
            data_mode="unavailable",
            error_code="NOT_CONFIGURED",
            error_message="Teams webhook / Graph not configured",
        )


class WriteAuditEvent(BaseTool):
    contract = ToolContract(
        name="write_audit_event",
        purpose="Persist immutable operational audit event",
        required_input=["payload"],
        optional_input=[],
        authentication=AuthMethod.MANAGED_IDENTITY,
        timeout_seconds=10,
        retry_policy=RetryPolicy(max_attempts=3),
        allowed_roles=["OpsReader", "OpsInvestigator", "OpsAdmin", "RemediationExecutor", "PredictionService"],
        expected_output="event_id",
        error_response="WRITE_FAILURE",
        audit_requirements="Self-auditing store",
        idempotency="Idempotent on payload.event_id if provided",
        production_restrictions="No secret values in payload",
    )

    events: list[dict[str, Any]] = []

    def execute(self, payload: dict[str, Any], *, correlation_id: str) -> ToolResult:
        body = dict(payload["payload"])
        body.setdefault("event_id", f"aud-{idempotency_key(correlation_id, str(len(self.events)))[:12]}")
        body.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        body["correlation_id"] = correlation_id
        self.events.append(body)
        return ToolResult(ok=True, tool=self.contract.name, data={"event_id": body["event_id"]})


def build_default_registry(audit_sink=None) -> "ToolRegistry":
    from .base import ToolRegistry

    registry = ToolRegistry()
    tools = [
        GetAzureResourceHealth(audit_sink=audit_sink),
        QueryLogAnalytics(audit_sink=audit_sink),
        GetAzureMonitorMetrics(audit_sink=audit_sink),
        GetRecentAzureChanges(audit_sink=audit_sink),
        GetServiceNowIncidents(audit_sink=audit_sink),
        PredictVmFailure(audit_sink=audit_sink),
        PredictEndpointIncident(audit_sink=audit_sink),
        GetApprovedRunbook(audit_sink=audit_sink),
        RequestHumanApproval(audit_sink=audit_sink),
        ExecuteApprovedRemediation(audit_sink=audit_sink),
        ValidateServiceRecovery(audit_sink=audit_sink),
        CreateOrUpdateServiceNowIncident(audit_sink=audit_sink),
        SendTeamsNotification(audit_sink=audit_sink),
        WriteAuditEvent(audit_sink=audit_sink),
    ]
    for t in tools:
        registry.register(t)
    return registry
