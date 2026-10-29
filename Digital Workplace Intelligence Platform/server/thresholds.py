"""Alert thresholds people set per parameter: global, per device type, and per application.

Stored in settings('thresholds') as overrides on top of brain.DEVICE_THRESHOLDS / APP_THRESHOLDS:
  {"device": {"cpu_pct": {"warn": 85, "crit": 95, "sustain_min": 5}},
   "kinds":  {"vdi": {"session_latency_ms": {"warn": 150}}},
   "apps":   {"*": {"mem_mb": {"warn": 2000}}, "Teams": {"latency_ms": {"warn": 1000}}}}
"""
import json
import time

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from . import brain
from .core import Ctx

KINDS = ("laptop", "desktop", "mobile", "vdi")
FIELDS = ("warn", "crit", "sustain_min")
SAMPLED = {"cpu_pct": "cpu", "mem_pct": "mem", "disk_pct": "disk", "battery_pct": "battery"}  # stored per sample


def load(db) -> dict:
    row = db.one("SELECT value FROM settings WHERE key='thresholds'")
    cfg = json.loads(row["value"]) if row else {}
    return {"device": cfg.get("device", {}), "kinds": cfg.get("kinds", {}), "apps": cfg.get("apps", {})}


def _merge(base: dict, *layers: dict) -> dict:
    out = {k: dict(v) for k, v in base.items()}
    for layer in layers:
        for k, v in (layer or {}).items():
            if k in out:
                out[k].update({f: v[f] for f in FIELDS if f in v})
    return out


def device_th(cfg: dict, kind: str | None) -> dict:
    return _merge(brain.DEVICE_THRESHOLDS, cfg["device"], cfg["kinds"].get(kind or "", {}))


def app_th(cfg: dict):
    cache = {}

    def get(name: str) -> dict:
        if name not in cache:
            cache[name] = _merge(brain.APP_THRESHOLDS, cfg["apps"].get("*", {}), cfg["apps"].get(name, {}))
        return cache[name]
    return get


def sustained(db, device_id: str, finding: dict, th: dict, now: float) -> bool:
    """True unless the finding's parameter needs a sustained breach that stored samples don't show yet."""
    p = finding.get("param")
    t = th.get(p or "")
    mins = (t or {}).get("sustain_min") or 0
    if not mins or p not in SAMPLED:
        return True
    rows = db.q(f"SELECT {SAMPLED[p]} v FROM telemetry WHERE device_id=? AND ts>=? AND {SAMPLED[p]} IS NOT NULL",
                (device_id, now - mins * 60))
    if len(rows) < 2:
        return False
    span = db.one("SELECT MIN(ts) a FROM telemetry WHERE device_id=?", (device_id,))["a"]
    if span is None or now - span < mins * 60 * 0.9:   # not enough history to prove it yet
        return False
    return all(brain.level({p: t}, p, r["v"]) for r in rows)


def validate(params: dict, catalog: dict) -> dict:
    out = {}
    for k, v in params.items():
        if k not in catalog:
            raise HTTPException(400, f"unknown parameter {k!r}")
        clean = {}
        for f in FIELDS:
            if f in v and v[f] is not None and v[f] != "":
                x = float(v[f])
                if x < 0 or (f != "sustain_min" and x > catalog[k]["max"] * 10):
                    raise HTTPException(400, f"{k}.{f} out of range")
                clean[f] = x
            elif f in v:
                clean[f] = None if f == "crit" else clean.get(f)
        below = catalog[k].get("dir") == "below"
        w, c = clean.get("warn", catalog[k]["warn"]), clean.get("crit")
        if c is not None and w is not None and ((c > w) if below else (c < w)):
            raise HTTPException(400, f"{k}: critical must be {'below' if below else 'above'} warning")
        out[k] = clean
    return out


class ThresholdIn(BaseModel):
    scope: str = "device"          # device | kind:<kind> | app:<name or *>
    params: dict = {}
    reset: bool = False            # clear this scope's overrides


def fleet_meter(db, cfg: dict, scope: str) -> dict:
    """Current values per parameter in a scope, so the console can show where the fleet sits on each meter."""
    if scope.startswith("app:"):
        app = scope[4:]
        rows = db.q("SELECT * FROM apps_current" + ("" if app == "*" else " WHERE app=?"), (() if app == "*" else (app,)))
        th = app_th(cfg)(app if app != "*" else "")
        cols = {"crashes_24h": "crashes", "hangs_24h": "hangs", "latency_ms": "latency_ms", "mem_mb": "mem_mb",
                "cpu_pct": "cpu"}
        vals = {k: [r[c] for r in rows if r[c] is not None] for k, c in cols.items()}
        catalog = brain.APP_THRESHOLDS
    else:
        kind = scope[5:] if scope.startswith("kind:") else None
        devs = db.q("SELECT metrics FROM devices" + (" WHERE kind=?" if kind else ""), ((kind,) if kind else ()))
        ms = [json.loads(d["metrics"] or "{}") for d in devs]
        th = device_th(cfg, kind)
        vals = {k: [m[k] for m in ms if isinstance(m.get(k), (int, float))] for k in brain.DEVICE_THRESHOLDS}
        catalog = brain.DEVICE_THRESHOLDS
    out = []
    for k, meta in catalog.items():
        v, t = vals.get(k, []), th[k]
        lv = [brain.level({k: t}, k, x) for x in v]
        out.append({"param": k, **{f: meta.get(f) for f in ("label", "unit", "max", "dir")},
                    "default": {f: meta.get(f) for f in ("warn", "crit")},
                    "warn": t.get("warn"), "crit": t.get("crit"), "sustain_min": t.get("sustain_min") or 0,
                    "sustain_supported": k in SAMPLED and not scope.startswith("app:"),
                    "samples": len(v), "current_max": max(v) if v else None, "current_min": min(v) if v else None,
                    "current_avg": round(sum(v) / len(v), 1) if v else None,
                    "breaching_warn": lv.count("warn"), "breaching_crit": lv.count("crit")})
    return {"scope": scope, "params": out}


def register(app: FastAPI, ctx: Ctx):
    db = ctx.db

    @app.get("/api/thresholds")
    def get_thresholds(scope: str = "device"):
        if not (scope == "device" or scope.startswith("app:") or scope[5:] in KINDS):
            raise HTTPException(400, "scope must be device, kind:<type> or app:<name|*>")
        cfg = load(db)
        return {**fleet_meter(db, cfg, scope), "apps": [r["app"] for r in db.q(
            "SELECT DISTINCT app FROM apps_current ORDER BY app")], "overrides": cfg}

    @app.post("/api/thresholds")
    def set_thresholds(t: ThresholdIn, request: Request):
        cfg = load(db)
        if t.scope == "device":
            bucket, catalog = cfg["device"], brain.DEVICE_THRESHOLDS
        elif t.scope.startswith("kind:") and t.scope[5:] in KINDS:
            bucket, catalog = cfg["kinds"].setdefault(t.scope[5:], {}), brain.DEVICE_THRESHOLDS
        elif t.scope.startswith("app:") and t.scope[4:]:
            bucket, catalog = cfg["apps"].setdefault(t.scope[4:][:80], {}), brain.APP_THRESHOLDS
        else:
            raise HTTPException(400, "bad scope")
        if t.reset:
            bucket.clear()
        else:
            for k, v in validate(t.params, catalog).items():
                bucket.setdefault(k, {}).update(v)
        db.x("INSERT OR REPLACE INTO settings(key,value) VALUES('thresholds',?)", (json.dumps(cfg),))
        ctx.audit(getattr(request.state, "actor", "local-dev"), getattr(request.state, "role", "admin"),
                  "thresholds.update", t.scope, "ok", "reset" if t.reset else json.dumps(t.params)[:400])
        return {"ok": True, "applies": "from each device's next report", "ts": time.time()}
