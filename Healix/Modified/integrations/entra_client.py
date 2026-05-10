# ============================================================
#  HEALIX Entra Client — integrations/entra_client.py
#  Microsoft Entra ID (Azure AD) integration.
#  Identity risk, sign-in logs, conditional access.
# ============================================================

import logging
from typing import Optional, List, Dict
from datetime import datetime, timezone, timedelta

from integrations.base_client import MicrosoftBaseClient

logger = logging.getLogger("healix.entra")


class EntraClient(MicrosoftBaseClient):
    """Microsoft Entra ID API client via Microsoft Graph."""

    async def get_risky_users(self, risk_level: Optional[str] = None,
                              top: int = 50) -> List[Dict]:
        """List risky users from Entra Identity Protection."""
        if not self.is_available:
            return self._demo_risky_users()

        params = {"$top": top, "$orderby": "riskLastUpdatedDateTime desc"}
        if risk_level:
            params["$filter"] = f"riskLevel eq '{risk_level}'"

        result = await self._get("/identityProtection/riskyUsers", params=params)
        if result and "value" in result:
            return result["value"]
        return self._demo_risky_users()

    async def get_risk_detections(self, top: int = 50) -> List[Dict]:
        """List risk detection events."""
        if not self.is_available:
            return self._demo_risk_detections()

        params = {"$top": top, "$orderby": "detectedDateTime desc"}
        result = await self._get("/identityProtection/riskDetections", params=params)
        if result and "value" in result:
            return result["value"]
        return self._demo_risk_detections()

    async def get_sign_in_logs(self, top: int = 100,
                               filter_str: Optional[str] = None) -> List[Dict]:
        """List sign-in logs from Entra audit."""
        if not self.is_available:
            return self._demo_sign_in_logs()

        params = {"$top": top, "$orderby": "createdDateTime desc"}
        if filter_str:
            params["$filter"] = filter_str

        result = await self._get("/auditLogs/signIns", params=params)
        if result and "value" in result:
            return result["value"]
        return self._demo_sign_in_logs()

    async def get_conditional_access_policies(self) -> List[Dict]:
        """List Conditional Access policies."""
        if not self.is_available:
            return self._demo_ca_policies()

        result = await self._get("/identity/conditionalAccess/policies")
        if result and "value" in result:
            return result["value"]
        return self._demo_ca_policies()

    async def get_directory_audit_logs(self, top: int = 50) -> List[Dict]:
        """List directory audit logs."""
        if not self.is_available:
            return self._demo_audit_logs()

        params = {"$top": top, "$orderby": "activityDateTime desc"}
        result = await self._get("/auditLogs/directoryAudits", params=params)
        if result and "value" in result:
            return result["value"]
        return self._demo_audit_logs()

    async def get_mfa_registration_status(self) -> Dict:
        """Get MFA registration statistics."""
        if not self.is_available:
            return self._demo_mfa_status()

        result = await self._get(
            "/reports/authenticationMethods/userRegistrationDetails",
            params={"$top": 999}
        )
        if result and "value" in result:
            users = result["value"]
            total = len(users)
            mfa_registered = sum(1 for u in users if u.get("isMfaRegistered", False))
            return {
                "totalUsers": total,
                "mfaRegistered": mfa_registered,
                "mfaRate": f"{(mfa_registered / total * 100):.1f}%" if total > 0 else "N/A",
                "methodsRegistered": self._count_methods(users),
            }
        return self._demo_mfa_status()

    @staticmethod
    def _count_methods(users: List[Dict]) -> Dict:
        methods = {}
        for u in users:
            for m in u.get("methodsRegistered", []):
                methods[m] = methods.get(m, 0) + 1
        return methods

    # ── Demo data ───────────────────────────────────────────────

    def _demo_risky_users(self) -> List[Dict]:
        now = datetime.now(timezone.utc)
        return [
            {
                "id": "user-001",
                "userDisplayName": "John Doe",
                "userPrincipalName": "john.doe@contoso.com",
                "riskLevel": "high",
                "riskState": "atRisk",
                "riskDetail": "adminConfirmedCompromised",
                "riskLastUpdatedDateTime": (now - timedelta(hours=1)).isoformat(),
                "_demo": True,
            },
            {
                "id": "user-002",
                "userDisplayName": "Jane Smith",
                "userPrincipalName": "jane.smith@contoso.com",
                "riskLevel": "medium",
                "riskState": "atRisk",
                "riskDetail": "suspiciousActivity",
                "riskLastUpdatedDateTime": (now - timedelta(hours=4)).isoformat(),
                "_demo": True,
            },
            {
                "id": "user-003",
                "userDisplayName": "Service Account SVC-01",
                "userPrincipalName": "svc01@contoso.com",
                "riskLevel": "low",
                "riskState": "atRisk",
                "riskDetail": "unfamiliarFeatures",
                "riskLastUpdatedDateTime": (now - timedelta(hours=8)).isoformat(),
                "_demo": True,
            },
        ]

    def _demo_risk_detections(self) -> List[Dict]:
        now = datetime.now(timezone.utc)
        return [
            {
                "id": "det-001",
                "riskEventType": "impossibleTravel",
                "riskLevel": "high",
                "riskState": "atRisk",
                "userDisplayName": "John Doe",
                "userPrincipalName": "john.doe@contoso.com",
                "ipAddress": "203.0.113.50",
                "location": {"city": "Moscow", "countryOrRegion": "RU"},
                "detectedDateTime": (now - timedelta(hours=2)).isoformat(),
                "activityType": "signin",
                "_demo": True,
            },
            {
                "id": "det-002",
                "riskEventType": "anonymizedIPAddress",
                "riskLevel": "medium",
                "riskState": "atRisk",
                "userDisplayName": "Jane Smith",
                "userPrincipalName": "jane.smith@contoso.com",
                "ipAddress": "198.51.100.1",
                "location": {"city": "Unknown", "countryOrRegion": "XX"},
                "detectedDateTime": (now - timedelta(hours=5)).isoformat(),
                "activityType": "signin",
                "_demo": True,
            },
            {
                "id": "det-003",
                "riskEventType": "maliciousIPAddress",
                "riskLevel": "medium",
                "riskState": "atRisk",
                "userDisplayName": "Service Account SVC-01",
                "userPrincipalName": "svc01@contoso.com",
                "ipAddress": "192.0.2.100",
                "location": {"city": "Beijing", "countryOrRegion": "CN"},
                "detectedDateTime": (now - timedelta(hours=6)).isoformat(),
                "activityType": "signin",
                "_demo": True,
            },
        ]

    def _demo_sign_in_logs(self) -> List[Dict]:
        now = datetime.now(timezone.utc)
        return [
            {
                "id": "signin-001",
                "userDisplayName": "John Doe",
                "userPrincipalName": "john.doe@contoso.com",
                "appDisplayName": "Microsoft 365",
                "ipAddress": "10.0.1.50",
                "clientAppUsed": "Browser",
                "status": {"errorCode": 0, "failureReason": None},
                "conditionalAccessStatus": "success",
                "riskLevelAggregated": "none",
                "createdDateTime": (now - timedelta(minutes=15)).isoformat(),
                "location": {"city": "Seattle", "countryOrRegion": "US"},
                "_demo": True,
            },
            {
                "id": "signin-002",
                "userDisplayName": "Jane Smith",
                "userPrincipalName": "jane.smith@contoso.com",
                "appDisplayName": "Azure Portal",
                "ipAddress": "198.51.100.1",
                "clientAppUsed": "Browser",
                "status": {"errorCode": 50126, "failureReason": "Invalid credentials"},
                "conditionalAccessStatus": "failure",
                "riskLevelAggregated": "medium",
                "createdDateTime": (now - timedelta(minutes=30)).isoformat(),
                "location": {"city": "Unknown", "countryOrRegion": "XX"},
                "_demo": True,
            },
            {
                "id": "signin-003",
                "userDisplayName": "Admin Account",
                "userPrincipalName": "admin@contoso.com",
                "appDisplayName": "Microsoft Graph",
                "ipAddress": "10.0.1.10",
                "clientAppUsed": "Mobile App",
                "status": {"errorCode": 0, "failureReason": None},
                "conditionalAccessStatus": "success",
                "riskLevelAggregated": "none",
                "createdDateTime": (now - timedelta(hours=1)).isoformat(),
                "location": {"city": "Redmond", "countryOrRegion": "US"},
                "_demo": True,
            },
        ]

    def _demo_ca_policies(self) -> List[Dict]:
        return [
            {
                "id": "ca-001",
                "displayName": "Require MFA for all users",
                "state": "enabled",
                "conditions": {"users": {"includeUsers": ["All"]}},
                "grantControls": {"builtInControls": ["mfa"]},
                "_demo": True,
            },
            {
                "id": "ca-002",
                "displayName": "Block legacy authentication",
                "state": "enabled",
                "conditions": {"clientAppTypes": ["exchangeActiveSync", "other"]},
                "grantControls": {"builtInControls": ["block"]},
                "_demo": True,
            },
            {
                "id": "ca-003",
                "displayName": "Require compliant device for sensitive apps",
                "state": "enabledForReportingButNotEnforced",
                "conditions": {"applications": {"includeApplications": ["Office365"]}},
                "grantControls": {"builtInControls": ["compliantDevice"]},
                "_demo": True,
            },
        ]

    def _demo_audit_logs(self) -> List[Dict]:
        now = datetime.now(timezone.utc)
        return [
            {
                "id": "audit-001",
                "activityDisplayName": "Add member to role",
                "activityDateTime": (now - timedelta(hours=2)).isoformat(),
                "initiatedBy": {"user": {"displayName": "Admin", "userPrincipalName": "admin@contoso.com"}},
                "targetResources": [{"displayName": "Global Administrator", "type": "Role"}],
                "result": "success",
                "_demo": True,
            },
            {
                "id": "audit-002",
                "activityDisplayName": "Update conditional access policy",
                "activityDateTime": (now - timedelta(hours=6)).isoformat(),
                "initiatedBy": {"user": {"displayName": "Security Admin"}},
                "targetResources": [{"displayName": "Require MFA for all users", "type": "Policy"}],
                "result": "success",
                "_demo": True,
            },
        ]

    def _demo_mfa_status(self) -> Dict:
        return {
            "totalUsers": 150,
            "mfaRegistered": 128,
            "mfaRate": "85.3%",
            "methodsRegistered": {
                "microsoftAuthenticator": 95,
                "phoneAuthentication": 45,
                "fido2": 12,
                "email": 30,
            },
            "_demo": True,
        }
