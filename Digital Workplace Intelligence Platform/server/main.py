"""DWIP server: enrolment, telemetry ingestion, N-DUDE-N pipeline, AI alerting and dashboard API.

Run:  python -m uvicorn server.main:app --host 0.0.0.0 --port 8000
"""
import json
import os
import random
import secrets
import time

from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import analytics, brain, collab, flows, identity, intel, ops
from .ai import AI, rule_insight
from .core import Ctx
from .db import DB, DEFAULT_PATH

STATIC = os.path.join(os.path.dirname(__file__), "static")
KINDS = ("laptop", "desktop", "mobile", "vdi")


class Enroll(BaseModel):
    token: str
    hostname: str
    kind: str = Field(pattern="^(laptop|desktop|mobile|vdi)$")
    platform: str
    os_version: str = ""
    model: str = ""
    user: str = ""
    department: str | None = None
    location: str | None = None
    demo: bool = False
    device_id: str | None = None


class AppSample(BaseModel):
    name: str
    version: str | None = None
    cpu_pct: float | None = None
    mem_mb: float | None = None
    crashes_24h: int | None = None
    hangs_24h: int | None = None
    latency_ms: float | None = None


class Telemetry(BaseModel):
    os_version: str | None = None
    metrics: dict
    apps: list[AppSample] = []


class ActionResult(BaseModel):
    ok: bool
    output: str = ""


class Survey(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = ""
    campaign_id: int | None = None


def create_app(db_path: str = DEFAULT_PATH, enroll_token: str | None = None,
               ai_enabled: bool | None = None, it_tokens: str | None = None) -> FastAPI:
    ctx = Ctx(DB(db_path), AI(ai_enabled))
    db = ctx.db
    token = enroll_token or os.environ.get("DWIP_ENROLL_TOKEN", "dev-token")
    tokens = identity.load_tokens(it_tokens)
    app = FastAPI(title="DWIP")
    app.state.default_enroll_token = token == "dev-token"

    # ---------- console identity, RBAC and audit ----------
    @app.middleware("http")
    async def guard(request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/") or path.startswith(identity.DEVICE_PATHS):
            return await call_next(request)
        if tokens:
            presented = request.headers.get("x-dwip-token") or                 request.headers.get("authorization", "").removeprefix("Bearer ").strip()
            who = identity.resolve(tokens, presented)
            if not who:
                return JSONResponse({"detail": "sign in required"}, 401)
            role, actor = who
        else:
            role, actor = "admin", "local-dev"
        need = identity.required_role(request.method, path)
        if not identity.allowed(role, need):
            ctx.audit(actor, role, f"{request.method} {path}", "", "denied", f"needs {need}")
            return JSONResponse({"detail": f"requires the {need} role"}, 403)
        request.state.role, request.state.actor = role, actor
        response = await call_next(request)
        if request.method != "GET" and path not in identity.READ_ONLY_POSTS:
            ctx.audit(actor, role, f"{request.method} {path}", "",
                      "ok" if response.status_code < 400 else f"http {response.status_code}")
        return response

    def masked(request: Request) -> bool:
        return getattr(request.state, "role", "admin") == "viewer"

    # ---------- AI alerting ----------
    async def raise_alert(scope: str, type_: str, severity: str, title: str, context: dict,
                          device_id: str | None = None) -> int:
        alert = {"type": type_, "title": title}
        insight = rule_insight(alert, context)   # instant; the LLM refines it in the background
        now = time.time()
        aid = db.x("INSERT INTO alerts(ts,scope,device_id,type,severity,title,insight,insight_source,devices,"
                   "status,updated_at) VALUES(?,?,?,?,?,?,?,'rules',?,'open',?)",
                   (now, scope, device_id, type_, severity, title, insight,
                    context.get("devices_affected", 1), now))
        await ctx.event(device_id, "alert", f"🚨 {title}")
        await ctx.hub.send({"type": "alert", "id": aid})
        if await ctx.ai.available():
            ctx.spawn(enrich_alert(aid, alert, context))
        dev = db.one("SELECT * FROM devices WHERE id=?", (device_id,)) if device_id else None
        await flows.fire(ctx, "alert_raised", type_, dev, {"alert": {"id": aid, "type": type_, "title": title,
                                                                   "severity": severity, "devices": context.get(
                                                                       "devices_affected", 1)}})
        return aid

    async def enrich_alert(aid: int, alert: dict, context: dict):
        text, source = await ctx.ai.insight(alert, context)
        if source == "llm":
            db.x("UPDATE alerts SET insight=?, insight_source='llm', updated_at=? WHERE id=?",
                 (text, time.time(), aid))
            await ctx.hub.send({"type": "alert", "id": aid})

    async def correlate(issue_type: str, title: str):
        if db.one("SELECT id FROM alerts WHERE scope='fleet' AND type=? AND status IN ('open','ack')", (issue_type,)):
            return
        context = analytics.fleet_candidates(db, issue_type)
        if context:
            await raise_alert("fleet", issue_type, "high",
                              f"{title} on {context['devices_affected']} devices", context)

    async def maybe_close_fleet_alert(issue_type: str):
        n = db.one("SELECT COUNT(DISTINCT device_id) n FROM issues WHERE type=? AND status='open'", (issue_type,))["n"]
        if n < 2:
            for a in db.q("SELECT id,title FROM alerts WHERE scope='fleet' AND type=? AND status IN ('open','ack')",
                          (issue_type,)):
                db.x("UPDATE alerts SET status='resolved', updated_at=? WHERE id=?", (time.time(), a["id"]))
                await ctx.event(None, "resolved", f"Fleet alert cleared: {a['title']}")

    async def auto_guides(dev: dict, issue_type: str):
        """In-app guidance: send the matching guide when an issue opens (most specific target first)."""
        guides = db.q("SELECT * FROM guides WHERE active=1 AND trigger_issue=? AND "
                      "(target_kind IS NULL OR target_kind=?) ORDER BY target_kind IS NULL",
                      (issue_type, dev["kind"]))
        if guides:
            await ctx.deliver_guide(guides[0], dev["id"], f"auto: {issue_type}")

    # ---------- agent API ----------
    @app.post("/api/enroll")
    async def enroll(e: Enroll):
        if not secrets.compare_digest(e.token, token):
            raise HTTPException(403, "bad enrolment token")
        device_id = e.device_id or secrets.token_hex(8)
        key = secrets.token_urlsafe(24)
        if db.one("SELECT id FROM devices WHERE id=?", (device_id,)):
            db.x("UPDATE devices SET key=?,hostname=?,kind=?,platform=?,os_version=?,model=?,user=?,"
                 "department=COALESCE(?,department),location=COALESCE(?,location),demo=? WHERE id=?",
                 (key, e.hostname, e.kind, e.platform, e.os_version, e.model, e.user, e.department,
                  e.location, int(e.demo), device_id))
        else:
            db.x("INSERT INTO devices(id,key,hostname,kind,platform,os_version,model,user,department,location,demo,"
                 "enrolled_at,dex,scores,metrics) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,NULL,'{}','{}')",
                 (device_id, key, e.hostname, e.kind, e.platform, e.os_version, e.model, e.user,
                  e.department, e.location, int(e.demo), time.time()))
            await ctx.event(device_id, "enroll", f"{e.hostname} joined the fleet ({e.kind}, {e.platform})")
            welcome = db.one("SELECT * FROM guides WHERE trigger_issue='onboarding' AND active=1")
            if welcome:
                await ctx.deliver_guide(welcome, device_id, "onboarding")
        return {"device_id": device_id, "key": key}

    @app.post("/api/telemetry")
    async def telemetry(t: Telemetry, x_device_key: str | None = Header(None)):
        dev = ctx.device_by_key(x_device_key)
        did, now, m = dev["id"], time.time(), t.metrics
        apps = [a.model_dump() for a in t.apps]
        if t.os_version:
            dev["os_version"] = t.os_version

        # application visibility
        if apps:
            db.many("INSERT OR REPLACE INTO apps_current(device_id,app,version,cpu,mem_mb,crashes,hangs,latency_ms,ts) "
                    "VALUES(?,?,?,?,?,?,?,?,?)", [(did, a["name"], a["version"], a["cpu_pct"], a["mem_mb"],
                                                   a["crashes_24h"], a["hangs_24h"], a["latency_ms"], now) for a in apps])
            db.many("INSERT INTO app_samples(device_id,ts,app,cpu,mem_mb,crashes,hangs,latency_ms) "
                    "VALUES(?,?,?,?,?,?,?,?)", [(did, now, a["name"], a["cpu_pct"], a["mem_mb"],
                                                 a["crashes_24h"], a["hangs_24h"], a["latency_ms"]) for a in apps])
            db.x("DELETE FROM apps_current WHERE device_id=? AND ts<?", (did, now - 600))
        if random.random() < 0.002:
            db.prune(now)

        # Notice + Discover
        findings = brain.evaluate(dev, m, apps)
        # Understand history: sentiment from past surveys and the device's own baseline
        scores = brain.score(m, ctx.sentiment(did), apps)
        anom = analytics.anomaly(db, did, scores["dex"])
        db.x("UPDATE devices SET last_seen=?,dex=?,scores=?,metrics=?,os_version=? WHERE id=?",
             (now, scores["dex"], json.dumps(scores), json.dumps(m), dev["os_version"], did))
        db.x("INSERT INTO telemetry(device_id,ts,dex,cpu,mem,disk,battery) VALUES(?,?,?,?,?,?,?)",
             (did, now, scores["dex"], m.get("cpu_pct"), m.get("mem_pct"), m.get("disk_pct"), m.get("battery_pct")))
        db.x("INSERT INTO rollups(bucket,device_id,n,dex_sum) VALUES(?,?,1,?) ON CONFLICT(bucket,device_id) "
             "DO UPDATE SET n=n+1, dex_sum=dex_sum+excluded.dex_sum", (int(now // 3600) * 3600, did, scores["dex"]))
        if anom and not db.one("SELECT id FROM alerts WHERE device_id=? AND type='anomaly' AND ts>?",
                               (did, now - 900)):
            await raise_alert("device", "anomaly", "medium",
                              f"{dev['hostname']}: experience dropped from {anom['baseline']} to {anom['current']}",
                              {**anom, "device": {k: dev[k] for k in ("hostname", "kind", "platform", "os_version")},
                               "metrics": m, "findings": [f["title"] for f in findings]}, did)

        open_issues = {i["type"]: i for i in
                       db.q("SELECT * FROM issues WHERE device_id=? AND status='open'", (did,))}
        found_types = {f["type"] for f in findings}

        for typ, issue in open_issues.items():
            if typ not in found_types:
                db.x("UPDATE issues SET status='resolved',resolved_at=? WHERE id=?", (now, issue["id"]))
                await ctx.event(did, "resolved", f"{dev['hostname']}: {issue['title']} resolved")
                await maybe_close_fleet_alert(typ)

        # Decide + Execute for new findings
        for f in findings:
            if f["type"] in open_issues:
                continue
            iid = db.x("INSERT INTO issues(device_id,type,severity,title,detail,status,opened_at) "
                       "VALUES(?,?,?,?,?,'open',?)", (did, f["type"], f["severity"], f["title"], f["detail"], now))
            await ctx.event(did, "issue", f"{dev['hostname']}: {f['title']} — {f['detail']}")
            if f["action"]:
                status = "queued" if f["risk"] == "low" else "pending_approval"
                db.x("INSERT INTO actions(device_id,issue_id,action,target,risk,status,created_at,updated_at) "
                     "VALUES(?,?,?,?,?,?,?,?)", (did, iid, f["action"], f["target"], f["risk"], status, now, now))
                verb = "auto-fix queued" if status == "queued" else "waiting for IT approval"
                if status == "queued":
                    ctx.audit("policy", "system", "remediation.auto", f"{f['action']} on {dev['hostname']}",
                              "queued", "low-risk catalogue action (policy-controlled automation)")
                await ctx.event(did, "decision", f"{dev['hostname']}: {f['action']} ({f['risk']} risk) — {verb}")
            else:
                ctx.notify(did, f"Heads up: {f['title'].lower()} ({f['detail']}).", "advice")
            await auto_guides(dev, f["type"])
            await flows.fire(ctx, "issue_opened", f["type"], {**dev, "metrics": json.dumps(m)},
                             {"issue": {"id": iid, "type": f["type"], "severity": f["severity"],
                                        "title": f["title"], "detail": f["detail"]}})
            await correlate(f["type"], f["title"])

        await ctx.hub.send({"type": "telemetry", "device_id": did, "dex": scores["dex"]})
        return {"dex": scores["dex"], "findings": len(findings)}

    @app.get("/api/agent/commands")
    async def commands(x_device_key: str | None = Header(None)):
        dev = ctx.device_by_key(x_device_key)
        acts = db.q("SELECT id,action,target FROM actions WHERE device_id=? AND status='queued'", (dev["id"],))
        for a in acts:
            db.x("UPDATE actions SET status='sent',updated_at=? WHERE id=?", (time.time(), a["id"]))
        notes = db.q("SELECT id,message,kind,payload FROM notifications WHERE device_id=? AND delivered=0",
                     (dev["id"],))
        for n in notes:
            db.x("UPDATE notifications SET delivered=1 WHERE id=?", (n["id"],))
            n["payload"] = json.loads(n["payload"] or "{}")
        return {"actions": acts, "notifications": notes}

    @app.post("/api/agent/actions/{action_id}/result")
    async def action_result(action_id: int, r: ActionResult, x_device_key: str | None = Header(None)):
        dev = ctx.device_by_key(x_device_key)
        act = db.one("SELECT * FROM actions WHERE id=? AND device_id=?", (action_id, dev["id"]))
        if not act:
            raise HTTPException(404)
        db.x("UPDATE actions SET status=?,result=?,updated_at=? WHERE id=?",
             ("done" if r.ok else "failed", r.output[:2000], time.time(), action_id))
        label = act["action"] + (f" ({act['target']})" if act["target"] else "")
        if r.ok:
            ctx.notify(dev["id"], brain.action_message(act["action"], act["target"]), "fix")
            ctx.notify(dev["id"], "How is your device feeling today?", "survey")
            await ctx.event(dev["id"], "executed", f"{dev['hostname']}: {label} succeeded")
        else:
            await ctx.event(dev["id"], "failed", f"{dev['hostname']}: {label} failed — {r.output[:120]}")
        return {"ok": True}

    @app.post("/api/agent/survey")
    async def survey(s: Survey, x_device_key: str | None = Header(None)):
        dev = ctx.device_by_key(x_device_key)
        db.x("INSERT INTO surveys(device_id,rating,comment,ts,campaign_id) VALUES(?,?,?,?,?)",
             (dev["id"], s.rating, s.comment, time.time(), s.campaign_id))
        note = f" — “{s.comment[:80]}”" if s.comment else ""
        await ctx.event(dev["id"], "survey", f"{dev['hostname']} rated {'★' * s.rating}{note}")
        return {"ok": True}

    # ---------- dashboard API ----------
    def summary():
        devs = [ctx.public(d) for d in db.q("SELECT * FROM devices")]
        scored = [d["dex"] for d in devs if d["dex"] is not None]
        sat = db.one("SELECT AVG(rating) a FROM surveys")["a"]
        return {
            "devices": len(devs), "online": sum(d["online"] for d in devs),
            "by_kind": {k: sum(1 for d in devs if d["kind"] == k) for k in KINDS},
            "dex": round(sum(scored) / len(scored), 1) if scored else None,
            "open_issues": db.one("SELECT COUNT(*) n FROM issues WHERE status='open'")["n"],
            "fixed": db.one("SELECT COUNT(*) n FROM actions WHERE status='done'")["n"],
            "pending_approvals": db.one("SELECT COUNT(*) n FROM actions WHERE status='pending_approval'")["n"],
            "alerts": db.one("SELECT COUNT(*) n FROM alerts WHERE status='open'")["n"],
            "apps": db.one("SELECT COUNT(DISTINCT app) n FROM apps_current")["n"],
            "conversations": db.one("SELECT COUNT(*) n FROM conversations WHERE status='open'")["n"],
            "unread": db.one("SELECT COALESCE(SUM(unread_it),0) n FROM conversations")["n"],
            "satisfaction": round(sat, 2) if sat else None,
        }

    app.get("/api/summary")(summary)

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    @app.get("/api/devices")
    def devices(request: Request, kind: str | None = None, location: str | None = None,
                department: str | None = None, data: str | None = None):
        w, args = intel.where({"kind": kind, "location": location, "department": department, "data": data})
        rows = db.q(f"SELECT * FROM devices d WHERE {w} ORDER BY hostname", args)
        return [ctx.public(d, masked(request)) for d in rows]

    @app.get("/api/devices/{device_id}")
    def device(device_id: str, request: Request):
        d = ctx.public(ctx.device(device_id), masked(request))
        d["history"] = list(reversed(db.q(
            "SELECT ts,dex,cpu,mem,disk,battery FROM telemetry WHERE device_id=? ORDER BY ts DESC LIMIT 60",
            (device_id,))))
        d["issues"] = db.q("SELECT * FROM issues WHERE device_id=? ORDER BY opened_at DESC LIMIT 20", (device_id,))
        d["actions"] = db.q("SELECT * FROM actions WHERE device_id=? ORDER BY created_at DESC LIMIT 20", (device_id,))
        d["surveys"] = db.q("SELECT rating,comment,ts FROM surveys WHERE device_id=? ORDER BY ts DESC LIMIT 5",
                            (device_id,))
        d["apps"] = db.q("SELECT * FROM apps_current WHERE device_id=? ORDER BY crashes DESC, cpu DESC", (device_id,))
        d["guides"] = db.q("SELECT x.status, x.source, x.ts, g.title, g.icon FROM guide_deliveries x JOIN guides g "
                           "ON g.id=x.guide_id WHERE x.device_id=? ORDER BY x.ts DESC LIMIT 10", (device_id,))
        d["conversations"] = db.q("SELECT id, subject, status, updated_at FROM conversations WHERE device_id=? "
                                  "ORDER BY updated_at DESC LIMIT 5", (device_id,))
        return d

    @app.get("/api/events")
    def events(limit: int = 40):
        return db.q("SELECT e.*, d.hostname FROM events e LEFT JOIN devices d ON d.id=e.device_id "
                    "ORDER BY e.id DESC LIMIT ?", (min(limit, 200),))

    @app.get("/api/approvals")
    def approvals():
        return db.q("SELECT a.*, d.hostname, i.title, i.detail FROM actions a "
                    "JOIN devices d ON d.id=a.device_id LEFT JOIN issues i ON i.id=a.issue_id "
                    "WHERE a.status='pending_approval' ORDER BY a.created_at")

    @app.post("/api/actions/{action_id}/{decision}")
    async def decide(action_id: int, decision: str):
        if decision not in ("approve", "reject"):
            raise HTTPException(400)
        act = db.one("SELECT a.*, d.hostname FROM actions a JOIN devices d ON d.id=a.device_id "
                     "WHERE a.id=? AND a.status='pending_approval'", (action_id,))
        if not act:
            raise HTTPException(404)
        status = "queued" if decision == "approve" else "rejected"
        db.x("UPDATE actions SET status=?,updated_at=? WHERE id=?", (status, time.time(), action_id))
        await ctx.event(act["device_id"], "approval", f"IT {decision}d {act['action']} on {act['hostname']}")
        return {"status": status}

    @app.post("/api/devices/{device_id}/survey")
    async def request_survey(device_id: str):
        ctx.device(device_id)
        return {"sent": ctx.notify(device_id, "Quick one: how is your device feeling today?", "survey")}

    @app.get("/api/alerts")
    def alerts(status: str = "active"):
        where = "a.status IN ('open','ack')" if status == "active" else "1=1"
        return db.q(f"SELECT a.*, d.hostname FROM alerts a LEFT JOIN devices d ON d.id=a.device_id "
                    f"WHERE {where} ORDER BY a.status='ack', a.ts DESC LIMIT 60")

    @app.post("/api/alerts/{alert_id}/{op}")
    async def alert_op(alert_id: int, op: str):
        if op not in ("ack", "resolve"):
            raise HTTPException(400)
        a = db.one("SELECT * FROM alerts WHERE id=?", (alert_id,))
        if not a:
            raise HTTPException(404)
        db.x("UPDATE alerts SET status=?, updated_at=? WHERE id=?",
             ("ack" if op == "ack" else "resolved", time.time(), alert_id))
        await ctx.event(a["device_id"], "alert", f"Alert {'acknowledged' if op == 'ack' else 'resolved'}: {a['title']}")
        return {"ok": True}

    @app.get("/api/predictions")
    def predictions():
        return analytics.predictions(db)

    @app.get("/api/apps")
    def apps_list():
        return analytics.app_stats(db)

    @app.get("/api/apps/{name}")
    def app_info(name: str):
        return analytics.app_detail(db, name)

    collab.register(app, ctx, summary)
    intel.register(app, ctx, "token" if tokens else "dev")
    flows.register(app, ctx)
    ops.register(app, ctx, token)

    @app.websocket("/ws")
    async def ws(socket: WebSocket):
        if tokens and not identity.resolve(tokens, socket.query_params.get("token")):
            await socket.close(code=4401)
            return
        await socket.accept()
        ctx.hub.clients.add(socket)
        try:
            while True:
                await socket.receive_text()
        except WebSocketDisconnect:
            ctx.hub.clients.discard(socket)

    # ---------- UI ----------
    @app.get("/")
    def index():
        return FileResponse(os.path.join(STATIC, "index.html"))

    @app.get("/companion")
    def companion():
        return FileResponse(os.path.join(STATIC, "companion.html"))

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


app = create_app()
