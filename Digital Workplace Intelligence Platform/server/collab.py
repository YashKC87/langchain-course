"""IT <-> employee collaboration, in-app guidance, engagement campaigns and the AI assistant."""
import json
import time

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from . import analytics
from .core import Ctx

SEED_GUIDES = [
    ("Welcome to DWIP", "👋", "How your device stays healthy and how to get help.", None, "onboarding", [
        "DWIP quietly checks your device's health — no personal content is collected.",
        "When we fix something automatically, you'll get a short message here.",
        "Need help? Open Help and ask the assistant, or tap 'Talk to IT'.",
        "Rate your device now and then — it directly shapes what IT improves."]),
    ("Free up phone storage", "📦", "Get space back in under two minutes.", "mobile", "disk_full", [
        "Open Settings → Storage to see what is using space.",
        "Delete downloaded videos and podcasts you've already watched.",
        "Turn on 'Optimise photos' to keep originals in the cloud.",
        "Offload apps you haven't used in a month."]),
    ("Free up disk space on your computer", "🧹", "Clear clutter safely.", None, "disk_full", [
        "Empty the Recycle Bin / Bin.",
        "Move large files from Downloads to OneDrive.",
        "Windows: Settings → System → Storage → turn on Storage Sense.",
        "Mac: Apple menu → System Settings → General → Storage → Recommendations."]),
    ("Make Microsoft Teams faster", "💬", "Fix a slow or laggy Teams.", None, "app_slow:Teams", [
        "Quit Teams fully (right-click the tray icon → Quit).",
        "Turn off background effects in meetings.",
        "Keep fewer than 10 chats pinned and close unused tabs.",
        "Still slow? Tap 'Talk to IT' and we'll reset the Teams cache for you."]),
    ("Keep your battery going", "🔋", "Simple habits for all-day battery.", None, "low_battery", [
        "Turn on battery saver / low power mode.",
        "Lower screen brightness a few notches.",
        "Close video calls and streaming tabs you are not using.",
        "Charge between 20% and 80% to keep the battery healthy longer."]),
    ("Install updates safely", "🔒", "Stay secure in 3 steps.", None, "os_patch_overdue", [
        "Save your work and plug in your charger.",
        "Open Settings → Update and install pending updates.",
        "Restart when asked — it usually takes under 10 minutes."]),
    ("Fix a laggy virtual desktop", "🖥️", "Smoother Citrix / AVD sessions.", "vdi", "vdi_latency", [
        "Close video and heavy browser tabs inside the session.",
        "Switch to a wired connection or move closer to the Wi-Fi router.",
        "Log off (don't just disconnect) and log back on to land on a fresh host.",
        "Still laggy? Tap 'Talk to IT' — we can move you to another host."]),
]


class Message(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class NewConversation(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=4000)


class Guide(BaseModel):
    title: str
    summary: str = ""
    icon: str = "💡"
    steps: list[str] = Field(min_length=1)
    target_kind: str | None = None
    trigger_issue: str | None = None


class Push(BaseModel):
    device_id: str | None = None
    kind: str | None = None


class Campaign(BaseModel):
    question: str = Field(min_length=3, max_length=300)
    target_kind: str | None = None
    department: str | None = None


class DeliveryUpdate(BaseModel):
    status: str = Field(pattern="^(viewed|completed|dismissed)$")


class Chat(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[dict] = []


def seed_guides(ctx: Ctx):
    if ctx.db.one("SELECT COUNT(*) n FROM guides")["n"]:
        return
    for title, icon, summary, kind, trigger, steps in SEED_GUIDES:
        ctx.db.x("INSERT INTO guides(title,summary,steps,target_kind,trigger_issue,icon,created_at) "
                 "VALUES(?,?,?,?,?,?,?)", (title, summary, json.dumps(steps), kind, trigger, icon, time.time()))


def guide_row(g: dict) -> dict:
    return {**g, "steps": json.loads(g["steps"] or "[]")}


def fleet_context(ctx: Ctx, summary: dict) -> dict:
    db = ctx.db
    worst = [{"hostname": d["hostname"], "kind": d["kind"], "platform": d["platform"], "dex": d["dex"],
              "open_issues": ctx.public(d)["open_issues"]}
             for d in db.q("SELECT * FROM devices WHERE dex IS NOT NULL ORDER BY dex LIMIT 8")]
    return {
        "summary": summary,
        "worst_devices": worst,
        "alerts": db.q("SELECT title,severity,insight,devices FROM alerts WHERE status='open' "
                       "ORDER BY ts DESC LIMIT 8"),
        "top_issues": db.q("SELECT title, COUNT(*) devices FROM issues WHERE status='open' "
                           "GROUP BY title ORDER BY devices DESC LIMIT 8"),
        "apps": analytics.app_stats(db)[:8],
        "predictions": [{k: p[k] for k in ("hostname", "title", "detail", "eta")}
                        for p in analytics.predictions(db)[:6]],
        "engagement": {k: v for k, v in analytics.engagement(db).items() if k != "comments"},
    }


def device_context(ctx: Ctx, dev: dict) -> dict:
    d = ctx.public(dev)
    return {
        "device": {k: d[k] for k in ("hostname", "kind", "platform", "os_version", "model", "dex")},
        "metrics": d["metrics"], "scores": d["scores"],
        "issues": ctx.db.q("SELECT title,detail FROM issues WHERE device_id=? AND status='open'", (dev["id"],)),
        "apps": ctx.db.q("SELECT app,version,cpu,mem_mb,crashes,latency_ms FROM apps_current WHERE device_id=?",
                         (dev["id"],)),
        "guides": [g["title"] for g in ctx.db.q("SELECT title FROM guides WHERE active=1")],
    }


def register(app: FastAPI, ctx: Ctx, summary_fn):
    db = ctx.db
    seed_guides(ctx)

    # ---------- conversations ----------
    def thread(cid: int) -> dict:
        c = db.one("SELECT c.*, d.hostname, d.user, d.kind FROM conversations c JOIN devices d "
                   "ON d.id=c.device_id WHERE c.id=?", (cid,))
        if not c:
            raise HTTPException(404)
        c["messages"] = db.q("SELECT * FROM messages WHERE conversation_id=? ORDER BY id", (cid,))
        return c

    async def post_message(cid: int, sender: str, text: str):
        now = time.time()
        mid = db.x("INSERT INTO messages(conversation_id,sender,text,ts) VALUES(?,?,?,?)", (cid, sender, text, now))
        col = "unread_it" if sender == "user" else "unread_user"
        db.x(f"UPDATE conversations SET updated_at=?, {col}={col}+1, status='open' WHERE id=?", (now, cid))
        await ctx.hub.send({"type": "message", "conversation_id": cid,
                            "message": {"id": mid, "sender": sender, "text": text, "ts": now}})

    async def ai_triage(cid: int, dev: dict, text: str):
        """AI looks at the device and posts a triage note for both IT and the user."""
        context = device_context(ctx, dev)
        answer, _ = await ctx.ai.chat(
            f"The employee reported: '{text}'. Briefly triage this using the device data and suggest a fix.",
            context, role="employee", background=True)
        await post_message(cid, "ai", answer)

    @app.post("/api/agent/conversations")
    async def employee_new(c: NewConversation, x_device_key: str | None = Header(None)):
        dev = ctx.device_by_key(x_device_key)
        now = time.time()
        cid = db.x("INSERT INTO conversations(device_id,subject,status,created_at,updated_at) "
                   "VALUES(?,?,'open',?,?)", (dev["id"], c.subject, now, now))
        await post_message(cid, "user", c.text)
        await ctx.event(dev["id"], "conversation", f"{dev['hostname']} asked IT: {c.subject}")
        if await ctx.ai.available():
            ctx.spawn(ai_triage(cid, dev, c.text))   # LLM can take seconds; don't block the user
        else:
            await ai_triage(cid, dev, c.text)
        return {"id": cid}

    @app.get("/api/agent/conversations")
    def employee_list(x_device_key: str | None = Header(None)):
        dev = ctx.device_by_key(x_device_key)
        out = [thread(c["id"]) for c in
               db.q("SELECT id FROM conversations WHERE device_id=? ORDER BY updated_at DESC LIMIT 10", (dev["id"],))]
        db.x("UPDATE conversations SET unread_user=0 WHERE device_id=?", (dev["id"],))
        return out

    @app.post("/api/agent/conversations/{cid}/messages")
    async def employee_reply(cid: int, m: Message, x_device_key: str | None = Header(None)):
        dev = ctx.device_by_key(x_device_key)
        if not db.one("SELECT id FROM conversations WHERE id=? AND device_id=?", (cid, dev["id"])):
            raise HTTPException(404)
        await post_message(cid, "user", m.text)
        return {"ok": True}

    @app.get("/api/conversations")
    def it_list():
        rows = db.q("SELECT c.*, d.hostname, d.user, d.kind, (SELECT text FROM messages m WHERE "
                    "m.conversation_id=c.id ORDER BY id DESC LIMIT 1) last FROM conversations c "
                    "JOIN devices d ON d.id=c.device_id ORDER BY c.status='closed', c.updated_at DESC LIMIT 60")
        return rows

    @app.get("/api/conversations/{cid}")
    def it_thread(cid: int):
        c = thread(cid)
        db.x("UPDATE conversations SET unread_it=0 WHERE id=?", (cid,))
        return c

    @app.post("/api/conversations/{cid}/messages")
    async def it_reply(cid: int, m: Message):
        c = thread(cid)
        await post_message(cid, "it", m.text)
        ctx.notify(c["device_id"], f"💬 IT replied: {m.text[:120]}", "message", {"conversation_id": cid}, force=True)
        return {"ok": True}

    @app.post("/api/conversations/{cid}/close")
    async def it_close(cid: int):
        c = thread(cid)
        db.x("UPDATE conversations SET status='closed', updated_at=? WHERE id=?", (time.time(), cid))
        await ctx.event(c["device_id"], "conversation", f"Conversation '{c['subject']}' with {c['hostname']} closed")
        return {"ok": True}

    @app.post("/api/devices/{device_id}/conversations")
    async def it_start(device_id: str, c: NewConversation):
        dev = ctx.device(device_id)
        now = time.time()
        cid = db.x("INSERT INTO conversations(device_id,subject,status,created_at,updated_at) "
                   "VALUES(?,?,'open',?,?)", (device_id, c.subject, now, now))
        await post_message(cid, "it", c.text)
        ctx.notify(device_id, f"💬 IT: {c.text[:120]}", "message", {"conversation_id": cid}, force=True)
        await ctx.event(device_id, "conversation", f"IT started a conversation with {dev['hostname']}: {c.subject}")
        return {"id": cid}

    # ---------- in-app guidance ----------
    @app.get("/api/guides")
    def guides():
        rows = db.q("SELECT g.*, (SELECT COUNT(*) FROM guide_deliveries x WHERE x.guide_id=g.id) sent, "
                    "(SELECT COUNT(*) FROM guide_deliveries x WHERE x.guide_id=g.id AND x.status='completed') "
                    "completed FROM guides g WHERE active=1 ORDER BY id")
        return [guide_row(g) for g in rows]

    @app.post("/api/guides")
    def create_guide(g: Guide):
        gid = db.x("INSERT INTO guides(title,summary,steps,target_kind,trigger_issue,icon,created_at) "
                   "VALUES(?,?,?,?,?,?,?)", (g.title, g.summary, json.dumps(g.steps), g.target_kind,
                                             g.trigger_issue, g.icon, time.time()))
        return {"id": gid}

    @app.post("/api/guides/{gid}/push")
    async def push_guide(gid: int, p: Push):
        g = db.one("SELECT * FROM guides WHERE id=?", (gid,))
        if not g:
            raise HTTPException(404)
        if p.device_id:
            targets = [p.device_id]
        else:
            targets = [d["id"] for d in db.q("SELECT id FROM devices" + (" WHERE kind=?" if p.kind else ""),
                                             (p.kind,) if p.kind else ())]
        sent = 0
        for t in targets:
            sent += await ctx.deliver_guide(g, t, "pushed by IT")
        return {"sent": sent}

    @app.get("/api/agent/guides")
    def employee_guides(x_device_key: str | None = Header(None)):
        dev = ctx.device_by_key(x_device_key)
        rows = db.q("SELECT x.id delivery_id, x.status, x.ts, x.source, g.* FROM guide_deliveries x JOIN guides g "
                    "ON g.id=x.guide_id WHERE x.device_id=? ORDER BY x.ts DESC LIMIT 20", (dev["id"],))
        library = db.q("SELECT * FROM guides WHERE active=1 AND (target_kind IS NULL OR target_kind=?)",
                       (dev["kind"],))
        return {"delivered": [guide_row(r) for r in rows], "library": [guide_row(g) for g in library]}

    @app.post("/api/agent/guides/{delivery_id}")
    async def employee_guide_progress(delivery_id: int, u: DeliveryUpdate, x_device_key: str | None = Header(None)):
        dev = ctx.device_by_key(x_device_key)
        row = db.one("SELECT x.*, g.title FROM guide_deliveries x JOIN guides g ON g.id=x.guide_id "
                     "WHERE x.id=? AND x.device_id=?", (delivery_id, dev["id"]))
        if not row:
            raise HTTPException(404)
        db.x("UPDATE guide_deliveries SET status=?, updated_at=? WHERE id=?", (u.status, time.time(), delivery_id))
        if u.status == "completed":
            await ctx.event(dev["id"], "guide", f"{dev['hostname']} completed guide '{row['title']}' ✅")
        return {"ok": True}

    # ---------- engagement ----------
    @app.get("/api/campaigns")
    def campaigns():
        rows = db.q("SELECT c.*, (SELECT COUNT(*) FROM surveys s WHERE s.campaign_id=c.id) responses, "
                    "(SELECT AVG(rating) FROM surveys s WHERE s.campaign_id=c.id) rating FROM campaigns c "
                    "ORDER BY c.id DESC")
        for r in rows:
            r["rating"] = round(r["rating"], 2) if r["rating"] else None
            r["response_rate"] = round(100 * r["responses"] / r["sent"]) if r["sent"] else None
        return rows

    @app.post("/api/campaigns")
    async def create_campaign(c: Campaign):
        cid = db.x("INSERT INTO campaigns(question,target_kind,department,created_at) VALUES(?,?,?,?)",
                   (c.question, c.target_kind, c.department, time.time()))
        where, args = [], []
        if c.target_kind:
            where.append("kind=?"); args.append(c.target_kind)  # noqa: E702
        if c.department:
            where.append("department=?"); args.append(c.department)  # noqa: E702
        targets = db.q("SELECT id FROM devices" + (" WHERE " + " AND ".join(where) if where else ""), tuple(args))
        sent = sum(ctx.notify(t["id"], c.question, "pulse", {"campaign_id": cid, "question": c.question},
                              force=True) for t in targets)
        db.x("UPDATE campaigns SET sent=? WHERE id=?", (sent, cid))
        await ctx.event(None, "pulse", f"Pulse survey sent to {sent} devices: “{c.question}”")
        return {"id": cid, "sent": sent}

    @app.get("/api/engagement")
    def engagement():
        return analytics.engagement(db)

    # ---------- AI assistant ----------
    @app.post("/api/assistant/chat")
    async def it_chat(c: Chat):
        context = fleet_context(ctx, summary_fn())
        answer, source = await ctx.ai.chat(c.question, context, "it", c.history)
        return {"answer": answer, "source": source, "model": ctx.ai.model if source == "llm" else None}

    @app.post("/api/agent/assistant")
    async def employee_chat(c: Chat, x_device_key: str | None = Header(None)):
        dev = ctx.device_by_key(x_device_key)
        answer, source = await ctx.ai.chat(c.question, device_context(ctx, dev), "employee", c.history)
        return {"answer": answer, "source": source}

    @app.get("/api/assistant/status")
    async def ai_status():
        return {"llm": await ctx.ai.available(), "model": ctx.ai.model}
