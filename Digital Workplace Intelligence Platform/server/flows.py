"""Flows: low-code workflows that orchestrate detection, decisions and remediation.

A flow is a graph of nodes (start, condition, action, notify_user, notify_it, guide, service_api, end)
joined by edges. The engine is deterministic: no LLM decides anything here. Every run is logged step by step,
can be a dry run (no side effects), and respects the same safety rules as the rest of DWIP:
- remediation uses only catalogue actions; medium/high risk still waits for an engineer's approval
- Service/API calls go only to allowlisted hosts (DWIP_FLOW_ALLOWED_HOSTS), with a timeout
- secrets are referenced as {{secret.NAME}} (env DWIP_SECRET_NAME) and never written to run logs
- each flow has a runs-per-hour cap so a fleet-wide event can't start a storm
"""
import json
import os
import re
import time
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from . import brain
from .core import Ctx

NODE_TYPES = {
    "start": {"label": "Start", "ports": ["out"]},
    "condition": {"label": "Condition", "ports": ["yes", "no"]},
    "action": {"label": "Remote action", "ports": ["out"]},
    "notify_user": {"label": "Notify employee", "ports": ["out"]},
    "notify_it": {"label": "Notify IT", "ports": ["out"]},
    "guide": {"label": "Send guide", "ports": ["out"]},
    "service_api": {"label": "Service/API", "ports": ["out"]},
    "script": {"label": "Run script", "ports": ["out"]},
    "end": {"label": "End state", "ports": []},
}
OPS = ["equals", "not_equals", "greater_than", "less_than", "contains", "starts_with", "is_set", "is_empty"]
FIELDS = ["device.kind", "device.platform", "device.os_version", "device.location", "device.department",
          "device.dex", "metrics.cpu_pct", "metrics.mem_pct", "metrics.disk_pct", "metrics.battery_pct",
          "metrics.patch_age_days", "metrics.uptime_hours", "metrics.session_latency_ms", "issue.type",
          "issue.severity", "alert.type", "alert.devices", "input.incident_number"]
TRIGGERS = ["manual", "issue_opened", "alert_raised"]
MANAGED = ("laptop", "desktop", "vdi")
MAX_STEPS = 50
API_TIMEOUT = 10


# ---------- model ----------
class FlowIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    trigger: dict = {"type": "manual"}
    graph: dict = {"nodes": [], "edges": []}
    enabled: bool = False
    max_runs_per_hour: int = Field(50, ge=1, le=1000)


class RunIn(BaseModel):
    device_id: str | None = None
    dry_run: bool = True
    input: dict = {}


def validate(graph: dict, trigger: dict) -> list[str]:
    errs = []
    nodes = {n.get("id"): n for n in graph.get("nodes", [])}
    if trigger.get("type") not in TRIGGERS:
        errs.append(f"Trigger must be one of {', '.join(TRIGGERS)}")
    starts = [n for n in nodes.values() if n.get("type") == "start"]
    if len(starts) != 1:
        errs.append("A flow needs exactly one Start node")
    for n in nodes.values():
        if n.get("type") not in NODE_TYPES:
            errs.append(f"Unknown node type {n.get('type')!r}")
        c = n.get("config") or {}
        if n.get("type") == "action" and c.get("action") not in brain.ACTIONS:
            errs.append(f"Node '{n.get('title') or n['id']}': pick an action from the approved catalogue")
        if n.get("type") == "condition" and (not c.get("field") or c.get("op") not in OPS):
            errs.append(f"Node '{n.get('title') or n['id']}': condition needs a field and an operator")
        if n.get("type") == "script" and not c.get("script_id"):
            errs.append(f"Node '{n.get('title') or n['id']}': pick an approved script")
        if n.get("type") == "service_api" and not str(c.get("url", "")).startswith(("https://", "http://")):
            errs.append(f"Node '{n.get('title') or n['id']}': Service/API needs a URL")
    seen = set()
    for e in graph.get("edges", []):
        if e.get("from") not in nodes or e.get("to") not in nodes:
            errs.append("An edge points to a missing node")
            continue
        if e.get("port") not in NODE_TYPES.get(nodes[e["from"]].get("type"), {}).get("ports", []):
            errs.append(f"Invalid output '{e.get('port')}' on node '{e['from']}'")
        if (e["from"], e.get("port")) in seen:
            errs.append(f"Node '{nodes[e['from']].get('title') or e['from']}' has two links from one output")
        seen.add((e["from"], e.get("port")))
    # cycles: walk from every node
    nxt = {}
    for e in graph.get("edges", []):
        nxt.setdefault(e.get("from"), []).append(e.get("to"))

    def cyclic(n, path):
        if n in path:
            return True
        return any(cyclic(m, path | {n}) for m in nxt.get(n, []))
    if starts and cyclic(starts[0]["id"], frozenset()):
        errs.append("Flows can't contain loops")
    return errs


# ---------- engine ----------
def get_field(vars_: dict, path: str):
    cur = vars_
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def render(text: str, vars_: dict, secrets: bool = False) -> str:
    def sub(m):
        key = m.group(1).strip()
        if key.startswith("secret."):
            return os.environ.get("DWIP_SECRET_" + key[7:].upper(), "") if secrets else "••••"
        v = get_field(vars_, key)
        return "" if v is None else str(v)
    return re.sub(r"\{\{\s*([\w.]+)\s*\}\}", sub, str(text or ""))


def check(cond: dict, vars_: dict) -> bool:
    v, op, want = get_field(vars_, cond.get("field", "")), cond.get("op"), cond.get("value", "")
    if op == "is_set":
        return v not in (None, "")
    if op == "is_empty":
        return v in (None, "")
    if v is None:
        return False
    if op in ("greater_than", "less_than"):
        try:
            a, b = float(v), float(want)
        except (TypeError, ValueError):
            return False
        return a > b if op == "greater_than" else a < b
    a, b = str(v).lower(), str(want).lower()
    return {"equals": a == b, "not_equals": a != b, "contains": b in a, "starts_with": a.startswith(b)}.get(op, False)


def allowed_host(url: str) -> bool:
    hosts = {h.strip().lower() for h in os.environ.get("DWIP_FLOW_ALLOWED_HOSTS", "").split(",") if h.strip()}
    return (urlparse(url).hostname or "").lower() in hosts


async def run_flow(ctx: Ctx, flow: dict, device: dict | None, dry_run: bool, extra: dict, actor: str) -> dict:
    db = ctx.db
    graph = json.loads(flow["graph"])
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = {(e["from"], e["port"]): e["to"] for e in graph["edges"]}
    dev_pub = ctx.public(device) if device else {}
    vars_ = {"device": {k: dev_pub.get(k) for k in ("id", "hostname", "kind", "platform", "os_version", "location",
                                                     "department", "user", "dex")} if device else {},
             "metrics": dev_pub.get("metrics", {}), "issue": extra.get("issue", {}), "alert": extra.get("alert", {}),
             "input": extra.get("input", {}), "steps": {}}
    started = time.time()
    rid = db.x("INSERT INTO flow_runs(flow_id,flow_version,device_id,trigger,dry_run,status,started_at,steps,actor) "
               "VALUES(?,?,?,?,?,'running',?,'[]',?)", (flow["id"], flow["version"], device and device["id"],
                                                        extra.get("trigger", "manual"), int(dry_run), started, actor))
    steps, status = [], "completed"
    node = next(n for n in nodes.values() if n["type"] == "start")
    who = dev_pub.get("hostname") or "no device"
    while node and len(steps) < MAX_STEPS:
        t0, c, port = time.perf_counter(), node.get("config") or {}, "out"
        st = {"node": node["id"], "type": node["type"], "title": node.get("title") or NODE_TYPES[node["type"]]["label"]}
        try:
            if node["type"] == "start":
                st["result"] = f"Triggered ({extra.get('trigger', 'manual')}) for {who}"
            elif node["type"] == "condition":
                ok = check(c, vars_)
                port = "yes" if ok else "no"
                st["result"] = f"{c.get('field')} = {get_field(vars_, c.get('field', ''))!r} → {port}"
            elif node["type"] == "action":
                name, target = c.get("action"), render(c.get("target", ""), vars_) or None
                risk = brain.ACTIONS[name][0]
                if not device:
                    raise ValueError("needs a device")
                if device["kind"] not in MANAGED:
                    raise ValueError(f"{device['kind']} devices can't run scripted actions")
                status_ = "queued" if risk == "low" else "pending_approval"
                if dry_run:
                    st["result"] = f"Would queue {name} ({risk} risk, {'auto' if risk == 'low' else 'needs approval'})"
                else:
                    now = time.time()
                    aid = db.x("INSERT INTO actions(device_id,issue_id,action,target,risk,status,created_at,updated_at) "
                               "VALUES(?,?,?,?,?,?,?,?)", (device["id"], extra.get("issue", {}).get("id"), name,
                                                           target, risk, status_, now, now))
                    vars_["steps"][node["id"]] = {"action_id": aid, "status": status_}
                    st["result"] = f"{name} {'queued' if risk == 'low' else 'waiting for engineer approval'} (#{aid})"
                    await ctx.event(device["id"], "decision", f"Flow '{flow['name']}': {name} on {who} ({status_})")
            elif node["type"] == "notify_user":
                msg = render(c.get("message", ""), vars_)
                if not device:
                    raise ValueError("needs a device")
                st["result"] = f"Would send: {msg}" if dry_run else (
                    "Sent" if ctx.notify(device["id"], msg, "message", force=bool(c.get("force"))) else
                    "Skipped: notification limit reached")
            elif node["type"] == "notify_it":
                msg = render(c.get("message", ""), vars_)
                hook = os.environ.get("DWIP_TEAMS_WEBHOOK")
                if dry_run:
                    st["result"] = f"Would post: {msg}" + (" (+ Teams)" if hook else "")
                else:
                    await ctx.event(device and device["id"], "alert", f"Flow '{flow['name']}': {msg}")
                    if hook:
                        async with httpx.AsyncClient(timeout=API_TIMEOUT) as cl:
                            await cl.post(hook, json={"text": msg})
                    st["result"] = "Posted to activity feed" + (" and Teams" if hook else "")
            elif node["type"] == "guide":
                g = db.one("SELECT * FROM guides WHERE id=?", (c.get("guide_id"),))
                if not g or not device:
                    raise ValueError("guide or device missing")
                st["result"] = f"Would send guide '{g['title']}'" if dry_run else (
                    "Guide sent" if await ctx.deliver_guide(g, device["id"], f"flow: {flow['name']}")
                    else "Skipped: already sent today")
            elif node["type"] == "script":
                s = db.one("SELECT * FROM scripts WHERE id=?", (c.get("script_id"),))
                if not s or s["status"] != "approved":
                    raise ValueError("script missing or not approved")
                if not device:
                    raise ValueError("needs a device")
                r = await ctx.queue_script(s, device, dry_run, actor, f"flow: {flow['name']}")
                vars_["steps"][node["id"]] = r
                if r["status"] == "skipped":
                    raise ValueError(r["detail"])
                st["result"] = r["detail"] or f"'{s['name']}' {r['status'].replace('_', ' ')} (run #{r['run_id']})"
            elif node["type"] == "service_api":
                url = render(c.get("url", ""), vars_)
                method = (c.get("method") or "GET").upper()
                if method not in ("GET", "POST", "PUT", "PATCH"):
                    raise ValueError("method not allowed")
                if not allowed_host(url):
                    raise ValueError(f"host {urlparse(url).hostname!r} is not in DWIP_FLOW_ALLOWED_HOSTS")
                if dry_run:
                    st["result"] = f"Would call {method} {url}"
                else:
                    headers = {k: render(v, vars_, secrets=True) for k, v in (c.get("headers") or {}).items()}
                    body = render(c.get("body", ""), vars_) or None
                    async with httpx.AsyncClient(timeout=API_TIMEOUT) as cl:
                        r = await cl.request(method, url, headers=headers, content=body)
                    try:
                        data = r.json()
                    except ValueError:
                        data = r.text[:500]
                    vars_["steps"][node["id"]] = {"status": r.status_code, "json": data}
                    st["result"] = f"{method} {url} → HTTP {r.status_code}"
                    if r.status_code >= 400:
                        raise ValueError(f"HTTP {r.status_code}")
            elif node["type"] == "end":
                st["result"] = c.get("outcome") or "Done"
            st["status"] = "ok"
        except (ValueError, KeyError, httpx.HTTPError) as e:
            st["status"], st["result"] = "failed", f"{st.get('result', '')} {type(e).__name__}: {e}".strip()
            status = "failed"
        st["ms"] = round((time.perf_counter() - t0) * 1000, 1)
        steps.append(st)
        if st["status"] == "failed":
            break
        nxt = edges.get((node["id"], port))
        node = nodes.get(nxt) if nxt else None
    if len(steps) >= MAX_STEPS:
        status = "failed"
    db.x("UPDATE flow_runs SET status=?, finished_at=?, steps=? WHERE id=?",
         (status, time.time(), json.dumps(steps), rid))
    ctx.audit(actor, "system" if actor == "flow-trigger" else "engineer",
              "flow.run" + (".dry" if dry_run else ""), f"{flow['name']} on {who}", status, f"run #{rid}")
    await ctx.hub.send({"type": "flow_run", "id": rid, "flow_id": flow["id"]})
    return {"id": rid, "status": status, "dry_run": dry_run, "steps": steps}


def _matches(flow: dict, kind: str, value: str) -> bool:
    t = json.loads(flow["trigger"])
    return t.get("type") == kind and value.startswith(t.get("match", "") or "")


async def fire(ctx: Ctx, kind: str, value: str, device: dict | None, extra: dict):
    """Start enabled flows whose trigger matches (issue_opened / alert_raised)."""
    for f in ctx.db.q("SELECT * FROM flows WHERE enabled=1"):
        if not _matches(f, kind, value):
            continue
        recent = ctx.db.one("SELECT COUNT(*) n FROM flow_runs WHERE flow_id=? AND started_at>? AND trigger<>'manual'",
                            (f["id"], time.time() - 3600))["n"]
        if recent >= f["max_runs_per_hour"]:
            continue
        await run_flow(ctx, f, device, False, {**extra, "trigger": kind}, "flow-trigger")


# ---------- samples ----------
def _sample(nodes, edges):
    return {"nodes": nodes, "edges": [{"from": a, "port": p, "to": b} for a, p, b in edges]}


SEEDS = [
    ("Teams crash response", "When Teams keeps crashing: repair it on managed devices, guide mobile users, tell IT.",
     {"type": "issue_opened", "match": "app_crash:Teams"},
     _sample([
         {"id": "s", "type": "start", "x": 260, "y": 20, "title": "Start"},
         {"id": "c1", "type": "condition", "x": 200, "y": 120, "title": "Is it a phone?",
          "config": {"field": "device.kind", "op": "equals", "value": "mobile"}},
         {"id": "g", "type": "notify_user", "x": 20, "y": 290, "title": "Tell the employee",
          "config": {"message": "Teams keeps closing on your phone. Please update it from the app store."}},
         {"id": "a", "type": "action", "x": 380, "y": 290, "title": "Repair Teams",
          "config": {"action": "repair_app", "target": "Teams"}},
         {"id": "n", "type": "notify_it", "x": 380, "y": 420, "title": "Tell IT",
          "config": {"message": "Teams repair requested on {{device.hostname}} ({{device.location}})"}},
         {"id": "e1", "type": "end", "x": 20, "y": 420, "title": "End state"},
         {"id": "e2", "type": "end", "x": 380, "y": 540, "title": "End state"}],
         [("s", "out", "c1"), ("c1", "yes", "g"), ("c1", "no", "a"), ("g", "out", "e1"), ("a", "out", "n"),
          ("n", "out", "e2")])),
    ("Incident follow-up", "Manual: if an incident number was given, look up the ticket in ServiceNow.",
     {"type": "manual"},
     _sample([
         {"id": "s", "type": "start", "x": 260, "y": 20, "title": "Start"},
         {"id": "c1", "type": "condition", "x": 200, "y": 120, "title": "Was an incident number provided?",
          "config": {"field": "input.incident_number", "op": "is_set"}},
         {"id": "e1", "type": "end", "x": 20, "y": 290, "title": "End state", "config": {"outcome": "No incident"}},
         {"id": "api", "type": "service_api", "x": 380, "y": 290, "title": "Get incident from ServiceNow",
          "config": {"method": "GET", "url": "https://your-instance.service-now.com/api/now/table/incident?"
                                            "number={{input.incident_number}}",
                     "headers": {"Authorization": "Basic {{secret.SNOW_BASIC}}"}}},
         {"id": "e2", "type": "end", "x": 380, "y": 420, "title": "End state"}],
         [("s", "out", "c1"), ("c1", "no", "e1"), ("c1", "yes", "api"), ("api", "out", "e2")])),
]


def seed(db):
    if db.one("SELECT COUNT(*) n FROM flows")["n"]:
        return
    now = time.time()
    for name, desc, trig, graph in SEEDS:   # samples start disabled: nothing runs until IT enables them
        db.x("INSERT INTO flows(name,description,trigger,graph,enabled,version,max_runs_per_hour,created_at,"
             "updated_at,updated_by) VALUES(?,?,?,?,0,1,50,?,?,'sample')",
             (name, desc, json.dumps(trig), json.dumps(graph), now, now))


# ---------- routes ----------
def register(app: FastAPI, ctx: Ctx):
    db = ctx.db
    seed(db)

    def out(f):
        return {**f, "trigger": json.loads(f["trigger"]), "graph": json.loads(f["graph"]), "enabled": bool(f["enabled"]),
                "last_run": db.one("SELECT id,status,started_at,dry_run FROM flow_runs WHERE flow_id=? "
                                   "ORDER BY id DESC LIMIT 1", (f["id"],))}

    def get(fid):
        f = db.one("SELECT * FROM flows WHERE id=?", (fid,))
        if not f:
            raise HTTPException(404, "flow not found")
        return f

    actor = lambda r: getattr(r.state, "actor", "local-dev")

    @app.get("/api/flows/meta")
    def meta():
        return {"node_types": NODE_TYPES, "ops": OPS, "fields": FIELDS, "triggers": TRIGGERS,
                "actions": [{"action": k, "risk": v[0]} for k, v in brain.ACTIONS.items()],
                "guides": db.q("SELECT id, title, icon FROM guides WHERE active=1"),
                "scripts": db.q("SELECT id, name, language, risk FROM scripts WHERE status='approved'"),
                "allowed_hosts": [h for h in os.environ.get("DWIP_FLOW_ALLOWED_HOSTS", "").split(",") if h],
                "teams_webhook": bool(os.environ.get("DWIP_TEAMS_WEBHOOK"))}

    @app.get("/api/flows")
    def list_flows():
        return [out(f) for f in db.q("SELECT * FROM flows ORDER BY name")]

    @app.get("/api/flows/{fid}")
    def one(fid: int):
        return out(get(fid))

    def save(f: FlowIn, fid: int | None, request: Request):
        errs = validate(f.graph, f.trigger)
        if f.enabled and errs:
            raise HTTPException(400, {"errors": errs})
        now = time.time()
        if fid is None:
            fid = db.x("INSERT INTO flows(name,description,trigger,graph,enabled,version,max_runs_per_hour,created_at,"
                       "updated_at,updated_by) VALUES(?,?,?,?,?,1,?,?,?,?)",
                       (f.name, f.description, json.dumps(f.trigger), json.dumps(f.graph), int(f.enabled),
                        f.max_runs_per_hour, now, now, actor(request)))
        else:
            get(fid)
            db.x("UPDATE flows SET name=?,description=?,trigger=?,graph=?,enabled=?,max_runs_per_hour=?,"
                 "version=version+1,updated_at=?,updated_by=? WHERE id=?",
                 (f.name, f.description, json.dumps(f.trigger), json.dumps(f.graph), int(f.enabled),
                  f.max_runs_per_hour, now, actor(request), fid))
        return {**out(get(fid)), "errors": errs}

    @app.post("/api/flows")
    def create(f: FlowIn, request: Request):
        return save(f, None, request)

    @app.put("/api/flows/{fid}")
    def update(fid: int, f: FlowIn, request: Request):
        return save(f, fid, request)

    @app.delete("/api/flows/{fid}")
    def delete(fid: int):
        get(fid)
        db.x("DELETE FROM flows WHERE id=?", (fid,))
        return {"ok": True}

    @app.post("/api/flows/{fid}/run")
    async def run(fid: int, r: RunIn, request: Request):
        f = get(fid)
        errs = validate(json.loads(f["graph"]), json.loads(f["trigger"]))
        if errs:
            raise HTTPException(400, {"errors": errs})
        dev = ctx.device(r.device_id) if r.device_id else None
        return await run_flow(ctx, f, dev, r.dry_run, {"input": r.input, "trigger": "manual"}, actor(request))

    @app.get("/api/flows/{fid}/runs")
    def runs(fid: int):
        rows = db.q("SELECT r.*, d.hostname FROM flow_runs r LEFT JOIN devices d ON d.id=r.device_id "
                    "WHERE flow_id=? ORDER BY r.id DESC LIMIT 30", (fid,))
        for x in rows:
            x["steps"] = json.loads(x["steps"] or "[]")
        return rows
