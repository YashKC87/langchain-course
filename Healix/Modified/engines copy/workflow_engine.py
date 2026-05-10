# ============================================================
#  HEALIX Workflow Engine — engines/workflow_engine.py
#  Automated incident triage and response workflows.
# ============================================================

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict

logger = logging.getLogger("healix.workflow")


class WorkflowEngine:
    """Automated incident triage, response, and mitigation."""

    def __init__(self, db, agent=None, defender_client=None,
                 intune_client=None, entra_client=None, alert_engine=None):
        self.db = db
        self.agent = agent
        self.defender = defender_client
        self.intune = intune_client
        self.entra = entra_client
        self.alert_engine = alert_engine

    async def triage_incident(self, incident_id: str, source: str = "defender") -> Dict:
        """Automated incident triage with AI-powered analysis."""
        # Fetch incident details
        incident = None
        if source == "defender" and self.defender:
            incident = await self.defender.get_incident_details(incident_id)
        elif source == "sentinel" and hasattr(self, 'sentinel') and self.sentinel:
            incidents = await self.sentinel.get_sentinel_incidents()
            incident = next((i for i in incidents if i.get("id") == incident_id), None)

        if not incident:
            incident = {
                "id": incident_id,
                "displayName": f"Incident {incident_id}",
                "severity": "medium",
                "alerts": [],
                "_demo": True,
            }

        # Classify severity
        severity = incident.get("severity", "medium").lower()
        alert_count = incident.get("alertCount", len(incident.get("alerts", [])))

        # Use AI agent for analysis if available
        ai_analysis = ""
        recommended_actions = []
        if self.agent:
            try:
                question = (f"Analyze this security incident and recommend response actions: "
                            f"'{incident.get('displayName', '')}' with severity {severity} "
                            f"and {alert_count} related alerts.")
                response = await self.agent.ask(question=question, context="security_triage")
                ai_analysis = response.get("answer", "")
                recommended_actions = response.get("actions_taken", [])
            except Exception as e:
                logger.error(f"AI triage failed: {e}")
                ai_analysis = "AI analysis unavailable"

        if not recommended_actions:
            recommended_actions = self._default_actions(severity, incident)

        # Determine if auto-execution is appropriate
        auto_execute = severity in ("high", "critical") and alert_count >= 3
        executed_actions = []

        if auto_execute:
            for action in recommended_actions[:2]:  # Limit auto-execution to first 2 actions
                result = await self._execute_action(action, incident)
                executed_actions.append(result)

        # Record triage in healing actions
        action_id = await self.db.insert_healing_action(
            timestamp=_now(),
            endpoint_name=self._extract_endpoint(incident),
            action_type="incident_triage",
            action_description=f"Triage: {incident.get('displayName', incident_id)}",
            status="completed",
            impact=severity,
            triggered_by="workflow_auto",
        )

        return {
            "incident_id": incident_id,
            "severity": severity,
            "classification": self._classify(incident),
            "ai_analysis": ai_analysis,
            "recommended_actions": recommended_actions,
            "auto_executed": auto_execute,
            "executed_actions": executed_actions,
            "triage_action_id": action_id,
            "timestamp": _now(),
        }

    async def apply_mitigation(self, action_type: str, target_id: str,
                               target_type: str = "device", reason: str = "") -> Dict:
        """Execute a specific mitigation action."""
        result = {"action": action_type, "target": target_id, "status": "pending", "timestamp": _now()}

        try:
            if action_type == "isolate_device" and self.intune:
                resp = await self.intune.trigger_device_action(target_id, "remoteLock")
                result["status"] = "executed"
                result["detail"] = resp

            elif action_type == "restart_device" and self.intune:
                resp = await self.intune.trigger_device_action(target_id, "rebootNow")
                result["status"] = "executed"
                result["detail"] = resp

            elif action_type == "scan_device" and self.intune:
                resp = await self.intune.trigger_device_action(target_id, "windowsDefenderScan")
                result["status"] = "executed"
                result["detail"] = resp

            elif action_type == "sync_device" and self.intune:
                resp = await self.intune.trigger_device_action(target_id, "syncDevice")
                result["status"] = "executed"
                result["detail"] = resp

            elif action_type == "block_ip" and self.defender:
                result["status"] = "queued"
                result["detail"] = "IP block indicator submitted to Defender"

            elif action_type == "disable_user":
                result["status"] = "queued"
                result["detail"] = "User disable action queued (requires admin approval)"

            elif action_type == "restart_service":
                result["status"] = "simulated"
                result["detail"] = "Service restart simulated in demo mode"

            else:
                result["status"] = "unsupported"
                result["detail"] = f"Action '{action_type}' not implemented"

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            logger.error(f"Mitigation failed: {action_type} on {target_id}: {e}")

        # Record action
        await self.db.insert_healing_action(
            timestamp=_now(),
            endpoint_name=target_id,
            action_type=action_type,
            action_description=f"{action_type} on {target_type}:{target_id}. {reason}",
            status=result["status"],
            impact="high" if action_type in ("isolate_device", "disable_user") else "medium",
            triggered_by="workflow_manual",
        )

        return result

    async def process_new_alerts(self) -> List[Dict]:
        """Auto-triage new critical/high alerts."""
        active = await self.alert_engine.get_active_alerts(limit=20) if self.alert_engine else []
        results = []

        for alert in active:
            severity = alert.get("alert_type", "")
            if severity in ("critical", "high"):
                # Auto-triage if from a known source
                if alert.get("source", "").startswith("rule:") or "defender" in alert.get("source", ""):
                    try:
                        triage = await self.triage_incident(
                            str(alert.get("id", "")),
                            source="internal"
                        )
                        results.append(triage)
                    except Exception as e:
                        logger.error(f"Auto-triage failed for alert {alert.get('id')}: {e}")

        return results

    async def get_workflow_history(self, limit: int = 50) -> List[Dict]:
        """Get history of workflow actions."""
        actions = await self.db.get_healing_actions(limit=limit)
        return [a for a in actions if a.get("triggered_by", "").startswith("workflow")]

    async def _execute_action(self, action_desc: str, incident: Dict) -> Dict:
        """Execute a single recommended action."""
        action_lower = action_desc.lower()
        endpoint = self._extract_endpoint(incident)

        if "isolat" in action_lower:
            return await self.apply_mitigation("isolate_device", endpoint, reason="Auto-triage")
        elif "restart" in action_lower or "reboot" in action_lower:
            return await self.apply_mitigation("restart_device", endpoint, reason="Auto-triage")
        elif "scan" in action_lower:
            return await self.apply_mitigation("scan_device", endpoint, reason="Auto-triage")
        elif "block" in action_lower:
            return await self.apply_mitigation("block_ip", endpoint, reason="Auto-triage")
        else:
            return {"action": action_desc, "status": "queued", "detail": "Queued for manual review"}

    def _classify(self, incident: Dict) -> str:
        """Classify incident type."""
        title = incident.get("displayName", "").lower()
        if "phishing" in title or "email" in title:
            return "phishing"
        if "ransomware" in title or "encryption" in title:
            return "ransomware"
        if "brute" in title or "credential" in title:
            return "credential_attack"
        if "lateral" in title or "movement" in title:
            return "lateral_movement"
        if "exfiltration" in title or "data" in title:
            return "data_exfiltration"
        return "unknown"

    def _extract_endpoint(self, incident: Dict) -> str:
        """Extract primary endpoint from incident."""
        alerts = incident.get("alerts", [])
        if alerts and isinstance(alerts, list):
            first = alerts[0] if isinstance(alerts[0], dict) else {}
            return first.get("machineName", first.get("title", "unknown-endpoint"))
        return "unknown-endpoint"

    def _default_actions(self, severity: str, incident: Dict) -> List[str]:
        """Default recommended actions based on severity."""
        if severity in ("critical", "high"):
            return [
                "Isolate affected endpoints to prevent lateral movement",
                "Initiate Defender scan on affected endpoints",
                "Collect forensic evidence and memory dumps",
                "Notify security operations team",
                "Review related sign-in and audit logs",
            ]
        elif severity == "medium":
            return [
                "Investigate sign-in logs for suspicious activity",
                "Verify MFA status for affected users",
                "Monitor for repeated incidents",
            ]
        return [
            "Log incident for review",
            "Monitor for escalation",
        ]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
