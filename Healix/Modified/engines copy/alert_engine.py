# ============================================================
#  HEALIX Alert Engine — engines/alert_engine.py
#  Evaluates alert rules against logs and metrics.
#  Routes triggered alerts to notification channels.
# ============================================================

import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict

logger = logging.getLogger("healix.alert_engine")


class AlertEngine:
    """Evaluates alert rules and manages alert lifecycle."""

    def __init__(self, db, notification_service=None, config=None):
        self.db = db
        self.notify = notification_service
        self.config = config
        self.app = None  # Set by main.py after engine creation to enable webhook dispatch

    async def evaluate_rules(self) -> List[Dict]:
        """Load enabled alert rules, evaluate each against recent data.
        Returns list of newly created alerts.
        """
        rules = await self.db.get_alert_rules(enabled_only=True)
        new_alerts = []

        for rule in rules:
            try:
                # Check cooldown
                if not self._check_cooldown(rule):
                    continue

                triggered = await self.evaluate_single_rule(rule)
                if triggered:
                    alert = await self.create_alert(
                        source=f"rule:{rule['name']}",
                        endpoint=triggered.get("endpoint_name", ""),
                        title=f"[Rule] {rule['name']}",
                        description=triggered.get("description", rule.get("description", "")),
                        severity=rule.get("severity", "warning"),
                        raw_data=triggered,
                    )
                    new_alerts.append(alert)

                    # Notify through configured channels
                    channels = json.loads(rule.get("delivery_channels", '["dashboard"]'))
                    if self.notify and channels:
                        await self.notify.notify(alert, channels)

                    # Update last triggered
                    await self.db.update_alert_rule(
                        rule["id"],
                        last_triggered_at=_now()
                    )

            except Exception as e:
                logger.error(f"Error evaluating rule '{rule.get('name', '?')}': {e}")

        if new_alerts:
            logger.info(f"Alert evaluation: {len(new_alerts)} new alerts triggered")
        return new_alerts

    async def evaluate_single_rule(self, rule: Dict) -> Optional[Dict]:
        """Evaluate one rule's condition against recent data."""
        source = rule.get("source", "")
        condition = json.loads(rule.get("condition_json", "{}"))

        if source == "log_query":
            return await self._eval_log_query(condition)
        elif source == "metric_threshold":
            return await self._eval_metric_threshold(condition)
        elif source == "defender_severity":
            return await self._eval_defender_severity(condition)
        else:
            logger.warning(f"Unknown rule source: {source}")
            return None

    async def _eval_log_query(self, condition: Dict) -> Optional[Dict]:
        """Evaluate a log-based query condition.
        Example condition: {"severity": "critical", "source": "defender", "min_count": 1, "hours": 1}
        """
        severity = condition.get("severity")
        source = condition.get("source")
        search = condition.get("search")
        min_count = condition.get("min_count", 1)
        hours = condition.get("hours", 1)

        logs = await self.db.query_logs(
            source=source, severity=severity, search=search,
            hours=hours, limit=min_count + 10
        )

        if len(logs) >= min_count:
            return {
                "triggered": True,
                "match_count": len(logs),
                "endpoint_name": logs[0].get("endpoint_name", "") if logs else "",
                "description": f"Found {len(logs)} matching log entries in the last {hours}h",
                "sample_logs": logs[:3],
            }
        return None

    async def _eval_metric_threshold(self, condition: Dict) -> Optional[Dict]:
        """Evaluate a metric threshold condition.
        Example condition: {"metric": "last_cpu", "operator": "gt", "value": 90}
        """
        metric = condition.get("metric", "last_cpu")
        operator = condition.get("operator", "gt")
        value = condition.get("value", 90)

        endpoints = await self.db.get_endpoints()
        for ep in endpoints:
            ep_value = ep.get(metric)
            if ep_value is None:
                continue

            triggered = False
            if operator == "gt" and ep_value > value:
                triggered = True
            elif operator == "lt" and ep_value < value:
                triggered = True
            elif operator == "eq" and ep_value == value:
                triggered = True
            elif operator == "gte" and ep_value >= value:
                triggered = True

            if triggered:
                return {
                    "triggered": True,
                    "endpoint_name": ep.get("name", ""),
                    "metric": metric,
                    "current_value": ep_value,
                    "threshold": value,
                    "description": f"Endpoint {ep.get('name', '')} has {metric}={ep_value} ({operator} {value})",
                }
        return None

    async def _eval_defender_severity(self, condition: Dict) -> Optional[Dict]:
        """Evaluate based on presence of Defender alerts at or above a severity.
        Example condition: {"min_severity": "high", "hours": 1}
        """
        min_severity = condition.get("min_severity", "high")
        hours = condition.get("hours", 1)

        logs = await self.db.query_logs(
            source="azure", severity=self._severity_to_log(min_severity),
            hours=hours, limit=5
        )
        # Also check critical if looking for high
        if min_severity in ("high", "medium"):
            critical_logs = await self.db.query_logs(
                source="azure", severity="critical", hours=hours, limit=5
            )
            logs.extend(critical_logs)

        if logs:
            return {
                "triggered": True,
                "match_count": len(logs),
                "endpoint_name": logs[0].get("endpoint_name", "") if logs else "",
                "description": f"Found {len(logs)} Defender alerts at {min_severity}+ severity",
            }
        return None

    def _check_cooldown(self, rule: Dict) -> bool:
        """Check if enough time has passed since last trigger."""
        last = rule.get("last_triggered_at")
        if not last:
            return True
        cooldown = rule.get("cooldown_minutes", 15)
        try:
            last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            return (now - last_dt) > timedelta(minutes=cooldown)
        except (ValueError, TypeError):
            return True

    async def create_alert(self, source: str, endpoint: str, title: str,
                           description: str = "", severity: str = "warning",
                           raw_data: Optional[Dict] = None) -> Dict:
        """Insert a new alert into the database."""
        severity_score = {"critical": 9.0, "high": 7.0, "warning": 5.0,
                          "medium": 5.0, "info": 2.0, "low": 1.0}.get(severity, 3.0)

        alert_id = await self.db.insert_alert(
            timestamp=_now(),
            alert_type=severity,
            source=source,
            endpoint_name=endpoint,
            title=title,
            description=description,
            severity_score=severity_score,
            raw_data=raw_data,
        )

        alert = {
            "id": alert_id,
            "timestamp": _now(),
            "alert_type": severity,
            "source": source,
            "endpoint_name": endpoint,
            "title": title,
            "description": description,
            "severity_score": severity_score,
            "resolved": False,
        }
        logger.info(f"Alert created: [{severity}] {title} on {endpoint}")

        # Fire-and-forget webhook delivery (never blocks the caller)
        if self.app:
            try:
                alert_record = await self.db.get_alert_by_id(alert_id)
                if alert_record:
                    from routers.integration import deliver_webhooks
                    asyncio.create_task(deliver_webhooks(self.app, alert_record, "alert"))
            except Exception:
                pass  # Webhook dispatch is best-effort

        return alert

    async def resolve_alert(self, alert_id: int, resolved_by: str = "manual") -> bool:
        """Mark an alert as resolved."""
        result = await self.db.resolve_alert(alert_id, resolved_by)
        if result:
            logger.info(f"Alert {alert_id} resolved by {resolved_by}")
        return result

    async def get_active_alerts(self, limit: int = 50) -> List[Dict]:
        """Get all unresolved alerts."""
        return await self.db.get_alerts(resolved=False, limit=limit)

    async def run_evaluation_cycle(self) -> Dict:
        """Called by background scheduler after each log collection cycle."""
        new_alerts = await self.evaluate_rules()
        stats = await self.db.get_alert_stats()
        return {
            "new_alerts": len(new_alerts),
            "active_alerts": stats.get("active", 0),
            "critical_alerts": stats.get("critical", 0),
            "timestamp": _now(),
        }

    @staticmethod
    def _severity_to_log(severity: str) -> str:
        mapping = {"high": "critical", "medium": "warning", "low": "info"}
        return mapping.get(severity, severity)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
