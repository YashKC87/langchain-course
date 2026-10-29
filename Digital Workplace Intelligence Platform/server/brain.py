"""Layer of Intelligence: turns raw metrics into findings, decisions and a DEX score.

Each finding carries a suggested action and a risk tier:
  low    -> executed automatically
  medium -> needs IT approval
  high   -> needs IT approval
  advise -> no action, user/IT is only notified
App findings carry the app name in `target` and in the issue type (e.g. app_crash:Teams).
"""

MIN_OS = {"ios": 17, "android": 13}
PATCH_MAX_DAYS = 30

# Alert thresholds people can change (Proactive Monitoring -> Thresholds). warn opens an issue at the rule's
# normal severity; crit (optional) raises it to high. "below" parameters alert when the value drops under.
# sustain_min > 0 means the value must stay past the threshold that long (checked against stored samples).
DEVICE_THRESHOLDS = {
    "cpu_pct": {"label": "CPU", "unit": "%", "warn": 90, "crit": None, "max": 100},
    "mem_pct": {"label": "Memory", "unit": "%", "warn": 92, "crit": None, "max": 100},
    "disk_pct": {"label": "Disk used", "unit": "%", "warn": 90, "crit": 95, "max": 100},
    "battery_pct": {"label": "Battery charge", "unit": "%", "warn": 15, "crit": None, "max": 100, "dir": "below"},
    "battery_health_pct": {"label": "Battery health", "unit": "%", "warn": 70, "crit": None, "max": 100, "dir": "below"},
    "network_latency_ms": {"label": "Network latency", "unit": "ms", "warn": 300, "crit": None, "max": 2000},
    "boot_seconds": {"label": "Boot time", "unit": "s", "warn": 120, "crit": None, "max": 600},
    "uptime_hours": {"label": "Uptime without restart", "unit": "h", "warn": 168, "crit": None, "max": 1000},
    "crashes_24h": {"label": "App crashes (device, 24 h)", "unit": "", "warn": 3, "crit": None, "max": 50},
    "os_errors_24h": {"label": "OS errors (24 h)", "unit": "", "warn": 20, "crit": None, "max": 200},
    "patch_age_days": {"label": "Patch age", "unit": "days", "warn": PATCH_MAX_DAYS, "crit": 60, "max": 180},
    "session_latency_ms": {"label": "VDI session latency", "unit": "ms", "warn": 200, "crit": None, "max": 1000},
    "logon_seconds": {"label": "VDI logon time", "unit": "s", "warn": 60, "crit": None, "max": 300},
}
APP_THRESHOLDS = {
    "crashes_24h": {"label": "Crashes (24 h)", "unit": "", "warn": 3, "crit": None, "max": 50},
    "hangs_24h": {"label": "Hangs (24 h)", "unit": "", "warn": 5, "crit": None, "max": 50},
    "latency_ms": {"label": "Response time", "unit": "ms", "warn": 1500, "crit": None, "max": 10000},
    "mem_mb": {"label": "Memory", "unit": "MB", "warn": 2500, "crit": None, "max": 8000},
    "cpu_pct": {"label": "CPU", "unit": "%", "warn": 80, "crit": None, "max": 100},
}


def level(th: dict, key: str, v: float | None) -> str | None:
    """'warn', 'crit' or None for value v against threshold th[key]."""
    t = th.get(key)
    if v is None or not t or t.get("warn") is None:
        return None
    below = t.get("dir") == "below"
    past = (lambda x: v <= x) if below else (lambda x: v >= x)
    if t.get("crit") is not None and past(t["crit"]):
        return "crit"
    return "warn" if past(t["warn"]) else None

# action -> (risk, friendly message sent to the user once it succeeds)
ACTIONS = {
    "clean_temp": ("low", "We cleared temporary files and freed up space for you. 🧹"),
    "top_processes": ("low", "We spotted an app hogging your CPU and flagged it to IT. 🔍"),
    "repair_app": ("medium", "We repaired {target}. It should behave now. 🛠️"),
    "restart_app": ("medium", "We gave {target} a fresh restart to free up memory. 🔄"),
    "install_updates": ("medium", "Your device is now up to date with the latest security patches. 🔒"),
    "schedule_reboot": ("high", "A restart is scheduled tonight to keep things fast. 🌙"),
}


def action_message(action: str, target: str | None) -> str:
    msg = ACTIONS.get(action, ("", "We fixed something for you. ✨"))[1]
    return msg.format(target=target or "an app")


def _f(m: dict, k: str):
    v = m.get(k)
    return None if v is None else float(v)


def _major(version: str | None) -> int | None:
    try:
        return int(str(version).split(".")[0])
    except (TypeError, ValueError):
        return None


def evaluate(device: dict, m: dict, apps: list[dict] | None = None, th: dict | None = None,
             app_th=None) -> list[dict]:
    """Return a list of findings for one telemetry sample.
    th = device thresholds (defaults DEVICE_THRESHOLDS); app_th(name) -> that app's thresholds."""
    out = []
    th = th or DEVICE_THRESHOLDS
    app_th = app_th or (lambda name: APP_THRESHOLDS)
    kind = device.get("kind")
    platform = (device.get("platform") or "").lower()
    managed = kind in ("laptop", "desktop", "vdi")   # can run scripted fixes

    def add(type_, severity, title, detail, action=None, target=None, param=None):
        risk = ACTIONS[action][0] if action else "advise"
        out.append({"type": type_, "severity": severity, "title": title, "detail": detail,
                    "action": action, "risk": risk, "target": target, "param": param})

    def hit(key, warn_sev):
        """Severity if metric `key` is past its threshold, else None."""
        lv = level(th, key, _f(m, key))
        return None if lv is None else ("high" if lv == "crit" else warn_sev)

    # ---------- device ----------
    if sev := hit("disk_pct", "medium"):
        add("disk_full", sev, "Storage almost full", f"Storage at {_f(m, 'disk_pct'):.0f}% used",
            "clean_temp" if managed else None, param="disk_pct")

    if (sev := hit("cpu_pct", "medium")) and managed:
        add("high_cpu", sev, "CPU saturated", f"CPU at {_f(m, 'cpu_pct'):.0f}%", "top_processes", param="cpu_pct")

    if sev := hit("mem_pct", "medium"):
        add("high_memory", sev, "Memory pressure", f"Memory at {_f(m, 'mem_pct'):.0f}%", param="mem_pct")

    if sev := hit("crashes_24h", "high"):
        add("crash_loop", sev, "Apps keep crashing", f"{_f(m, 'crashes_24h'):.0f} app crashes in 24h",
            param="crashes_24h")

    if (sev := hit("uptime_hours", "low")) and kind in ("laptop", "desktop"):
        add("pending_reboot", sev, "Not restarted in a while",
            f"Up for {_f(m, 'uptime_hours') / 24:.0f} days", "schedule_reboot", param="uptime_hours")

    if (sev := hit("battery_pct", "low")) and not m.get("battery_plugged"):
        add("low_battery", sev, "Battery low", f"Battery at {_f(m, 'battery_pct'):.0f}% and unplugged",
            param="battery_pct")

    if sev := hit("battery_health_pct", "medium"):
        add("battery_worn", sev, "Battery worn out",
            f"Battery health {_f(m, 'battery_health_pct'):.0f}% — consider replacement", param="battery_health_pct")

    if sev := hit("network_latency_ms", "medium"):
        add("slow_network", sev, "Slow network", f"Latency {_f(m, 'network_latency_ms'):.0f} ms",
            param="network_latency_ms")

    if sev := hit("boot_seconds", "medium"):
        add("slow_boot", sev, "Slow startup", f"Boot took {_f(m, 'boot_seconds'):.0f}s", param="boot_seconds")

    # ---------- OS ----------
    if platform in MIN_OS:
        major = _major(device.get("os_version"))
        if major is not None and major < MIN_OS[platform]:
            add("os_outdated", "high", "OS out of date",
                f"{platform} {device.get('os_version')} is below {MIN_OS[platform]}")

    if sev := hit("patch_age_days", "medium"):
        add("os_patch_overdue", sev, "Security patches overdue",
            f"Last OS update {_f(m, 'patch_age_days'):.0f} days ago", "install_updates" if managed else None,
            param="patch_age_days")

    if sev := hit("os_errors_24h", "medium"):
        add("os_errors", sev, "OS reporting errors", f"{_f(m, 'os_errors_24h'):.0f} system errors in 24h",
            param="os_errors_24h")

    # ---------- VDI ----------
    if kind == "vdi":
        if sev := hit("session_latency_ms", "high"):
            add("vdi_latency", sev, "Virtual desktop lagging",
                f"Session round-trip {_f(m, 'session_latency_ms'):.0f} ms", param="session_latency_ms")
        if sev := hit("logon_seconds", "medium"):
            add("vdi_slow_logon", sev, "Slow virtual desktop logon",
                f"Logon took {_f(m, 'logon_seconds'):.0f}s", param="logon_seconds")

    # ---------- applications ----------
    for a in apps or []:
        name = a.get("name")
        if not name:
            continue
        at = app_th(name)
        sev = lambda k, warn_sev: (None if (lv := level(at, k, _f(a, k))) is None
                                   else "high" if lv == "crit" else warn_sev)
        if s_ := sev("crashes_24h", "high"):
            add(f"app_crash:{name}", s_, f"{name} keeps crashing",
                f"{a['crashes_24h']} crashes in 24h (v{a.get('version') or '?'})",
                "repair_app" if managed else None, name, "app.crashes_24h")
        if s_ := sev("hangs_24h", "medium"):
            add(f"app_hang:{name}", s_, f"{name} keeps hanging", f"{a['hangs_24h']} hangs in 24h", None, name,
                "app.hangs_24h")
        if s_ := sev("latency_ms", "medium"):
            add(f"app_slow:{name}", s_, f"{name} is slow",
                f"Response time {a['latency_ms']:.0f} ms", None, name, "app.latency_ms")
        if s_ := sev("mem_mb", "medium"):
            add(f"app_memory:{name}", s_, f"{name} using too much memory",
                f"{a['mem_mb']:.0f} MB in use", "restart_app" if managed else None, name, "app.mem_mb")
        if s_ := sev("cpu_pct", "medium"):
            add(f"app_cpu:{name}", s_, f"{name} using a lot of CPU", f"{a['cpu_pct']:.0f}% CPU", None, name,
                "app.cpu_pct")
    return out


def clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


def app_score(a: dict) -> float:
    return round(clamp(100 - (a.get("crashes") or 0) * 6 - (a.get("hangs") or 0) * 3
                       - max(0, (a.get("latency_ms") or 0) - 500) / 25
                       - max(0, (a.get("cpu") or 0) - 50) / 2), 1)


def score(m: dict, sentiment: float | None = None, apps: list[dict] | None = None) -> dict:
    """DEX score (0-100) from four weighted components."""
    g = lambda k, d=0.0: _f(m, k) if _f(m, k) is not None else d  # noqa: E731
    apps = apps or []
    app_crashes = sum(a.get("crashes_24h") or 0 for a in apps)
    app_hangs = sum(a.get("hangs_24h") or 0 for a in apps)
    lat = [a["latency_ms"] for a in apps if a.get("latency_ms")]
    app_latency = sum(lat) / len(lat) if lat else 0

    performance = clamp(100 - max(0, g("cpu_pct") - 70) * 1.5
                        - max(0, g("mem_pct") - 75) * 1.5
                        - max(0, g("disk_pct") - 85) * 3
                        - max(0, 70 - g("battery_health_pct", 100)))
    stability = clamp(100 - g("crashes_24h") * 8 - app_crashes * 4 - app_hangs * 2
                      - max(0, g("uptime_hours") - 168) / 10
                      - g("os_errors_24h") / 4
                      - max(0, g("patch_age_days") - PATCH_MAX_DAYS) / 3)
    responsiveness = clamp(100 - max(0, g("boot_seconds") - 60) / 2
                           - max(0, g("network_latency_ms") - 100) / 5
                           - max(0, g("session_latency_ms") - 80) / 4
                           - max(0, g("logon_seconds") - 30)
                           - max(0, app_latency - 500) / 40)
    sent = clamp(sentiment if sentiment is not None else 80.0)
    dex = 0.35 * performance + 0.30 * stability + 0.20 * responsiveness + 0.15 * sent
    return {"dex": round(dex, 1), "performance": round(performance, 1),
            "stability": round(stability, 1), "responsiveness": round(responsiveness, 1),
            "sentiment": round(sent, 1)}
