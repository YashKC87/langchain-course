"""Script library: controlled PowerShell / Python / Batch / JavaScript for device and application management.

Safety model (the LLM never writes or runs scripts):
- every saved change is a new version in "draft"; it runs only after an engineer approves that exact version
  (a different person from the author whenever console sign-in is on)
- the approved body's SHA-256 travels with each run; the agent re-hashes and refuses a mismatch
- high-risk scripts also need approval on every run
- the agent executes only if it was installed/started with --allow-scripts; phones never run scripts
- per-run device cap, agent-side timeout, full output and exit code recorded, every step audited
"""
import hashlib
import json
import time

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from .core import Ctx

LANGUAGES = {
    "powershell": {"label": "PowerShell", "ext": ".ps1", "platforms": ("windows", "avd", "citrix")},
    "batch": {"label": "Batch (cmd)", "ext": ".cmd", "platforms": ("windows", "avd", "citrix")},
    "python": {"label": "Python", "ext": ".py", "platforms": ("windows", "avd", "citrix", "macos", "linux")},
    "javascript": {"label": "JavaScript (Node.js)", "ext": ".js", "platforms": ("windows", "avd", "citrix", "macos", "linux")},
}
RISKS = ("low", "medium", "high")
MAX_DEVICES = 50
TIMEOUT_S = 120

SEEDS = [
    ("Flush DNS cache", "Clears the DNS resolver cache when sites fail to resolve.", "batch", "device", None, "low",
     "ipconfig /flushdns"),
    ("Set power plan to Balanced", "Switches the active power plan to Balanced.", "powershell", "device", None, "low",
     "powercfg /setactive SCHEME_BALANCED\npowercfg /getactivescheme"),
    ("Clear Teams cache", "Stops Teams and clears its cache folders. Teams restarts clean.", "powershell", "app", "Teams",
     "medium", "Get-Process ms-teams, Teams -ErrorAction SilentlyContinue | Stop-Process -Force\n"
               "$paths = \"$env:LOCALAPPDATA\\Packages\\MSTeams_8wekyb3d8bbwe\\LocalCache\\Microsoft\\MSTeams\", "
               "\"$env:APPDATA\\Microsoft\\Teams\\Cache\"\n"
               "foreach ($p in $paths) { if (Test-Path $p) { Remove-Item \"$p\\*\" -Recurse -Force -ErrorAction SilentlyContinue; \"cleared $p\" } }"),
    ("Report Python version", "Prints the Python version and platform.", "python", "device", None, "low",
     "import platform, sys\nprint(sys.version)\nprint(platform.platform())"),
    ("Report Node.js version", "Prints the Node.js version and OS.", "javascript", "device", None, "low",
     "console.log(process.version, process.platform, require('os').release())"),
]


def sha(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class ScriptIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    language: str
    target: str = "device"          # device | app
    app: str | None = None
    risk: str = "low"
    body: str = Field(min_length=1, max_length=20000)


class RunIn(BaseModel):
    device_ids: list[str] = []
    kind: str | None = None
    location: str | None = None
    app: str | None = None          # devices currently running this app
    dry_run: bool = True


def compatible(dev: dict, language: str) -> str | None:
    """Reason a device can't run this language, or None."""
    if dev["kind"] == "mobile":
        return "phones can't run scripts"
    plat = (dev["platform"] or "").lower()
    if plat not in LANGUAGES[language]["platforms"]:
        return f"{LANGUAGES[language]['label']} doesn't run on {plat or 'this platform'}"
    return None


def register(app: FastAPI, ctx: Ctx, tokens_on: bool):
    db = ctx.db
    who = lambda r: (getattr(r.state, "actor", "local-dev"), getattr(r.state, "role", "admin"))
    if not db.one("SELECT COUNT(*) n FROM scripts")["n"]:
        for name, desc, lang, target, app_, risk, body in SEEDS:   # samples are drafts: nothing runs unapproved
            db.x("INSERT INTO scripts(name,description,language,target,app,risk,body,sha256,version,status,"
                 "created_by,updated_at) VALUES(?,?,?,?,?,?,?,?,1,'draft','sample',?)",
                 (name, desc, lang, target, app_, risk, body, sha(body), time.time()))

    def get(sid):
        s = db.one("SELECT * FROM scripts WHERE id=?", (sid,))
        if not s:
            raise HTTPException(404, "script not found")
        return s

    @app.get("/api/scripts/meta")
    def meta():
        return {"languages": {k: v["label"] for k, v in LANGUAGES.items()}, "risks": RISKS,
                "max_devices": MAX_DEVICES, "timeout_s": TIMEOUT_S, "separate_approver": tokens_on,
                "apps": [r["app"] for r in db.q("SELECT DISTINCT app FROM apps_current ORDER BY app")]}

    @app.get("/api/scripts")
    def list_scripts():
        rows = db.q("SELECT id,name,description,language,target,app,risk,version,status,created_by,approved_by,"
                    "approved_at,updated_at,sha256 FROM scripts ORDER BY name")
        for r in rows:
            r["last_run"] = db.one("SELECT status, created_at FROM script_runs WHERE script_id=? ORDER BY id DESC LIMIT 1",
                                   (r["id"],))
        return rows

    @app.get("/api/scripts/{sid}")
    def one(sid: int):
        return get(sid)

    def check(s: ScriptIn):
        if s.language not in LANGUAGES or s.risk not in RISKS or s.target not in ("device", "app"):
            raise HTTPException(400, "pick a language, risk and target from the lists")
        if s.target == "app" and not s.app:
            raise HTTPException(400, "pick the application this script manages")

    @app.post("/api/scripts")
    def create(s: ScriptIn, request: Request):
        check(s)
        actor, role = who(request)
        sid = db.x("INSERT INTO scripts(name,description,language,target,app,risk,body,sha256,version,status,"
                   "created_by,updated_at) VALUES(?,?,?,?,?,?,?,?,1,'draft',?,?)",
                   (s.name, s.description, s.language, s.target, s.app if s.target == "app" else None, s.risk,
                    s.body, sha(s.body), actor, time.time()))
        ctx.audit(actor, role, "script.create", s.name, "draft", f"{s.language} v1")
        return get(sid)

    @app.put("/api/scripts/{sid}")
    def update(sid: int, s: ScriptIn, request: Request):
        check(s)
        old = get(sid)
        actor, role = who(request)
        db.x("UPDATE scripts SET name=?,description=?,language=?,target=?,app=?,risk=?,body=?,sha256=?,"
             "version=version+1,status='draft',created_by=?,approved_by=NULL,approved_at=NULL,updated_at=? WHERE id=?",
             (s.name, s.description, s.language, s.target, s.app if s.target == "app" else None, s.risk, s.body,
              sha(s.body), actor, time.time(), sid))
        ctx.audit(actor, role, "script.edit", s.name, "draft", f"v{old['version'] + 1}: needs approval again")
        return get(sid)

    @app.post("/api/scripts/{sid}/review/{decision}")
    async def decide(sid: int, decision: str, request: Request):
        if decision not in ("approve", "reject"):
            raise HTTPException(404)
        s = get(sid)
        actor, role = who(request)
        if s["status"] != "draft":
            raise HTTPException(400, f"version {s['version']} is already {s['status']}")
        if tokens_on and actor == s["created_by"]:
            raise HTTPException(403, "another engineer must approve a script you wrote")
        status = "approved" if decision == "approve" else "rejected"
        db.x("UPDATE scripts SET status=?, approved_by=?, approved_at=? WHERE id=?", (status, actor, time.time(), sid))
        ctx.audit(actor, role, f"script.{decision}", s["name"], status, f"v{s['version']} sha256 {s['sha256'][:12]}")
        await ctx.event(None, "approval", f"{actor} {status} script '{s['name']}' v{s['version']}")
        return get(sid)

    def targets(r: RunIn, s: dict) -> list[dict]:
        if r.device_ids:
            devs = db.q("SELECT * FROM devices WHERE id IN (%s)" % ",".join("?" * len(r.device_ids)), tuple(r.device_ids))
        else:
            conds, args = ["COALESCE(demo,0)=0"], []
            if r.kind:
                conds.append("kind=?"); args.append(r.kind)
            if r.location:
                conds.append("COALESCE(location,'Unassigned')=?"); args.append(r.location)
            app_ = r.app or (s["app"] if s["target"] == "app" else None)
            if app_:
                conds.append("id IN (SELECT device_id FROM apps_current WHERE app=?)"); args.append(app_)
            devs = db.q(f"SELECT * FROM devices WHERE {' AND '.join(conds)}", tuple(args))
        return devs

    async def queue(s: dict, dev: dict, dry: bool, actor: str, source: str) -> dict:
        why = compatible(dev, s["language"])
        now = time.time()
        if why:
            status, out = "skipped", why
        elif dry:
            status, out = "dry_run", f"Would run {LANGUAGES[s['language']]['label']} '{s['name']}' v{s['version']} on {dev['hostname']}"
        else:
            status, out = ("pending_approval" if s["risk"] == "high" else "queued"), ""
        rid = db.x("INSERT INTO script_runs(script_id,version,sha256,device_id,status,dry_run,requested_by,source,"
                   "output,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                   (s["id"], s["version"], s["sha256"], dev["id"], status, int(dry), actor, source, out, now, now))
        return {"run_id": rid, "device_id": dev["id"], "hostname": dev["hostname"], "status": status, "detail": out}

    ctx.queue_script = queue   # used by Flows "Run script" steps

    @app.post("/api/scripts/{sid}/run")
    async def run(sid: int, r: RunIn, request: Request):
        s = get(sid)
        if s["status"] != "approved":
            raise HTTPException(400, f"version {s['version']} is {s['status']}: approve it before running")
        devs = targets(r, s)
        if not devs:
            raise HTTPException(400, "no devices match")
        if len(devs) > MAX_DEVICES:
            raise HTTPException(400, f"{len(devs)} devices match; the limit per run is {MAX_DEVICES}")
        actor, role = who(request)
        res = [await queue(s, d, r.dry_run, actor, "console") for d in devs]
        ctx.audit(actor, role, "script.run" + (".dry" if r.dry_run else ""), s["name"], "ok",
                  f"v{s['version']} on {len(devs)} device(s): " + ", ".join(sorted({x['status'] for x in res})))
        await ctx.hub.send({"type": "script_run", "script_id": sid})
        return {"results": res}

    @app.get("/api/scripts/{sid}/runs")
    def runs(sid: int):
        return db.q("SELECT r.*, d.hostname FROM script_runs r LEFT JOIN devices d ON d.id=r.device_id "
                    "WHERE r.script_id=? ORDER BY r.id DESC LIMIT 60", (sid,))

    @app.get("/api/script-runs/pending")
    def pending():
        return db.q("SELECT r.*, d.hostname, s.name, s.language, s.risk FROM script_runs r JOIN devices d ON "
                    "d.id=r.device_id JOIN scripts s ON s.id=r.script_id WHERE r.status='pending_approval' ORDER BY r.id")

    @app.post("/api/script-runs/{rid}/{decision}")
    def decide_run(rid: int, decision: str, request: Request):
        if decision not in ("approve", "reject"):
            raise HTTPException(404)
        run_ = db.one("SELECT r.*, s.name FROM script_runs r JOIN scripts s ON s.id=r.script_id WHERE r.id=? "
                      "AND r.status='pending_approval'", (rid,))
        if not run_:
            raise HTTPException(404)
        actor, role = who(request)
        if tokens_on and actor == run_["requested_by"]:
            raise HTTPException(403, "another engineer must approve a high-risk run you requested")
        status = "queued" if decision == "approve" else "rejected"
        db.x("UPDATE script_runs SET status=?, approved_by=?, updated_at=? WHERE id=?", (status, actor, time.time(), rid))
        ctx.audit(actor, role, f"script.run.{decision}", run_["name"], status, f"run #{rid}")
        return {"status": status}

    # ---------- agent side ----------
    def pull(device_id: str) -> list[dict]:
        """Queued runs for a device, marked sent. Includes the approved body + its hash."""
        rows = db.q("SELECT r.id, s.language, s.body, r.sha256, r.version, s.name FROM script_runs r JOIN scripts s "
                    "ON s.id=r.script_id WHERE r.device_id=? AND r.status='queued' AND s.version=r.version",
                    (device_id,))
        for x in rows:
            db.x("UPDATE script_runs SET status='sent', updated_at=? WHERE id=?", (time.time(), x["id"]))
            x["timeout"] = TIMEOUT_S
        # a script edited after the run was queued: its approved version no longer exists, so never send it
        db.x("UPDATE script_runs SET status='failed', output='script changed after this run was queued', updated_at=? "
             "WHERE device_id=? AND status='queued' AND version <> (SELECT version FROM scripts s WHERE s.id=script_id)",
             (time.time(), device_id))
        return rows

    ctx.pull_scripts = pull

    class Result(BaseModel):
        status: str          # done | failed | refused
        exit_code: int | None = None
        output: str = ""

    @app.post("/api/agent/scripts/{rid}/result")
    async def result(rid: int, r: Result, request: Request):
        dev = ctx.device_by_key(request.headers.get("x-device-key"))
        run_ = db.one("SELECT r.*, s.name FROM script_runs r JOIN scripts s ON s.id=r.script_id WHERE r.id=? "
                      "AND r.device_id=?", (rid, dev["id"]))
        if not run_:
            raise HTTPException(404)
        status = r.status if r.status in ("done", "failed", "refused") else "failed"
        db.x("UPDATE script_runs SET status=?, exit_code=?, output=?, updated_at=? WHERE id=?",
             (status, r.exit_code, r.output[-8000:], time.time(), rid))
        await ctx.event(dev["id"], "executed" if status == "done" else "failed",
                        f"{dev['hostname']}: script '{run_['name']}' {status}"
                        + (f" (exit {r.exit_code})" if r.exit_code is not None else ""))
        return {"ok": True}
