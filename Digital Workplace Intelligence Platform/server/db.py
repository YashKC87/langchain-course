"""SQLite storage for DWIP. Small, local, zero-setup."""
import os
import sqlite3
import threading

# Keep the live database out of synced folders (OneDrive locks/syncs it on every write).
DEFAULT_PATH = os.environ.get("DWIP_DB") or os.path.join(
    os.environ.get("LOCALAPPDATA") or os.path.join(os.path.dirname(__file__), "..", "data"), "DWIP", "dwip.db")
RETENTION_SECONDS = 24 * 3600          # raw samples
ROLLUP_RETENTION = 90 * 86400          # hourly DEX rollups (baselines)
AUDIT_RETENTION = 365 * 86400

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices(
    id TEXT PRIMARY KEY, key TEXT, hostname TEXT, kind TEXT, platform TEXT,
    os_version TEXT, model TEXT, user TEXT, enrolled_at REAL, last_seen REAL,
    dex REAL, scores TEXT, metrics TEXT);
CREATE TABLE IF NOT EXISTS telemetry(
    id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, ts REAL,
    dex REAL, cpu REAL, mem REAL, disk REAL, battery REAL);
CREATE INDEX IF NOT EXISTS ix_telemetry ON telemetry(device_id, ts);
CREATE TABLE IF NOT EXISTS issues(
    id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, type TEXT, severity TEXT,
    title TEXT, detail TEXT, status TEXT, opened_at REAL, resolved_at REAL);
CREATE TABLE IF NOT EXISTS actions(
    id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, issue_id INTEGER,
    action TEXT, risk TEXT, status TEXT, created_at REAL, updated_at REAL, result TEXT);
CREATE TABLE IF NOT EXISTS notifications(
    id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, message TEXT, kind TEXT,
    created_at REAL, delivered INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS surveys(
    id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, rating INTEGER, comment TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS events(
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, device_id TEXT, kind TEXT, message TEXT);

-- application visibility
CREATE TABLE IF NOT EXISTS apps_current(
    device_id TEXT, app TEXT, version TEXT, cpu REAL, mem_mb REAL, crashes INTEGER,
    hangs INTEGER, latency_ms REAL, ts REAL, PRIMARY KEY(device_id, app));
CREATE TABLE IF NOT EXISTS app_samples(
    id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, ts REAL, app TEXT,
    cpu REAL, mem_mb REAL, crashes INTEGER, hangs INTEGER, latency_ms REAL);
CREATE INDEX IF NOT EXISTS ix_app_samples ON app_samples(app, ts);

-- AI alerting
CREATE TABLE IF NOT EXISTS alerts(
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, scope TEXT, device_id TEXT, type TEXT,
    severity TEXT, title TEXT, insight TEXT, insight_source TEXT, devices INTEGER,
    status TEXT, updated_at REAL);

-- IT <-> employee collaboration
CREATE TABLE IF NOT EXISTS conversations(
    id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, subject TEXT, status TEXT,
    created_at REAL, updated_at REAL, unread_it INTEGER DEFAULT 0, unread_user INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS messages(
    id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id INTEGER, sender TEXT, text TEXT, ts REAL);

-- in-app guidance
CREATE TABLE IF NOT EXISTS guides(
    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, summary TEXT, steps TEXT,
    target_kind TEXT, trigger_issue TEXT, icon TEXT, created_at REAL, active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS guide_deliveries(
    id INTEGER PRIMARY KEY AUTOINCREMENT, guide_id INTEGER, device_id TEXT, status TEXT,
    source TEXT, ts REAL, updated_at REAL);

-- employee engagement
CREATE TABLE IF NOT EXISTS campaigns(
    id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, target_kind TEXT,
    department TEXT, created_at REAL, sent INTEGER DEFAULT 0);

-- governance, baselines and AI observability
CREATE TABLE IF NOT EXISTS audit(
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, actor TEXT, role TEXT, action TEXT,
    target TEXT, status TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS rollups(
    bucket INTEGER, device_id TEXT, n INTEGER, dex_sum REAL, PRIMARY KEY(bucket, device_id));
CREATE TABLE IF NOT EXISTS ai_calls(
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, purpose TEXT, model TEXT, prompt_tokens INTEGER,
    completion_tokens INTEGER, latency_ms REAL, ok INTEGER);
CREATE TABLE IF NOT EXISTS investigations(
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, actor TEXT, question TEXT, facts INTEGER,
    llm_used INTEGER, latency_ms REAL);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);

-- flows (low-code workflows)
CREATE TABLE IF NOT EXISTS flows(
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, description TEXT, trigger TEXT, graph TEXT,
    enabled INTEGER DEFAULT 0, version INTEGER DEFAULT 1, max_runs_per_hour INTEGER DEFAULT 50,
    created_at REAL, updated_at REAL, updated_by TEXT);
CREATE TABLE IF NOT EXISTS flow_runs(
    id INTEGER PRIMARY KEY AUTOINCREMENT, flow_id INTEGER, flow_version INTEGER, device_id TEXT, trigger TEXT,
    dry_run INTEGER, status TEXT, started_at REAL, finished_at REAL, steps TEXT, actor TEXT);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS ix_issues_dev ON issues(device_id, status);
CREATE INDEX IF NOT EXISTS ix_issues_type ON issues(type, status);
CREATE INDEX IF NOT EXISTS ix_actions_dev ON actions(device_id, status);
CREATE INDEX IF NOT EXISTS ix_notes_dev ON notifications(device_id, delivered);
CREATE INDEX IF NOT EXISTS ix_alerts ON alerts(status, type);
CREATE INDEX IF NOT EXISTS ix_apps_app ON apps_current(app);
CREATE INDEX IF NOT EXISTS ix_guide_dev ON guide_deliveries(device_id, guide_id);
CREATE INDEX IF NOT EXISTS ix_msgs ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS ix_surveys ON surveys(device_id, ts);
CREATE INDEX IF NOT EXISTS ix_audit ON audit(ts);
CREATE INDEX IF NOT EXISTS ix_rollups ON rollups(bucket);
CREATE INDEX IF NOT EXISTS ix_flow_runs ON flow_runs(flow_id, started_at);
"""

# columns added after the first release; applied idempotently to existing databases
MIGRATIONS = [
    ("devices", "department", "TEXT"),
    ("actions", "target", "TEXT"),
    ("notifications", "payload", "TEXT"),
    ("surveys", "campaign_id", "INTEGER"),
    ("devices", "location", "TEXT"),
    ("devices", "demo", "INTEGER DEFAULT 0"),
]


class DB:
    def __init__(self, path: str = DEFAULT_PATH):
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self._writes = 0
        with self.lock:
            if path != ":memory:":
                self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.executescript(SCHEMA)
            for table, col, typ in MIGRATIONS:
                cols = {r[1] for r in self.conn.execute(f"PRAGMA table_info({table})")}
                if col not in cols:
                    self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
            self.conn.executescript(INDEXES)
            self.conn.commit()

    def prune(self, now: float):
        """Drop raw time-series samples older than the retention window."""
        with self.lock:
            for table in ("telemetry", "app_samples"):
                self.conn.execute(f"DELETE FROM {table} WHERE ts<?", (now - RETENTION_SECONDS,))
            self.conn.execute("DELETE FROM rollups WHERE bucket<?", (now - ROLLUP_RETENTION,))
            self.conn.execute("DELETE FROM ai_calls WHERE ts<?", (now - ROLLUP_RETENTION,))
            self.conn.execute("DELETE FROM audit WHERE ts<?", (now - AUDIT_RETENTION,))
            self.conn.execute("DELETE FROM flow_runs WHERE started_at<?", (now - ROLLUP_RETENTION,))
            self.conn.commit()

    def q(self, sql: str, args: tuple = ()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def one(self, sql: str, args: tuple = ()) -> dict | None:
        rows = self.q(sql, args)
        return rows[0] if rows else None

    def x(self, sql: str, args: tuple = ()) -> int:
        with self.lock:
            cur = self.conn.execute(sql, args)
            self.conn.commit()
            return cur.lastrowid

    def many(self, sql: str, rows: list[tuple]):
        with self.lock:
            self.conn.executemany(sql, rows)
            self.conn.commit()
