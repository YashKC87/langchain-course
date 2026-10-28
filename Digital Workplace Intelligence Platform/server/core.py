"""Shared runtime context: storage, live hub, AI, and helpers used by every route module."""
import asyncio
import json
import time

from fastapi import HTTPException, WebSocket

from .ai import AI
from .db import DB

ONLINE_WINDOW = 90          # seconds since last telemetry to count as online
NOTIFY_LIMIT_PER_HOUR = 5   # notification-fatigue cap per device


class Hub:
    """Pushes live events to every connected dashboard."""

    def __init__(self):
        self.clients: set[WebSocket] = set()

    async def send(self, msg: dict):
        dead = []
        for ws in self.clients:
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)


class Ctx:
    def __init__(self, db: DB, ai: AI):
        self.db, self.ai, self.hub = db, ai, Hub()
        self._tasks: set[asyncio.Task] = set()
        ai.ledger = lambda *row: db.x("INSERT INTO ai_calls(ts,purpose,model,prompt_tokens,completion_tokens,"
                                      "latency_ms,ok) VALUES(?,?,?,?,?,?,?)", (time.time(), *row))

    def audit(self, actor: str, role: str, action: str, target: str = "", status: str = "ok", detail: str = ""):
        self.db.x("INSERT INTO audit(ts,actor,role,action,target,status,detail) VALUES(?,?,?,?,?,?,?)",
                  (time.time(), actor, role, action, target, status, detail[:500]))

    def spawn(self, coro):
        """Run a background coroutine (e.g. an LLM call) and keep a reference until it finishes."""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def device_by_key(self, key: str | None) -> dict:
        dev = self.db.one("SELECT * FROM devices WHERE key=?", (key or "",))
        if not dev:
            raise HTTPException(401, "unknown device key")
        return dev

    def device(self, device_id: str) -> dict:
        dev = self.db.one("SELECT * FROM devices WHERE id=?", (device_id,))
        if not dev:
            raise HTTPException(404, "device not found")
        return dev

    async def event(self, device_id: str | None, kind: str, message: str):
        ts = time.time()
        eid = self.db.x("INSERT INTO events(ts,device_id,kind,message) VALUES(?,?,?,?)",
                        (ts, device_id, kind, message))
        host = None
        if device_id:
            d = self.db.one("SELECT hostname FROM devices WHERE id=?", (device_id,))
            host = d and d["hostname"]
        await self.hub.send({"type": "event", "event": {"id": eid, "ts": ts, "device_id": device_id,
                                                         "hostname": host, "kind": kind, "message": message}})

    def notify(self, device_id: str, message: str, kind: str = "info", payload: dict | None = None,
               force: bool = False) -> bool:
        """Queue a user notification, respecting the per-hour fatigue cap unless forced."""
        if not force:
            recent = self.db.one("SELECT COUNT(*) n FROM notifications WHERE device_id=? AND created_at>? "
                                 "AND kind NOT IN ('message','guide')", (device_id, time.time() - 3600))["n"]
            if recent >= NOTIFY_LIMIT_PER_HOUR:
                return False
        self.db.x("INSERT INTO notifications(device_id,message,kind,created_at,payload) VALUES(?,?,?,?,?)",
                  (device_id, message, kind, time.time(), json.dumps(payload or {})))
        return True

    def sentiment(self, device_id: str) -> float | None:
        r = self.db.one("SELECT AVG(rating) a FROM (SELECT rating FROM surveys WHERE device_id=? "
                        "ORDER BY ts DESC LIMIT 5)", (device_id,))
        return None if r["a"] is None else r["a"] * 20

    def public(self, dev: dict, mask: bool = False) -> dict:
        """Device as the console sees it. `mask` hides the employee's name (viewer role)."""
        d = {k: v for k, v in dev.items() if k != "key"}
        if mask and d.get("user"):
            d["user"] = d["user"][0] + "•••"
        d["demo"] = bool(d.get("demo"))
        d["scores"] = json.loads(d["scores"] or "{}")
        d["metrics"] = json.loads(d["metrics"] or "{}")
        d["online"] = bool(d["last_seen"] and time.time() - d["last_seen"] < ONLINE_WINDOW)
        d["open_issues"] = self.db.one("SELECT COUNT(*) n FROM issues WHERE device_id=? AND status='open'",
                                       (d["id"],))["n"]
        return d

    async def deliver_guide(self, guide: dict, device_id: str, source: str) -> bool:
        """Send an in-app guide to a device (at most once per guide per device per day)."""
        recent = self.db.one("SELECT id FROM guide_deliveries WHERE guide_id=? AND device_id=? AND ts>?",
                             (guide["id"], device_id, time.time() - 86400))
        if recent:
            return False
        now = time.time()
        did = self.db.x("INSERT INTO guide_deliveries(guide_id,device_id,status,source,ts,updated_at) "
                        "VALUES(?,?,'sent',?,?,?)", (guide["id"], device_id, source, now, now))
        self.notify(device_id, f"{guide['icon'] or '💡'} New tip: {guide['title']}", "guide",
                    {"guide_id": guide["id"], "delivery_id": did}, force=True)
        dev = self.db.one("SELECT hostname FROM devices WHERE id=?", (device_id,))
        await self.event(device_id, "guide", f"Guide '{guide['title']}' sent to {dev['hostname']} ({source})")
        return True
