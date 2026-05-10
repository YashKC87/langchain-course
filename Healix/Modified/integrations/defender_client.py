# ============================================================
#  HEALIX Defender Client — integrations/defender_client.py
#  Microsoft Defender XDR integration for threat detection,
#  security incidents, alerts, and threat hunting.
# ============================================================

import logging
from typing import Optional, List, Dict
from datetime import datetime, timezone, timedelta

from integrations.base_client import MicrosoftBaseClient

logger = logging.getLogger("healix.defender")


class DefenderClient(MicrosoftBaseClient):
    """Microsoft Defender XDR API client."""

    async def get_incidents(self, top: int = 50, status: Optional[str] = None) -> List[Dict]:
        """List security incidents from Defender XDR."""
        if not self.is_available:
            return self._demo_incidents()

        params = {"$top": top, "$orderby": "createdDateTime desc"}
        if status:
            params["$filter"] = f"status eq '{status}'"

        result = await self._get("/security/incidents", params=params)
        if result and "value" in result:
            return result["value"]
        return self._demo_incidents()

    async def get_incident_details(self, incident_id: str) -> Optional[Dict]:
        """Get detailed information about a specific incident."""
        if not self.is_available:
            return self._demo_incident_detail(incident_id)

        result = await self._get(f"/security/incidents/{incident_id}")
        return result or self._demo_incident_detail(incident_id)

    async def get_security_alerts(self, severity: Optional[str] = None,
                                  top: int = 100) -> List[Dict]:
        """List security alerts from Defender."""
        if not self.is_available:
            return self._demo_alerts()

        params = {"$top": top, "$orderby": "createdDateTime desc"}
        if severity:
            params["$filter"] = f"severity eq '{severity}'"

        result = await self._get("/security/alerts_v2", params=params)
        if result and "value" in result:
            return result["value"]
        return self._demo_alerts()

    async def run_hunting_query(self, kql_query: str) -> Optional[Dict]:
        """Execute an advanced threat hunting query (KQL)."""
        if not self.is_available:
            return self._demo_hunting_result(kql_query)

        result = await self._post("/security/runHuntingQuery", json_body={"Query": kql_query})
        return result or self._demo_hunting_result(kql_query)

    async def get_secure_score(self) -> Optional[Dict]:
        """Get Microsoft Secure Score."""
        if not self.is_available:
            return self._demo_secure_score()

        result = await self._get("/security/secureScores", params={"$top": 1})
        if result and "value" in result and len(result["value"]) > 0:
            return result["value"][0]
        return self._demo_secure_score()

    async def update_incident_status(self, incident_id: str, status: str,
                                     classification: Optional[str] = None,
                                     comment: Optional[str] = None) -> Optional[Dict]:
        """Update incident status and classification."""
        if not self.is_available:
            return {"status": "demo_mode", "message": "Incident update simulated"}

        body = {"status": status}
        if classification:
            body["classification"] = classification
        if comment:
            body["customTags"] = [comment]

        return await self._patch(f"/security/incidents/{incident_id}", json_body=body)

    # ── Demo data for when API is unavailable ───────────────────

    def _demo_incidents(self) -> List[Dict]:
        now = datetime.now(timezone.utc)
        return [
            {
                "id": "INC-2024-001",
                "displayName": "Multi-stage attack involving phishing and lateral movement",
                "severity": "high",
                "status": "active",
                "classification": "truePositive",
                "createdDateTime": (now - timedelta(hours=2)).isoformat(),
                "lastUpdateDateTime": (now - timedelta(minutes=30)).isoformat(),
                "assignedTo": "Security Team",
                "alertCount": 5,
                "incidentWebUrl": "https://security.microsoft.com/incidents/INC-2024-001",
                "alerts": [
                    {"title": "Suspicious email with malicious attachment", "severity": "medium"},
                    {"title": "Credential harvesting page detected", "severity": "high"},
                    {"title": "Lateral movement using stolen credentials", "severity": "high"},
                ],
            },
            {
                "id": "INC-2024-002",
                "displayName": "Suspicious sign-in from unfamiliar location",
                "severity": "medium",
                "status": "active",
                "classification": "unknown",
                "createdDateTime": (now - timedelta(hours=6)).isoformat(),
                "lastUpdateDateTime": (now - timedelta(hours=1)).isoformat(),
                "assignedTo": "Unassigned",
                "alertCount": 2,
                "incidentWebUrl": "https://security.microsoft.com/incidents/INC-2024-002",
                "alerts": [
                    {"title": "Sign-in from anonymous IP address", "severity": "medium"},
                    {"title": "Impossible travel activity", "severity": "medium"},
                ],
            },
            {
                "id": "INC-2024-003",
                "displayName": "Ransomware activity detected on endpoint",
                "severity": "high",
                "status": "resolved",
                "classification": "truePositive",
                "createdDateTime": (now - timedelta(days=1)).isoformat(),
                "lastUpdateDateTime": (now - timedelta(hours=12)).isoformat(),
                "assignedTo": "Security Team",
                "alertCount": 8,
                "incidentWebUrl": "https://security.microsoft.com/incidents/INC-2024-003",
                "alerts": [
                    {"title": "Ransomware behavior detected", "severity": "high"},
                    {"title": "Mass file encryption", "severity": "high"},
                ],
            },
            {
                "id": "INC-2024-004",
                "displayName": "Brute force attack on service account",
                "severity": "low",
                "status": "active",
                "classification": "unknown",
                "createdDateTime": (now - timedelta(hours=4)).isoformat(),
                "lastUpdateDateTime": (now - timedelta(hours=3)).isoformat(),
                "assignedTo": "Unassigned",
                "alertCount": 1,
                "incidentWebUrl": "https://security.microsoft.com/incidents/INC-2024-004",
                "alerts": [
                    {"title": "Multiple failed sign-in attempts", "severity": "low"},
                ],
            },
        ]

    def _demo_incident_detail(self, incident_id: str) -> Dict:
        incidents = self._demo_incidents()
        for inc in incidents:
            if inc["id"] == incident_id:
                inc["comments"] = [
                    {"comment": "Initial triage started", "createdBy": "HEALIX Auto-Triage"},
                ]
                return inc
        return incidents[0] if incidents else {}

    def _demo_alerts(self) -> List[Dict]:
        now = datetime.now(timezone.utc)
        return [
            {
                "id": "AL-001",
                "title": "Suspicious PowerShell execution",
                "severity": "high",
                "status": "new",
                "category": "Execution",
                "createdDateTime": (now - timedelta(hours=1)).isoformat(),
                "description": "PowerShell executed with encoded command on PROD-SRV-01",
                "machineName": "PROD-SRV-01",
                "userPrincipalName": "admin@contoso.com",
            },
            {
                "id": "AL-002",
                "title": "Malicious URL clicked in email",
                "severity": "medium",
                "status": "inProgress",
                "category": "InitialAccess",
                "createdDateTime": (now - timedelta(hours=3)).isoformat(),
                "description": "User clicked a known phishing link in email message",
                "machineName": "DEV-WS-015",
                "userPrincipalName": "user01@contoso.com",
            },
            {
                "id": "AL-003",
                "title": "Data exfiltration detected",
                "severity": "high",
                "status": "new",
                "category": "Exfiltration",
                "createdDateTime": (now - timedelta(minutes=45)).isoformat(),
                "description": "Large volume of data transferred to external endpoint",
                "machineName": "EDGE-NODE-07",
                "userPrincipalName": "service_account@contoso.com",
            },
            {
                "id": "AL-004",
                "title": "Privilege escalation attempt",
                "severity": "medium",
                "status": "new",
                "category": "PrivilegeEscalation",
                "createdDateTime": (now - timedelta(hours=2)).isoformat(),
                "description": "Attempt to add user to privileged group detected",
                "machineName": "DB-CLUSTER-01",
                "userPrincipalName": "user02@contoso.com",
            },
            {
                "id": "AL-005",
                "title": "Suspicious file modification",
                "severity": "low",
                "status": "resolved",
                "category": "DefenseEvasion",
                "createdDateTime": (now - timedelta(hours=8)).isoformat(),
                "description": "System file modified outside of maintenance window",
                "machineName": "BACKUP-SRV",
                "userPrincipalName": "admin@contoso.com",
            },
        ]

    def _demo_hunting_result(self, query: str) -> Dict:
        return {
            "schema": [
                {"Name": "Timestamp", "Type": "DateTime"},
                {"Name": "DeviceName", "Type": "String"},
                {"Name": "ActionType", "Type": "String"},
                {"Name": "FileName", "Type": "String"},
            ],
            "results": [
                {"Timestamp": self._now_iso(), "DeviceName": "PROD-SRV-01",
                 "ActionType": "ProcessCreated", "FileName": "powershell.exe"},
                {"Timestamp": self._now_iso(), "DeviceName": "EDGE-NODE-07",
                 "ActionType": "FileModified", "FileName": "config.sys"},
            ],
            "_demo": True,
            "_query": query,
        }

    def _demo_secure_score(self) -> Dict:
        return {
            "currentScore": 68.5,
            "maxScore": 100,
            "averageComparativeScores": [
                {"basis": "AllTenants", "averageScore": 52.3},
                {"basis": "TotalSeats", "averageScore": 58.1},
            ],
            "controlScores": [
                {"controlName": "MFARegistrationV2", "score": 9.0, "maxScore": 10.0, "description": "Multi-factor authentication"},
                {"controlName": "AdminMFAV2", "score": 10.0, "maxScore": 10.0, "description": "Require MFA for admin roles"},
                {"controlName": "BlockLegacyAuthentication", "score": 8.0, "maxScore": 8.0, "description": "Block legacy authentication"},
                {"controlName": "SigninRiskPolicy", "score": 0.0, "maxScore": 6.0, "description": "Sign-in risk policy"},
                {"controlName": "UserRiskPolicy", "score": 0.0, "maxScore": 6.0, "description": "User risk policy"},
                {"controlName": "IntuneMDMEnrollment", "score": 5.0, "maxScore": 10.0, "description": "MDM enrollment"},
            ],
            "_demo": True,
        }
