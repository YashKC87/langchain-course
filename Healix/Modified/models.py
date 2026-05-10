# ============================================================
#  HEALIX Models — models.py
#  Pydantic request/response models for all API endpoints.
# ============================================================

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


# ── Existing models (moved from main.py) ────────────────────

class ChatRequest(BaseModel):
    question: str
    endpoint_context: Optional[str] = None

class RemediationRequest(BaseModel):
    endpoint_id: str
    issue_type: str


# ── Log models ──────────────────────────────────────────────

class LogEntry(BaseModel):
    timestamp: Optional[str] = None
    source: Optional[str] = None
    source_service: Optional[str] = None
    severity: str = "info"
    category: Optional[str] = None
    endpoint_name: Optional[str] = None
    message: str
    raw_data: Optional[Dict[str, Any]] = None

class LogIngestRequest(BaseModel):
    source: str
    entries: List[LogEntry]

class LogQueryRequest(BaseModel):
    query: str
    hours: int = 24
    limit: int = 200

class SyslogIngestRequest(BaseModel):
    raw: str


# ── Alert models ────────────────────────────────────────────

class AlertRuleCreateRequest(BaseModel):
    name: str
    description: str = ""
    source: str  # "log_query", "metric_threshold", "defender_severity"
    condition_json: Dict[str, Any]
    severity: str = "warning"
    delivery_channels: List[str] = Field(default_factory=lambda: ["dashboard"])
    cooldown_minutes: int = 15

class AlertRuleUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None
    condition_json: Optional[Dict[str, Any]] = None
    severity: Optional[str] = None
    delivery_channels: Optional[List[str]] = None
    cooldown_minutes: Optional[int] = None
    enabled: Optional[bool] = None

class AlertResolveRequest(BaseModel):
    resolved_by: str = "manual"


# ── Microsoft integration models ────────────────────────────

class KQLQueryRequest(BaseModel):
    query: str
    timespan: str = "P1D"

class DeviceActionRequest(BaseModel):
    action: str  # "rebootNow", "remoteLock", "syncDevice", "windowsDefenderScan"

class IncidentUpdateRequest(BaseModel):
    status: str  # "active", "resolved", "redirected"
    classification: Optional[str] = None
    comment: Optional[str] = None


# ── Workflow models ─────────────────────────────────────────

class WorkflowTriageRequest(BaseModel):
    incident_id: str
    source: str = "defender"

class WorkflowMitigateRequest(BaseModel):
    action_type: str  # "isolate_device", "disable_user", "block_ip", "restart_service"
    target_id: str
    target_type: str = "device"  # "device", "user", "ip"
    reason: str = ""

class WorkflowRuleCreateRequest(BaseModel):
    name: str
    trigger: str  # "new_critical_alert", "defender_incident", "compliance_failure"
    conditions: Dict[str, Any] = Field(default_factory=dict)
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    enabled: bool = True
