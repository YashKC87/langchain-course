# ============================================================
#  HEALIX Compliance Engine — engines/compliance_engine.py
#  Security posture assessment and compliance gap analysis.
# ============================================================

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict

logger = logging.getLogger("healix.compliance")


class ComplianceEngine:
    """Assesses security posture across identity, device, data, and infrastructure."""

    def __init__(self, db, defender_client=None, intune_client=None,
                 entra_client=None, agent=None):
        self.db = db
        self.defender = defender_client
        self.intune = intune_client
        self.entra = entra_client
        self.agent = agent  # For RAG+LLM remediation suggestions

    async def run_full_assessment(self) -> Dict:
        """Execute all compliance checks and compute aggregate scores."""
        results = {
            "timestamp": _now(),
            "identity": await self.check_identity_risks(),
            "device": await self.check_device_compliance(),
            "security": await self.check_security_score(),
            "data": await self.check_data_governance(),
        }

        # Compute dimension scores
        identity_score = self._compute_identity_score(results["identity"])
        device_score = self._compute_device_score(results["device"])
        security_score = results["security"].get("score", 50)
        data_score = self._compute_data_score(results["data"])
        infrastructure_score = (identity_score + device_score + security_score) / 3

        overall = (identity_score * 0.25 + device_score * 0.25 +
                   security_score * 0.20 + data_score * 0.15 +
                   infrastructure_score * 0.15)

        scores = {
            "overall_score": round(overall, 1),
            "identity_score": round(identity_score, 1),
            "device_score": round(device_score, 1),
            "security_score": round(security_score, 1),
            "data_score": round(data_score, 1),
            "infrastructure_score": round(infrastructure_score, 1),
            "timestamp": _now(),
        }

        # Store snapshot for trend tracking
        await self.store_posture_snapshot(scores)

        return scores

    async def check_device_compliance(self) -> List[Dict]:
        """Query Intune for device compliance states."""
        findings = []

        if self.intune and self.intune.is_available:
            devices = await self.intune.list_managed_devices()
        else:
            devices = self._demo_device_findings()

        for d in devices:
            compliance = d.get("complianceState", "unknown")
            device_name = d.get("deviceName", "Unknown")

            if compliance != "compliant":
                finding = {
                    "check_type": "device_compliance",
                    "scope": f"device:{device_name}",
                    "check_name": f"Device compliance: {device_name}",
                    "status": "non_compliant",
                    "details": json.dumps({
                        "compliance_state": compliance,
                        "os": d.get("operatingSystem", ""),
                        "encrypted": d.get("isEncrypted", False),
                        "last_sync": d.get("lastSyncDateTime", ""),
                    }),
                    "remediation_suggestion": self._device_remediation(d),
                    "score": 30 if compliance == "noncompliant" else 50,
                }
                findings.append(finding)
                await self.db.insert_compliance_check(
                    timestamp=_now(), **finding
                )
            else:
                await self.db.insert_compliance_check(
                    timestamp=_now(),
                    check_type="device_compliance",
                    scope=f"device:{device_name}",
                    check_name=f"Device compliance: {device_name}",
                    status="compliant",
                    score=100,
                )

        return findings

    async def check_identity_risks(self) -> List[Dict]:
        """Query Entra for risky users, MFA gaps."""
        findings = []

        # Risky users
        if self.entra and self.entra.is_available:
            risky_users = await self.entra.get_risky_users()
            mfa_status = await self.entra.get_mfa_registration_status()
        else:
            risky_users = self._demo_risky_users()
            mfa_status = self._demo_mfa_status()

        for user in risky_users:
            risk_level = user.get("riskLevel", "none")
            if risk_level in ("high", "medium", "low"):
                finding = {
                    "check_type": "identity_risk",
                    "scope": f"user:{user.get('userPrincipalName', 'unknown')}",
                    "check_name": f"Risky user: {user.get('userDisplayName', 'Unknown')}",
                    "status": "non_compliant",
                    "details": json.dumps({
                        "risk_level": risk_level,
                        "risk_state": user.get("riskState", ""),
                        "risk_detail": user.get("riskDetail", ""),
                    }),
                    "remediation_suggestion": self._identity_remediation(user),
                    "score": {"high": 10, "medium": 40, "low": 70}.get(risk_level, 50),
                }
                findings.append(finding)
                await self.db.insert_compliance_check(timestamp=_now(), **finding)

        # MFA gaps
        mfa_rate_str = mfa_status.get("mfaRate", "0%")
        mfa_rate = float(mfa_rate_str.replace("%", "")) if mfa_rate_str != "N/A" else 0
        if mfa_rate < 100:
            finding = {
                "check_type": "identity_risk",
                "scope": "tenant",
                "check_name": "MFA registration coverage",
                "status": "non_compliant" if mfa_rate < 90 else "compliant",
                "details": json.dumps(mfa_status),
                "remediation_suggestion": f"MFA coverage is {mfa_rate}%. Target 100% by enforcing MFA via Conditional Access policy.",
                "score": mfa_rate,
            }
            findings.append(finding)
            await self.db.insert_compliance_check(timestamp=_now(), **finding)

        return findings

    async def check_security_score(self) -> Dict:
        """Fetch Microsoft Secure Score from Defender."""
        if self.defender and self.defender.is_available:
            score_data = await self.defender.get_secure_score()
        else:
            score_data = self._demo_secure_score()

        current = score_data.get("currentScore", 0)
        max_score = score_data.get("maxScore", 100)
        percentage = (current / max_score * 100) if max_score > 0 else 0

        controls = score_data.get("controlScores", [])
        improvement_actions = []
        for ctrl in controls:
            if ctrl.get("score", 0) < ctrl.get("maxScore", 0):
                improvement_actions.append({
                    "control": ctrl.get("controlName", ""),
                    "description": ctrl.get("description", ""),
                    "current": ctrl.get("score", 0),
                    "max": ctrl.get("maxScore", 0),
                    "gap": ctrl.get("maxScore", 0) - ctrl.get("score", 0),
                })

        return {
            "score": round(percentage, 1),
            "current": current,
            "max": max_score,
            "improvement_actions": sorted(improvement_actions, key=lambda x: x["gap"], reverse=True),
        }

    async def check_data_governance(self) -> List[Dict]:
        """Check data protection status. Returns findings for gaps."""
        # Basic data governance checks (expandable with DLP/sensitivity labels)
        findings = []

        # Check for unencrypted devices
        if self.intune and self.intune.is_available:
            devices = await self.intune.list_managed_devices()
        else:
            devices = self._demo_device_findings()

        unencrypted = [d for d in devices if not d.get("isEncrypted", True)]
        if unencrypted:
            finding = {
                "check_type": "data_governance",
                "scope": "tenant",
                "check_name": "Device encryption",
                "status": "non_compliant",
                "details": json.dumps({
                    "unencrypted_devices": [d.get("deviceName") for d in unencrypted],
                    "count": len(unencrypted),
                }),
                "remediation_suggestion": f"{len(unencrypted)} devices lack disk encryption. Enable BitLocker (Windows) or LUKS (Linux) via Intune configuration profile.",
                "score": max(0, 100 - len(unencrypted) * 20),
            }
            findings.append(finding)
            await self.db.insert_compliance_check(timestamp=_now(), **finding)

        return findings

    async def get_remediation_suggestions(self, findings: List[Dict]) -> List[Dict]:
        """Use RAG+LLM to generate remediation suggestions for compliance findings."""
        suggestions = []
        for finding in findings:
            suggestion = {
                "finding": finding.get("check_name", ""),
                "status": finding.get("status", ""),
                "remediation": finding.get("remediation_suggestion", ""),
                "priority": "high" if finding.get("score", 100) < 50 else "medium",
            }

            # Enhance with AI if agent is available
            if self.agent and not getattr(self.agent, '_demo_mode', True):
                try:
                    response = await self.agent.ask(
                        question=f"Provide remediation steps for: {finding.get('check_name', '')}. "
                                 f"Details: {finding.get('details', '')}",
                        context="compliance"
                    )
                    suggestion["ai_remediation"] = response.get("answer", "")
                except Exception:
                    pass

            suggestions.append(suggestion)
        return suggestions

    async def store_posture_snapshot(self, scores: Dict):
        """Insert security posture scores into database for trending."""
        await self.db.insert_posture_snapshot(
            timestamp=scores.get("timestamp", _now()),
            overall=scores.get("overall_score", 0),
            identity=scores.get("identity_score", 0),
            device=scores.get("device_score", 0),
            data=scores.get("data_score", 0),
            app=scores.get("security_score", 0),
            infrastructure=scores.get("infrastructure_score", 0),
            details=json.dumps(scores),
        )

    def _compute_identity_score(self, findings: List[Dict]) -> float:
        if not findings:
            return 85.0  # Default healthy
        scores = [f.get("score", 50) for f in findings]
        return sum(scores) / len(scores) if scores else 85.0

    def _compute_device_score(self, findings: List[Dict]) -> float:
        if not findings:
            return 90.0
        # Each non-compliant device reduces score
        return max(0, 100 - len(findings) * 15)

    def _compute_data_score(self, findings: List[Dict]) -> float:
        if not findings:
            return 80.0
        scores = [f.get("score", 50) for f in findings]
        return sum(scores) / len(scores) if scores else 80.0

    @staticmethod
    def _device_remediation(device: Dict) -> str:
        issues = []
        if not device.get("isEncrypted", True):
            issues.append("Enable disk encryption (BitLocker/LUKS)")
        if device.get("complianceState") == "noncompliant":
            issues.append("Review and apply required compliance policies")
        os_ver = device.get("osVersion", "")
        if os_ver and "20.5.1" in os_ver:
            issues.append("Upgrade Node.js to v20.9.0+ (security fix)")
        return ". ".join(issues) if issues else "Review device policies in Intune."

    @staticmethod
    def _identity_remediation(user: Dict) -> str:
        risk = user.get("riskLevel", "")
        detail = user.get("riskDetail", "")
        if risk == "high":
            return "Immediately reset password, revoke sessions, enforce MFA re-registration."
        elif risk == "medium":
            return "Investigate suspicious activity, enforce MFA, review sign-in logs."
        return "Monitor user activity and ensure MFA is registered."

    def _demo_device_findings(self) -> List[Dict]:
        return [
            {"deviceName": "PROD-SRV-02", "complianceState": "noncompliant",
             "operatingSystem": "Linux", "isEncrypted": False,
             "lastSyncDateTime": _now(), "_demo": True},
            {"deviceName": "EDGE-NODE-07", "complianceState": "noncompliant",
             "operatingSystem": "Linux", "isEncrypted": False,
             "lastSyncDateTime": _now(), "_demo": True},
        ]

    def _demo_risky_users(self) -> List[Dict]:
        return [
            {"userDisplayName": "John Doe", "userPrincipalName": "john.doe@contoso.com",
             "riskLevel": "high", "riskState": "atRisk", "riskDetail": "suspiciousActivity", "_demo": True},
            {"userDisplayName": "Service Account", "userPrincipalName": "svc01@contoso.com",
             "riskLevel": "medium", "riskState": "atRisk", "riskDetail": "unfamiliarFeatures", "_demo": True},
        ]

    def _demo_mfa_status(self) -> Dict:
        return {"totalUsers": 150, "mfaRegistered": 128, "mfaRate": "85.3%", "_demo": True}

    def _demo_secure_score(self) -> Dict:
        return {
            "currentScore": 68.5, "maxScore": 100,
            "controlScores": [
                {"controlName": "MFARegistration", "score": 9.0, "maxScore": 10.0, "description": "Multi-factor authentication"},
                {"controlName": "SigninRiskPolicy", "score": 0.0, "maxScore": 6.0, "description": "Sign-in risk policy"},
                {"controlName": "UserRiskPolicy", "score": 0.0, "maxScore": 6.0, "description": "User risk policy"},
                {"controlName": "IntuneMDM", "score": 5.0, "maxScore": 10.0, "description": "MDM enrollment"},
            ],
            "_demo": True,
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
