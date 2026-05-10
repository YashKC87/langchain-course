# ============================================================
#  HEALIX Database — database.py
#  SQLite schema, async connection, and helper functions.
#  Uses aiosqlite for non-blocking database access.
# ============================================================

import json
import aiosqlite
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any


SCHEMA_SQL = """
-- Collected logs from Azure, on-prem, and multi-cloud sources
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    source TEXT NOT NULL,
    source_service TEXT,
    severity TEXT DEFAULT 'info',
    category TEXT,
    endpoint_name TEXT,
    message TEXT NOT NULL,
    raw_data TEXT,
    ingested_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_source ON logs(source);
CREATE INDEX IF NOT EXISTS idx_logs_severity ON logs(severity);

-- Alerts (replaces hardcoded alert list)
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    source TEXT NOT NULL,
    endpoint_name TEXT,
    title TEXT NOT NULL,
    description TEXT,
    severity_score REAL,
    resolved INTEGER DEFAULT 0,
    resolved_at TEXT,
    resolved_by TEXT,
    notification_sent INTEGER DEFAULT 0,
    raw_data TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON alerts(resolved);
CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp);

-- Healing actions (replaces hardcoded action list)
CREATE TABLE IF NOT EXISTS healing_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id INTEGER REFERENCES alerts(id),
    timestamp TEXT NOT NULL,
    endpoint_name TEXT NOT NULL,
    action_type TEXT NOT NULL,
    action_description TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    impact TEXT DEFAULT 'low',
    result_message TEXT,
    duration_seconds REAL,
    triggered_by TEXT DEFAULT 'system',
    created_at TEXT DEFAULT (datetime('now'))
);

-- Compliance assessment results
CREATE TABLE IF NOT EXISTS compliance_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    check_type TEXT NOT NULL,
    scope TEXT NOT NULL,
    check_name TEXT NOT NULL,
    status TEXT NOT NULL,
    details TEXT,
    remediation_suggestion TEXT,
    score REAL,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Security posture snapshots over time
CREATE TABLE IF NOT EXISTS security_posture (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    overall_score REAL NOT NULL,
    identity_score REAL,
    device_score REAL,
    data_score REAL,
    app_score REAL,
    infrastructure_score REAL,
    details TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Copilot / platform usage metrics
CREATE TABLE IF NOT EXISTS usage_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    metric_type TEXT NOT NULL,
    user_identifier TEXT,
    service TEXT,
    action TEXT,
    token_count INTEGER,
    response_time_ms REAL,
    success INTEGER DEFAULT 1,
    metadata TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage_metrics(timestamp);

-- User-defined alert rules
CREATE TABLE IF NOT EXISTS alert_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    enabled INTEGER DEFAULT 1,
    source TEXT NOT NULL,
    condition_json TEXT NOT NULL,
    severity TEXT DEFAULT 'warning',
    delivery_channels TEXT DEFAULT '["dashboard"]',
    cooldown_minutes INTEGER DEFAULT 15,
    last_triggered_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Monitored endpoints (replaces hardcoded endpoint list)
CREATE TABLE IF NOT EXISTS endpoints (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    os TEXT,
    status TEXT DEFAULT 'unknown',
    source TEXT DEFAULT 'manual',
    intune_device_id TEXT,
    defender_device_id TEXT,
    entra_device_id TEXT,
    last_cpu REAL,
    last_mem REAL,
    last_disk REAL,
    uptime TEXT,
    last_seen_at TEXT,
    metadata TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Webhook registrations for external push notifications
CREATE TABLE IF NOT EXISTS webhooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    events TEXT DEFAULT '["all"]',
    description TEXT DEFAULT '',
    api_key_hint TEXT DEFAULT '',
    active INTEGER DEFAULT 1,
    secret TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

-- Webhook delivery log
CREATE TABLE IF NOT EXISTS webhook_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    webhook_id INTEGER NOT NULL REFERENCES webhooks(id),
    alert_id INTEGER REFERENCES alerts(id),
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    delivered INTEGER DEFAULT 0,
    http_status INTEGER,
    error_message TEXT,
    delivered_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


class Database:
    """Async SQLite database wrapper for HEALIX."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        """Create database connection and run schema migrations."""
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA_SQL)
        await self._db.commit()
        print(f"Database initialized at {self.db_path}")

    async def close(self):
        if self._db:
            await self._db.close()

    # ── Log operations ──────────────────────────────────────────

    async def insert_log(self, timestamp: str, source: str, source_service: str,
                         severity: str, category: str, endpoint_name: str,
                         message: str, raw_data: Optional[dict] = None) -> int:
        cursor = await self._db.execute(
            """INSERT INTO logs (timestamp, source, source_service, severity, category,
               endpoint_name, message, raw_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (timestamp, source, source_service, severity, category,
             endpoint_name, message, json.dumps(raw_data) if raw_data else None)
        )
        await self._db.commit()
        return cursor.lastrowid

    async def insert_logs_batch(self, logs: List[Dict[str, Any]]) -> int:
        """Insert multiple log entries efficiently."""
        if not logs:
            return 0
        await self._db.executemany(
            """INSERT INTO logs (timestamp, source, source_service, severity, category,
               endpoint_name, message, raw_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [(l.get("timestamp") or _now(), l.get("source", ""), l.get("source_service", ""),
              l.get("severity", "info"), l.get("category", ""), l.get("endpoint_name", ""),
              l.get("message", ""), json.dumps(l.get("raw_data")) if l.get("raw_data") else None)
             for l in logs]
        )
        await self._db.commit()
        return len(logs)

    async def query_logs(self, source: Optional[str] = None, severity: Optional[str] = None,
                         search: Optional[str] = None, hours: int = 24,
                         limit: int = 200, offset: int = 0) -> List[Dict]:
        conditions = ["timestamp >= datetime('now', ?)" ]
        params: list = [f"-{hours} hours"]

        if source:
            conditions.append("source = ?")
            params.append(source)
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        if search:
            conditions.append("message LIKE ?")
            params.append(f"%{search}%")

        where = " AND ".join(conditions)
        params.extend([limit, offset])

        cursor = await self._db.execute(
            f"SELECT * FROM logs WHERE {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            params
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_log_stats(self, hours: int = 24) -> Dict:
        cursor = await self._db.execute(
            """SELECT source, severity, COUNT(*) as count FROM logs
               WHERE timestamp >= datetime('now', ?) GROUP BY source, severity""",
            (f"-{hours} hours",)
        )
        rows = await cursor.fetchall()
        by_source = {}
        by_severity = {}
        total = 0
        for r in rows:
            row = dict(r)
            by_source[row["source"]] = by_source.get(row["source"], 0) + row["count"]
            by_severity[row["severity"]] = by_severity.get(row["severity"], 0) + row["count"]
            total += row["count"]
        return {"total": total, "by_source": by_source, "by_severity": by_severity}

    async def get_log_sources(self) -> List[Dict]:
        cursor = await self._db.execute(
            "SELECT source, COUNT(*) as count FROM logs GROUP BY source ORDER BY count DESC"
        )
        return [dict(r) for r in await cursor.fetchall()]

    # ── Alert operations ────────────────────────────────────────

    async def insert_alert(self, timestamp: str, alert_type: str, source: str,
                           endpoint_name: str, title: str, description: str = "",
                           severity_score: float = 0.0, raw_data: Optional[dict] = None) -> int:
        cursor = await self._db.execute(
            """INSERT INTO alerts (timestamp, alert_type, source, endpoint_name, title,
               description, severity_score, raw_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (timestamp, alert_type, source, endpoint_name, title, description,
             severity_score, json.dumps(raw_data) if raw_data else None)
        )
        await self._db.commit()
        return cursor.lastrowid

    async def get_alerts(self, resolved: Optional[bool] = None, alert_type: Optional[str] = None,
                         limit: int = 50) -> List[Dict]:
        conditions = []
        params = []
        if resolved is not None:
            conditions.append("resolved = ?")
            params.append(1 if resolved else 0)
        if alert_type:
            conditions.append("alert_type = ?")
            params.append(alert_type)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)

        cursor = await self._db.execute(
            f"SELECT * FROM alerts{where} ORDER BY timestamp DESC LIMIT ?", params
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_alert_by_id(self, alert_id: int) -> Optional[Dict]:
        cursor = await self._db.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def resolve_alert(self, alert_id: int, resolved_by: str = "manual") -> bool:
        await self._db.execute(
            "UPDATE alerts SET resolved = 1, resolved_at = datetime('now'), resolved_by = ? WHERE id = ?",
            (resolved_by, alert_id)
        )
        await self._db.commit()
        return True

    async def get_alert_stats(self) -> Dict:
        cursor = await self._db.execute(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN resolved = 0 THEN 1 ELSE 0 END) as active,
                SUM(CASE WHEN alert_type = 'critical' AND resolved = 0 THEN 1 ELSE 0 END) as critical,
                SUM(CASE WHEN alert_type = 'warning' AND resolved = 0 THEN 1 ELSE 0 END) as warning
            FROM alerts"""
        )
        row = await cursor.fetchone()
        return dict(row) if row else {"total": 0, "active": 0, "critical": 0, "warning": 0}

    # ── Healing action operations ───────────────────────────────

    async def insert_healing_action(self, timestamp: str, endpoint_name: str,
                                    action_type: str, action_description: str,
                                    status: str = "pending", impact: str = "low",
                                    alert_id: Optional[int] = None,
                                    triggered_by: str = "system") -> int:
        cursor = await self._db.execute(
            """INSERT INTO healing_actions (alert_id, timestamp, endpoint_name, action_type,
               action_description, status, impact, triggered_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (alert_id, timestamp, endpoint_name, action_type, action_description,
             status, impact, triggered_by)
        )
        await self._db.commit()
        return cursor.lastrowid

    async def update_healing_action(self, action_id: int, status: str,
                                    result_message: str = "", duration: float = 0.0):
        await self._db.execute(
            "UPDATE healing_actions SET status = ?, result_message = ?, duration_seconds = ? WHERE id = ?",
            (status, result_message, duration, action_id)
        )
        await self._db.commit()

    async def get_healing_actions(self, limit: int = 50) -> List[Dict]:
        cursor = await self._db.execute(
            "SELECT * FROM healing_actions ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_healing_stats(self) -> Dict:
        cursor = await self._db.execute(
            """SELECT COUNT(*) as total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM healing_actions"""
        )
        row = await cursor.fetchone()
        r = dict(row) if row else {"total": 0, "completed": 0, "failed": 0}
        r["success_rate"] = f"{(r['completed'] / r['total'] * 100):.1f}%" if r["total"] > 0 else "N/A"
        return r

    # ── Endpoint operations ─────────────────────────────────────

    async def upsert_endpoint(self, id: str, name: str, os: str = "", status: str = "unknown",
                              source: str = "manual", **kwargs) -> str:
        await self._db.execute(
            """INSERT INTO endpoints (id, name, os, status, source, intune_device_id,
               defender_device_id, entra_device_id, last_cpu, last_mem, last_disk, uptime,
               last_seen_at, metadata, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(id) DO UPDATE SET
               name=excluded.name, os=excluded.os, status=excluded.status,
               last_cpu=excluded.last_cpu, last_mem=excluded.last_mem, last_disk=excluded.last_disk,
               uptime=excluded.uptime, last_seen_at=excluded.last_seen_at,
               metadata=excluded.metadata, updated_at=datetime('now')""",
            (id, name, os, status, source,
             kwargs.get("intune_device_id"), kwargs.get("defender_device_id"),
             kwargs.get("entra_device_id"), kwargs.get("last_cpu"), kwargs.get("last_mem"),
             kwargs.get("last_disk"), kwargs.get("uptime"), kwargs.get("last_seen_at"),
             json.dumps(kwargs.get("metadata")) if kwargs.get("metadata") else None)
        )
        await self._db.commit()
        return id

    async def get_endpoints(self) -> List[Dict]:
        cursor = await self._db.execute("SELECT * FROM endpoints ORDER BY name")
        return [dict(r) for r in await cursor.fetchall()]

    async def get_endpoint(self, endpoint_id: str) -> Optional[Dict]:
        cursor = await self._db.execute("SELECT * FROM endpoints WHERE id = ?", (endpoint_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    # ── Compliance operations ───────────────────────────────────

    async def insert_compliance_check(self, timestamp: str, check_type: str, scope: str,
                                      check_name: str, status: str, details: str = "",
                                      remediation_suggestion: str = "", score: float = 0.0) -> int:
        cursor = await self._db.execute(
            """INSERT INTO compliance_checks (timestamp, check_type, scope, check_name,
               status, details, remediation_suggestion, score) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (timestamp, check_type, scope, check_name, status, details, remediation_suggestion, score)
        )
        await self._db.commit()
        return cursor.lastrowid

    async def get_compliance_checks(self, check_type: Optional[str] = None,
                                    limit: int = 100) -> List[Dict]:
        if check_type:
            cursor = await self._db.execute(
                "SELECT * FROM compliance_checks WHERE check_type = ? ORDER BY timestamp DESC LIMIT ?",
                (check_type, limit)
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM compliance_checks ORDER BY timestamp DESC LIMIT ?", (limit,)
            )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_compliance_gaps(self) -> List[Dict]:
        cursor = await self._db.execute(
            """SELECT * FROM compliance_checks WHERE status = 'non_compliant'
               ORDER BY score ASC, timestamp DESC LIMIT 100"""
        )
        return [dict(r) for r in await cursor.fetchall()]

    # ── Security posture operations ─────────────────────────────

    async def insert_posture_snapshot(self, timestamp: str, overall: float,
                                      identity: float = 0, device: float = 0,
                                      data: float = 0, app: float = 0,
                                      infrastructure: float = 0, details: str = ""):
        await self._db.execute(
            """INSERT INTO security_posture (timestamp, overall_score, identity_score,
               device_score, data_score, app_score, infrastructure_score, details)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (timestamp, overall, identity, device, data, app, infrastructure, details)
        )
        await self._db.commit()

    async def get_posture_history(self, limit: int = 30) -> List[Dict]:
        cursor = await self._db.execute(
            "SELECT * FROM security_posture ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_latest_posture(self) -> Optional[Dict]:
        cursor = await self._db.execute(
            "SELECT * FROM security_posture ORDER BY timestamp DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    # ── Usage metrics operations ────────────────────────────────

    async def insert_usage_metric(self, timestamp: str, metric_type: str,
                                  service: str, action: str, user_identifier: str = "",
                                  token_count: int = 0, response_time_ms: float = 0,
                                  success: bool = True, metadata: Optional[dict] = None):
        await self._db.execute(
            """INSERT INTO usage_metrics (timestamp, metric_type, user_identifier, service,
               action, token_count, response_time_ms, success, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (timestamp, metric_type, user_identifier, service, action,
             token_count, response_time_ms, 1 if success else 0,
             json.dumps(metadata) if metadata else None)
        )
        await self._db.commit()

    async def get_usage_summary(self, hours: int = 168) -> Dict:
        cursor = await self._db.execute(
            """SELECT service, COUNT(*) as count, AVG(response_time_ms) as avg_response,
               SUM(token_count) as total_tokens
               FROM usage_metrics WHERE timestamp >= datetime('now', ?)
               GROUP BY service""",
            (f"-{hours} hours",)
        )
        rows = [dict(r) for r in await cursor.fetchall()]
        return {
            "by_service": rows,
            "total_queries": sum(r["count"] for r in rows),
            "total_tokens": sum(r["total_tokens"] or 0 for r in rows),
        }

    # ── Alert rules operations ──────────────────────────────────

    async def insert_alert_rule(self, name: str, source: str, condition_json: str,
                                severity: str = "warning", description: str = "",
                                delivery_channels: str = '["dashboard"]',
                                cooldown_minutes: int = 15) -> int:
        cursor = await self._db.execute(
            """INSERT INTO alert_rules (name, description, source, condition_json,
               severity, delivery_channels, cooldown_minutes) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, description, source, condition_json, severity,
             delivery_channels, cooldown_minutes)
        )
        await self._db.commit()
        return cursor.lastrowid

    async def get_alert_rules(self, enabled_only: bool = True) -> List[Dict]:
        if enabled_only:
            cursor = await self._db.execute(
                "SELECT * FROM alert_rules WHERE enabled = 1 ORDER BY created_at DESC"
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM alert_rules ORDER BY created_at DESC"
            )
        return [dict(r) for r in await cursor.fetchall()]

    async def update_alert_rule(self, rule_id: int, **kwargs):
        sets = []
        params = []
        for key, value in kwargs.items():
            if key in ("name", "description", "source", "condition_json", "severity",
                       "delivery_channels", "enabled", "cooldown_minutes", "last_triggered_at"):
                sets.append(f"{key} = ?")
                params.append(value)
        if sets:
            params.append(rule_id)
            await self._db.execute(
                f"UPDATE alert_rules SET {', '.join(sets)} WHERE id = ?", params
            )
            await self._db.commit()

    async def delete_alert_rule(self, rule_id: int):
        await self._db.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))
        await self._db.commit()

    # ── Webhook operations ──────────────────────────────────────

    async def insert_webhook(self, url: str, events: str = '["all"]',
                             description: str = "", api_key_hint: str = "",
                             secret: str = "") -> int:
        cursor = await self._db.execute(
            """INSERT INTO webhooks (url, events, description, api_key_hint, secret)
               VALUES (?, ?, ?, ?, ?)""",
            (url, events, description, api_key_hint, secret)
        )
        await self._db.commit()
        return cursor.lastrowid

    async def get_webhooks(self, active_only: bool = True) -> List[Dict]:
        if active_only:
            cursor = await self._db.execute(
                "SELECT * FROM webhooks WHERE active = 1 ORDER BY created_at DESC"
            )
        else:
            cursor = await self._db.execute("SELECT * FROM webhooks ORDER BY created_at DESC")
        return [dict(r) for r in await cursor.fetchall()]

    async def deactivate_webhook(self, webhook_id: int) -> bool:
        await self._db.execute(
            "UPDATE webhooks SET active = 0 WHERE id = ?", (webhook_id,)
        )
        await self._db.commit()
        return True

    async def insert_webhook_event(self, webhook_id: int, alert_id: Optional[int],
                                   event_type: str, payload: str) -> int:
        cursor = await self._db.execute(
            """INSERT INTO webhook_events (webhook_id, alert_id, event_type, payload)
               VALUES (?, ?, ?, ?)""",
            (webhook_id, alert_id, event_type, payload)
        )
        await self._db.commit()
        return cursor.lastrowid

    async def mark_webhook_delivered(self, event_id: int, http_status: int,
                                     error_message: str = ""):
        await self._db.execute(
            """UPDATE webhook_events SET delivered = 1, http_status = ?,
               error_message = ?, delivered_at = datetime('now') WHERE id = ?""",
            (http_status, error_message, event_id)
        )
        await self._db.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
