"""Employee Impact Score (0-100): transparent, configurable, explainable.

Each factor is normalised to 0..1, multiplied by its weight, and the weights are rescaled to sum to 100.
The breakdown is returned with every score so the console can show exactly why an incident ranks where it does.
"""
import json

DEFAULTS = {
    "weights": {"reach": 30, "severity": 25, "critical_app": 15, "duration": 10, "recurrence": 10, "escalation": 10},
    "critical_apps": ["Teams", "Outlook", "SAP GUI", "Citrix Workspace"],
    "duration_cap_min": 60,      # an issue open this long scores the full duration factor
    "recurrence_cap": 5,         # this many recurrences in 24 h scores the full recurrence factor
}
SEVERITY = {"high": 1.0, "medium": 0.6, "low": 0.3}


def load_config(db) -> dict:
    row = db.one("SELECT value FROM settings WHERE key='impact'")
    cfg = json.loads(json.dumps(DEFAULTS))
    if row:
        saved = json.loads(row["value"])
        cfg["weights"].update({k: float(v) for k, v in saved.get("weights", {}).items() if k in cfg["weights"]})
        for k in ("critical_apps", "duration_cap_min", "recurrence_cap"):
            if k in saved:
                cfg[k] = saved[k]
    return cfg


def save_config(db, cfg: dict):
    db.x("INSERT OR REPLACE INTO settings(key,value) VALUES('impact',?)", (json.dumps(cfg),))


def score(inc: dict, total_employees: int, cfg: dict) -> tuple[int, list[dict]]:
    """inc needs: employees, severity, critical (bool), minutes_open, recurrences, spreading (bool)."""
    w = cfg["weights"]
    total_w = sum(w.values()) or 1
    reach = inc["employees"] / total_employees if total_employees else 0
    factors = [
        ("reach", min(1.0, reach), f"{inc['employees']} of {total_employees} employees affected"),
        ("severity", SEVERITY.get(inc["severity"], 0.3), f"highest severity: {inc['severity']}"),
        ("critical_app", 1.0 if inc["critical"] else 0.0,
         "business-critical app or virtual desktop" if inc["critical"] else "not a business-critical service"),
        ("duration", min(1.0, inc["minutes_open"] / cfg["duration_cap_min"]), f"open {inc['minutes_open']:.0f} min"),
        ("recurrence", min(1.0, inc["recurrences"] / cfg["recurrence_cap"]),
         f"{inc['recurrences']} times resolved and re-opened in 24 h"),
        ("escalation", 1.0 if inc["spreading"] else 0.0,
         "new devices affected in the last 10 min" if inc["spreading"] else "not spreading"),
    ]
    breakdown, total = [], 0.0
    for name, value, why in factors:
        pts = 100 * w[name] / total_w * value
        total += pts
        breakdown.append({"factor": name, "weight": round(100 * w[name] / total_w, 1),
                          "value": round(value, 2), "points": round(pts, 1), "why": why})
    return round(total), breakdown
