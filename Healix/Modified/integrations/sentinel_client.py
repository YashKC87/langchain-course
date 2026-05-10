# ============================================================
#  HEALIX Sentinel Client — integrations/sentinel_client.py
#  Microsoft Sentinel / Log Analytics integration.
#  Queries logs via KQL, ingests custom logs.
# ============================================================

import logging
from typing import Optional, List, Dict
from datetime import datetime, timezone, timedelta

from integrations.base_client import MicrosoftBaseClient

logger = logging.getLogger("healix.sentinel")


class SentinelClient(MicrosoftBaseClient):
    """Microsoft Sentinel / Log Analytics API client."""

    LOG_ANALYTICS_BASE = "https://api.loganalytics.io/v1"
    ARM_BASE = "https://management.azure.com"
    SCOPE = "https://api.loganalytics.io/.default"

    def __init__(self, tenant_id: str, client_id: str, client_secret: str,
                 workspace_id: str = "", subscription_id: str = "",
                 resource_group: str = ""):
        super().__init__(tenant_id, client_id, client_secret)
        self.workspace_id = workspace_id
        self.subscription_id = subscription_id
        self.resource_group = resource_group

    @property
    def is_workspace_configured(self) -> bool:
        return bool(self.workspace_id)

    async def query_logs(self, kql: str, timespan: str = "P1D") -> Optional[Dict]:
        """Execute a KQL query against the Log Analytics workspace."""
        if not self.is_available or not self.workspace_id:
            return self._demo_query_result(kql)

        url = f"{self.LOG_ANALYTICS_BASE}/workspaces/{self.workspace_id}/query"
        result = await self._request(
            "POST", url,
            scope="https://api.loganalytics.io/.default",
            json_body={"query": kql, "timespan": timespan}
        )
        return result or self._demo_query_result(kql)

    async def get_sentinel_incidents(self, top: int = 50) -> List[Dict]:
        """List Sentinel incidents via Azure Resource Manager API."""
        if not self.is_available or not self.subscription_id:
            return self._demo_sentinel_incidents()

        path = (f"/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}"
                f"/providers/Microsoft.OperationalInsights/workspaces/{self.workspace_id}"
                f"/providers/Microsoft.SecurityInsights/incidents")
        params = {"api-version": "2023-11-01", "$top": top, "$orderby": "properties/createdTimeUtc desc"}

        result = await self._request(
            "GET", f"{self.ARM_BASE}{path}",
            scope="https://management.azure.com/.default",
            params=params
        )
        if result and "value" in result:
            return result["value"]
        return self._demo_sentinel_incidents()

    async def get_alert_rules(self) -> List[Dict]:
        """List configured Sentinel analytics rules."""
        if not self.is_available or not self.subscription_id:
            return self._demo_alert_rules()

        path = (f"/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}"
                f"/providers/Microsoft.OperationalInsights/workspaces/{self.workspace_id}"
                f"/providers/Microsoft.SecurityInsights/alertRules")
        params = {"api-version": "2023-11-01"}

        result = await self._request(
            "GET", f"{self.ARM_BASE}{path}",
            scope="https://management.azure.com/.default",
            params=params
        )
        if result and "value" in result:
            return result["value"]
        return self._demo_alert_rules()

    async def query_security_events(self, timespan: str = "PT1H") -> List[Dict]:
        """Pre-built KQL: SecurityEvent summary by EventID and Computer."""
        kql = """SecurityEvent
| where TimeGenerated > ago(1h)
| summarize Count=count() by EventID, Computer, Activity
| top 20 by Count desc"""
        result = await self.query_logs(kql, timespan)
        return self._extract_rows(result)

    async def query_syslog(self, severity: str = "err", timespan: str = "PT1H") -> List[Dict]:
        """Pre-built KQL: Syslog entries filtered by severity."""
        kql = f"""Syslog
| where TimeGenerated > ago(1h)
| where SeverityLevel == "{severity}"
| project TimeGenerated, Computer, Facility, SeverityLevel, SyslogMessage
| top 50 by TimeGenerated desc"""
        result = await self.query_logs(kql, timespan)
        return self._extract_rows(result)

    async def query_heartbeat(self) -> List[Dict]:
        """Pre-built KQL: Agent connectivity status via Heartbeat table."""
        kql = """Heartbeat
| summarize LastCall=max(TimeGenerated), Version=any(Version), OSType=any(OSType),
  ComputerEnvironment=any(ComputerEnvironment), ResourceGroup=any(ResourceGroup)
  by Computer
| extend Status = iff(LastCall > ago(5m), 'Connected', iff(LastCall > ago(30m), 'Degraded', 'Disconnected'))
| project Computer, LastCall, Status, OSType, Version, ComputerEnvironment, ResourceGroup
| order by Status asc, LastCall desc"""
        result = await self.query_logs(kql, "PT1H")
        return self._extract_rows(result)

    async def query_performance(self, timespan: str = "PT4H") -> List[Dict]:
        """Pre-built KQL: Performance counters (CPU, Memory, Disk)."""
        kql = """Perf
| where TimeGenerated > ago(4h)
| where ObjectName in ("Processor", "Memory", "LogicalDisk")
| where CounterName in ("% Processor Time", "% Used Memory", "% Free Space")
| summarize AvgValue=avg(CounterValue) by Computer, ObjectName, CounterName, bin(TimeGenerated, 5m)
| order by TimeGenerated desc"""
        result = await self.query_logs(kql, timespan)
        return self._extract_rows(result)

    def _extract_rows(self, result: Optional[Dict]) -> List[Dict]:
        """Convert Log Analytics query result into list of dicts."""
        if not result:
            return []
        if "_demo" in result:
            return result.get("rows", [])
        tables = result.get("tables", [])
        if not tables:
            return []
        table = tables[0]
        columns = [c["name"] for c in table.get("columns", [])]
        rows = []
        for row in table.get("rows", []):
            rows.append(dict(zip(columns, row)))
        return rows

    # ── Demo data ───────────────────────────────────────────────

    def _demo_query_result(self, kql: str) -> Dict:
        now = datetime.now(timezone.utc)
        return {
            "tables": [{
                "name": "PrimaryResult",
                "columns": [
                    {"name": "TimeGenerated", "type": "datetime"},
                    {"name": "Computer", "type": "string"},
                    {"name": "Category", "type": "string"},
                    {"name": "Message", "type": "string"},
                ],
                "rows": [
                    [(now - timedelta(minutes=5)).isoformat(), "PROD-SRV-01", "Security", "Failed logon attempt from 192.168.1.100"],
                    [(now - timedelta(minutes=10)).isoformat(), "EDGE-NODE-07", "Performance", "CPU threshold exceeded: 97%"],
                    [(now - timedelta(minutes=15)).isoformat(), "DB-CLUSTER-01", "Security", "Privilege escalation attempt blocked"],
                    [(now - timedelta(minutes=22)).isoformat(), "PROD-SRV-02", "System", "Service W3SVC stopped unexpectedly"],
                    [(now - timedelta(minutes=30)).isoformat(), "BACKUP-SRV", "Audit", "Backup job completed successfully"],
                ],
            }],
            "_demo": True,
            "_query": kql,
        }

    def _demo_sentinel_incidents(self) -> List[Dict]:
        now = datetime.now(timezone.utc)
        return [
            {
                "id": "SENT-001",
                "name": "SENT-001",
                "properties": {
                    "title": "Brute force SSH attack detected",
                    "severity": "High",
                    "status": "Active",
                    "createdTimeUtc": (now - timedelta(hours=3)).isoformat(),
                    "alertsCount": 12,
                    "owner": {"assignedTo": "SOC Team"},
                },
            },
            {
                "id": "SENT-002",
                "name": "SENT-002",
                "properties": {
                    "title": "Anomalous sign-in activity from Tor exit node",
                    "severity": "Medium",
                    "status": "Active",
                    "createdTimeUtc": (now - timedelta(hours=5)).isoformat(),
                    "alertsCount": 3,
                    "owner": {"assignedTo": "Unassigned"},
                },
            },
        ]

    def _demo_alert_rules(self) -> List[Dict]:
        return [
            {
                "id": "rule-001",
                "name": "Failed SSH Logins",
                "properties": {
                    "displayName": "Multiple failed SSH logon attempts",
                    "enabled": True,
                    "severity": "Medium",
                    "query": "Syslog | where Facility == 'auth' | where SyslogMessage contains 'Failed'",
                    "queryFrequency": "PT5M",
                    "triggerThreshold": 10,
                },
            },
            {
                "id": "rule-002",
                "name": "High Severity Alerts",
                "properties": {
                    "displayName": "SecurityAlert with high severity",
                    "enabled": True,
                    "severity": "High",
                    "query": "SecurityAlert | where AlertSeverity == 'High'",
                    "queryFrequency": "PT5M",
                    "triggerThreshold": 1,
                },
            },
        ]
