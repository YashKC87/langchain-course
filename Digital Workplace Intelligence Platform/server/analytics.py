"""Analytics: anomaly detection, fleet correlation, predictions and application performance."""
import json
import statistics
import time

from . import brain

FLEET_THRESHOLD = 3          # distinct devices with the same issue -> fleet alert
CORRELATION_WINDOW = 1800    # seconds


def anomaly(db, device_id: str, dex: float) -> dict | None:
    """Detect a sharp DEX drop relative to the device's own baseline."""
    rows = db.q("SELECT dex FROM telemetry WHERE device_id=? ORDER BY ts DESC LIMIT 41", (device_id,))
    hist = [r["dex"] for r in rows[1:] if r["dex"] is not None]
    if len(hist) < 12:
        return None
    mean, sd = statistics.mean(hist), statistics.pstdev(hist) or 1.0
    z = (dex - mean) / sd
    if z <= -3 and mean - dex >= 12:
        return {"baseline": round(mean, 1), "current": dex, "z": round(z, 1)}
    return None


def fleet_candidates(db, issue_type: str) -> dict | None:
    """When the same issue opens on several devices, describe the pattern."""
    rows = db.q("SELECT i.device_id, i.detail, d.hostname FROM issues i JOIN devices d ON d.id=i.device_id "
                "WHERE i.type=? AND i.status='open' AND i.opened_at>?",
                (issue_type, time.time() - CORRELATION_WINDOW))
    devices = {r["device_id"]: r["hostname"] for r in rows}
    if len(devices) < FLEET_THRESHOLD:
        return None
    ctx = {"devices_affected": len(devices), "hostnames": list(devices.values())[:10],
           "samples": [r["detail"] for r in rows[:6]]}
    if ":" in issue_type:
        app = issue_type.split(":", 1)[1]
        vers = {}
        for v in db.q("SELECT version FROM apps_current WHERE app=? AND device_id IN (%s)"
                      % ",".join("?" * len(devices)), (app, *devices)):
            vers[v["version"]] = vers.get(v["version"], 0) + 1
        ctx["app"], ctx["versions"] = app, vers
    return ctx


def _fit(points: list[tuple[float, float]]) -> tuple[float, float]:
    """Least-squares (slope per second, r²). r² tells a real trend from noise."""
    n = len(points)
    if n < 2:
        return 0.0, 0.0
    mx = sum(p[0] for p in points) / n
    my = sum(p[1] for p in points) / n
    sxx = sum((p[0] - mx) ** 2 for p in points)
    syy = sum((p[1] - my) ** 2 for p in points)
    if sxx == 0 or syy == 0:
        return 0.0, 0.0
    sxy = sum((p[0] - mx) * (p[1] - my) for p in points)
    return sxy / sxx, (sxy * sxy) / (sxx * syy)


MIN_R2 = 0.6
PATCH_LIMIT_DAYS = brain.PATCH_MAX_DAYS
PATCH_WARN_DAYS = 16         # forecast the breach up to two weeks ahead
MIN_STEADY = 0.7   # share of consecutive samples moving in the trend's direction


def _steady(points: list[tuple[float, float]], rising: bool) -> bool:
    """A real trend moves the same way most of the time; a one-off jump does not."""
    deltas = [b[1] - a[1] for a, b in zip(points, points[1:]) if b[1] != a[1]]
    if len(deltas) < 5:
        return False
    same = sum(1 for d in deltas if (d > 0) == rising)
    total = abs(points[-1][1] - points[0][1])
    biggest = max(abs(d) for d in deltas)
    return same / len(deltas) >= MIN_STEADY and total > 0 and biggest < 0.5 * total


def eta(seconds: float) -> str:
    if seconds < 3600:
        return f"in ~{max(1, int(seconds / 60))} min"
    if seconds < 86400 * 2:
        return f"in ~{seconds / 3600:.0f} h"
    return f"in ~{seconds / 86400:.0f} days"


def predictions(db) -> list[dict]:
    out = []
    devices = db.q("SELECT id,hostname,kind,dex,metrics FROM devices")
    for d in devices:
        hist = db.q("SELECT ts,dex,disk FROM telemetry WHERE device_id=? ORDER BY ts DESC LIMIT 40", (d["id"],))
        if len(hist) < 8:
            continue
        hist.reverse()
        disk_pts = [(h["ts"], h["disk"]) for h in hist if h["disk"] is not None]
        if disk_pts:
            (s, r2), cur = _fit(disk_pts), disk_pts[-1][1]
            if s > 0 and r2 >= MIN_R2 and cur < 90 and _steady(disk_pts, rising=True):
                secs = (95 - cur) / s
                if secs < 30 * 86400:
                    out.append({"device_id": d["id"], "hostname": d["hostname"], "kind": d["kind"],
                                "type": "disk_forecast", "title": "Storage will be full",
                                "detail": f"{cur:.0f}% used and rising", "eta": eta(secs),
                                "seconds": secs, "confidence": round(100 * r2), "model": "linear trend (R²)"})
        dex_pts = [(h["ts"], h["dex"]) for h in hist if h["dex"] is not None]
        (s, r2), cur = _fit(dex_pts), dex_pts[-1][1]
        if s < 0 and r2 >= MIN_R2 and cur > 60 and _steady(dex_pts, rising=False):
            secs = (cur - 60) / -s
            if secs < 7 * 86400:
                out.append({"device_id": d["id"], "hostname": d["hostname"], "kind": d["kind"],
                            "type": "dex_decline", "title": "Experience degrading",
                            "detail": f"DEX {cur:.0f} trending down", "eta": eta(secs),
                            "seconds": secs, "confidence": round(100 * r2), "model": "linear trend (R²)"})
        m = json.loads(d["metrics"] or "{}")
        health = m.get("battery_health_pct")
        if health is not None and health < 80:
            months = max(0.5, (health - 60) / 1.5)  # ~1.5% wear per month
            out.append({"device_id": d["id"], "hostname": d["hostname"], "kind": d["kind"],
                        "type": "battery_forecast", "title": "Battery replacement needed",
                        "detail": f"Health {health:.0f}%", "eta": f"in ~{months:.0f} months",
                        "seconds": months * 30 * 86400, "confidence": 70,
                        "model": "wear-rate estimate (~1.5%/month)"})
        age = m.get("patch_age_days")
        if age is not None and PATCH_WARN_DAYS <= age < PATCH_LIMIT_DAYS:
            days = PATCH_LIMIT_DAYS - age   # deterministic: patch age grows one day per day
            out.append({"device_id": d["id"], "hostname": d["hostname"], "kind": d["kind"],
                        "type": "patch_forecast", "title": "Will breach the 30-day patch policy",
                        "detail": f"last patched {age:.0f} days ago", "eta": eta(days * 86400),
                        "seconds": days * 86400, "confidence": 95, "model": "deterministic threshold"})
    out.extend(app_crash_trends(db))
    return sorted(out, key=lambda p: p["seconds"])


def app_crash_trends(db, now: float | None = None) -> list[dict]:
    """Apps whose fleet-wide crash count (24h gauge per device) is clearly higher than 5-15 min ago."""
    now = now or time.time()
    window = ("SELECT app, SUM(c) total, COUNT(*) devices FROM (SELECT app, device_id, MAX(crashes) c "
              "FROM app_samples WHERE ts BETWEEN ? AND ? GROUP BY app, device_id) GROUP BY app")
    recent = {r["app"]: r for r in db.q(window, (now - 120, now))}
    older = {r["app"]: r for r in db.q(window, (now - 900, now - 300))}
    out = []
    for app, r in recent.items():
        before = older.get(app)
        if not before:      # no baseline yet: can't call it a trend
            continue
        now_total, then_total = r["total"] or 0, before["total"] or 0
        if now_total >= 6 and now_total >= 2 * then_total + 3:
            out.append({"device_id": None, "hostname": "Fleet", "kind": "app", "type": "app_crash_trend",
                        "title": f"{app} crash rate rising",
                        "detail": f"{now_total} crashes in 24h across {r['devices']} devices (was {then_total})",
                        "eta": "now", "seconds": 0, "confidence": 80, "model": "baseline comparison"})
    return out


def app_stats(db) -> list[dict]:
    rows = db.q("SELECT app, COUNT(*) devices, GROUP_CONCAT(DISTINCT version) versions, AVG(cpu) cpu, "
                "AVG(mem_mb) mem_mb, SUM(crashes) crashes, SUM(hangs) hangs, AVG(latency_ms) latency_ms "
                "FROM apps_current WHERE ts>? GROUP BY app", (time.time() - 3600,))
    out = []
    for r in rows:
        per_dev = {"crashes": (r["crashes"] or 0) / r["devices"], "hangs": (r["hangs"] or 0) / r["devices"],
                   "latency_ms": r["latency_ms"], "cpu": r["cpu"]}
        out.append({"app": r["app"], "devices": r["devices"],
                    "versions": sorted((r["versions"] or "").split(",")),
                    "avg_cpu": round(r["cpu"] or 0, 1), "avg_mem_mb": round(r["mem_mb"] or 0),
                    "crashes": r["crashes"] or 0, "hangs": r["hangs"] or 0,
                    "avg_latency_ms": round(r["latency_ms"] or 0), "score": brain.app_score(per_dev)})
    return sorted(out, key=lambda a: a["score"])


def app_detail(db, app: str) -> dict:
    devices = db.q("SELECT a.*, d.hostname, d.kind, d.platform FROM apps_current a JOIN devices d "
                   "ON d.id=a.device_id WHERE a.app=? ORDER BY a.crashes DESC, a.latency_ms DESC", (app,))
    versions = {}
    for d in devices:
        v = versions.setdefault(d["version"] or "?", {"version": d["version"] or "?", "devices": 0,
                                                       "crashes": 0, "latency": []})
        v["devices"] += 1
        v["crashes"] += d["crashes"] or 0
        if d["latency_ms"]:
            v["latency"].append(d["latency_ms"])
    for v in versions.values():
        lat = v.pop("latency")
        v["avg_latency_ms"] = round(sum(lat) / len(lat)) if lat else 0
    trend = db.q("SELECT CAST(ts/60 AS INTEGER)*60 t, AVG(latency_ms) latency, SUM(crashes) crashes, "
                 "AVG(cpu) cpu FROM app_samples WHERE app=? AND ts>? GROUP BY t ORDER BY t",
                 (app, time.time() - 3600))
    return {"app": app, "devices": devices, "versions": sorted(versions.values(), key=lambda v: -v["devices"]),
            "trend": trend}


def engagement(db) -> dict:
    dept = db.q("SELECT COALESCE(d.department,'Unassigned') department, AVG(s.rating) rating, COUNT(*) n "
                "FROM surveys s JOIN devices d ON d.id=s.device_id GROUP BY 1 ORDER BY rating")
    kinds = db.q("SELECT d.kind, AVG(s.rating) rating, COUNT(*) n FROM surveys s JOIN devices d "
                 "ON d.id=s.device_id GROUP BY 1")
    asked = db.one("SELECT COUNT(*) n FROM notifications WHERE kind IN ('survey','pulse')")["n"]
    answered = db.one("SELECT COUNT(*) n FROM surveys")["n"]
    ratings = [r["rating"] for r in db.q("SELECT rating FROM surveys")]
    promoters = sum(1 for r in ratings if r == 5)
    detractors = sum(1 for r in ratings if r <= 3)
    g = db.one("SELECT SUM(status='completed') done, COUNT(*) n FROM guide_deliveries")
    comments = db.q("SELECT s.rating, s.comment, s.ts, d.hostname FROM surveys s JOIN devices d "
                    "ON d.id=s.device_id WHERE s.comment<>'' ORDER BY s.ts DESC LIMIT 8")
    return {
        "departments": [{**r, "rating": round(r["rating"], 2)} for r in dept],
        "kinds": [{**r, "rating": round(r["rating"], 2)} for r in kinds],
        "response_rate": round(100 * answered / asked) if asked else None,
        "score": round(100 * (promoters - detractors) / len(ratings)) if ratings else None,
        "responses": answered,
        "guide_completion": round(100 * (g["done"] or 0) / g["n"]) if g["n"] else None,
        "comments": comments,
    }
