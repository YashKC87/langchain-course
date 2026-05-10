# ============================================================
#  HEALIX Log Pipeline — engines/log_pipeline.py
#  Collects, normalizes, and stores logs from multiple sources.
# ============================================================

import json
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

logger = logging.getLogger("healix.log_pipeline")


class LogPipeline:
    """Multi-source log collection and ingestion into SQLite."""

    def __init__(self, db, sentinel_client=None, defender_client=None, config=None):
        self.db = db
        self.sentinel = sentinel_client
        self.defender = defender_client
        self.config = config
        self._last_collection = None

    async def collect_from_sentinel(self, timespan: str = "PT5M") -> int:
        """Pull recent logs from Sentinel/Log Analytics via KQL queries."""
        if not self.sentinel or not self.sentinel.is_available:
            return 0

        total = 0

        # Collect security events
        try:
            events = await self.sentinel.query_security_events(timespan)
            for ev in events:
                await self.db.insert_log(
                    timestamp=ev.get("TimeGenerated", _now()),
                    source="azure",
                    source_service="sentinel",
                    severity=self._map_security_severity(ev),
                    category="security",
                    endpoint_name=ev.get("Computer", ""),
                    message=ev.get("Activity", ev.get("Message", str(ev))),
                    raw_data=ev,
                )
            total += len(events)
        except Exception as e:
            logger.error(f"Failed to collect security events: {e}")

        # Collect syslog
        try:
            syslogs = await self.sentinel.query_syslog("err", timespan)
            for sl in syslogs:
                await self.db.insert_log(
                    timestamp=sl.get("TimeGenerated", _now()),
                    source="on_prem",
                    source_service="syslog",
                    severity=self._map_syslog_severity(sl.get("SeverityLevel", "info")),
                    category="system",
                    endpoint_name=sl.get("Computer", ""),
                    message=sl.get("SyslogMessage", str(sl)),
                    raw_data=sl,
                )
            total += len(syslogs)
        except Exception as e:
            logger.error(f"Failed to collect syslog: {e}")

        # Collect heartbeat (agent connectivity)
        try:
            heartbeats = await self.sentinel.query_heartbeat()
            for hb in heartbeats:
                status = hb.get("Status", "Unknown")
                severity = "critical" if status == "Disconnected" else ("warning" if status == "Degraded" else "info")
                await self.db.insert_log(
                    timestamp=hb.get("LastCall", _now()),
                    source="azure",
                    source_service="heartbeat",
                    severity=severity,
                    category="monitoring",
                    endpoint_name=hb.get("Computer", ""),
                    message=f"Agent status: {status} (OS: {hb.get('OSType', 'N/A')})",
                    raw_data=hb,
                )
            total += len(heartbeats)
        except Exception as e:
            logger.error(f"Failed to collect heartbeat: {e}")

        logger.info(f"Collected {total} log entries from Sentinel")
        return total

    async def collect_from_defender(self) -> int:
        """Pull security alerts from Defender and store as log entries."""
        if not self.defender or not self.defender.is_available:
            return 0

        try:
            alerts = await self.defender.get_security_alerts(top=50)
            count = 0
            for alert in alerts:
                await self.db.insert_log(
                    timestamp=alert.get("createdDateTime", _now()),
                    source="azure",
                    source_service="defender",
                    severity=self._map_defender_severity(alert.get("severity", "unknown")),
                    category="security",
                    endpoint_name=alert.get("machineName", ""),
                    message=f"[{alert.get('category', 'Alert')}] {alert.get('title', 'Defender Alert')}",
                    raw_data=alert,
                )
                count += 1
            logger.info(f"Collected {count} alerts from Defender")
            return count
        except Exception as e:
            logger.error(f"Failed to collect Defender alerts: {e}")
            return 0

    async def ingest_custom_log(self, source: str, entries: List[Dict]) -> int:
        """API-driven log ingestion for on-prem/multi-cloud sources."""
        logs = []
        for entry in entries:
            logs.append({
                "timestamp": entry.get("timestamp") or _now(),
                "source": source,
                "source_service": entry.get("source_service", "custom"),
                "severity": entry.get("severity", "info"),
                "category": entry.get("category", "custom"),
                "endpoint_name": entry.get("endpoint_name", ""),
                "message": entry.get("message", ""),
                "raw_data": entry.get("raw_data"),
            })
        count = await self.db.insert_logs_batch(logs)
        logger.info(f"Ingested {count} custom log entries from '{source}'")
        return count

    async def ingest_syslog_raw(self, raw: str) -> int:
        """Parse RFC 5424 / RFC 3164 syslog messages and store."""
        lines = raw.strip().split("\n")
        count = 0
        for line in lines:
            parsed = self._parse_syslog_line(line)
            if parsed:
                await self.db.insert_log(**parsed)
                count += 1
        logger.info(f"Ingested {count} syslog lines")
        return count

    async def run_collection_cycle(self) -> Dict:
        """Execute all configured collectors. Called by background scheduler."""
        results = {"sentinel": 0, "defender": 0, "timestamp": _now()}

        results["sentinel"] = await self.collect_from_sentinel()
        results["defender"] = await self.collect_from_defender()

        self._last_collection = results
        total = results["sentinel"] + results["defender"]
        logger.info(f"Collection cycle complete: {total} total new entries")
        return results

    def _parse_syslog_line(self, line: str) -> Optional[Dict]:
        """Parse a syslog line into log entry fields."""
        # RFC 3164 format: <PRI>TIMESTAMP HOSTNAME APP[PID]: MESSAGE
        match = re.match(
            r'<(\d{1,3})>(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(\S+)\s+(\S+?)(?:\[(\d+)\])?:\s+(.*)',
            line
        )
        if match:
            pri, ts, hostname, app, pid, msg = match.groups()
            severity_num = int(pri) & 0x07
            severity_map = {0: "critical", 1: "critical", 2: "critical", 3: "error",
                           4: "warning", 5: "info", 6: "info", 7: "info"}
            return {
                "timestamp": _now(),
                "source": "on_prem",
                "source_service": "syslog",
                "severity": severity_map.get(severity_num, "info"),
                "category": "system",
                "endpoint_name": hostname,
                "message": f"[{app}] {msg}",
                "raw_data": {"pri": pri, "app": app, "pid": pid, "raw": line},
            }
        # Fallback: store raw line
        if line.strip():
            return {
                "timestamp": _now(),
                "source": "on_prem",
                "source_service": "syslog",
                "severity": "info",
                "category": "system",
                "endpoint_name": "",
                "message": line.strip(),
                "raw_data": {"raw": line},
            }
        return None

    @staticmethod
    def _map_security_severity(event: Dict) -> str:
        event_id = str(event.get("EventID", ""))
        # Map common Windows Security Event IDs to severity
        critical_events = {"4720", "4728", "4732", "4756"}  # Account/group changes
        warning_events = {"4625", "4771", "4776"}  # Failed logins
        if event_id in critical_events:
            return "warning"
        if event_id in warning_events:
            return "warning"
        return "info"

    @staticmethod
    def _map_syslog_severity(level: str) -> str:
        mapping = {"emerg": "critical", "alert": "critical", "crit": "critical",
                   "err": "error", "warning": "warning", "notice": "info",
                   "info": "info", "debug": "info"}
        return mapping.get(level.lower(), "info")

    @staticmethod
    def _map_defender_severity(severity: str) -> str:
        mapping = {"high": "critical", "medium": "warning", "low": "info", "informational": "info"}
        return mapping.get(severity.lower(), "info")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
