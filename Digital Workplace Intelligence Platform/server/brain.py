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


def evaluate(device: dict, m: dict, apps: list[dict] | None = None) -> list[dict]:
    """Return a list of findings for one telemetry sample."""
    out = []
    kind = device.get("kind")
    platform = (device.get("platform") or "").lower()
    managed = kind in ("laptop", "desktop", "vdi")   # can run scripted fixes

    def add(type_, severity, title, detail, action=None, target=None):
        risk = ACTIONS[action][0] if action else "advise"
        out.append({"type": type_, "severity": severity, "title": title, "detail": detail,
                    "action": action, "risk": risk, "target": target})

    # ---------- device ----------
    disk = _f(m, "disk_pct")
    if disk is not None and disk >= 90:
        add("disk_full", "high" if disk >= 95 else "medium",
            "Storage almost full", f"Storage at {disk:.0f}% used", "clean_temp" if managed else None)

    cpu = _f(m, "cpu_pct")
    if cpu is not None and cpu >= 90 and managed:
        add("high_cpu", "medium", "CPU saturated", f"CPU at {cpu:.0f}%", "top_processes")

    mem = _f(m, "mem_pct")
    if mem is not None and mem >= 92:
        add("high_memory", "medium", "Memory pressure", f"Memory at {mem:.0f}%")

    crashes = _f(m, "crashes_24h")
    if crashes is not None and crashes >= 3:
        add("crash_loop", "high", "Apps keep crashing", f"{crashes:.0f} app crashes in 24h")

    uptime = _f(m, "uptime_hours")
    if uptime is not None and uptime >= 168 and kind in ("laptop", "desktop"):
        add("pending_reboot", "low", "Not restarted in a week",
            f"Up for {uptime / 24:.0f} days", "schedule_reboot")

    batt = _f(m, "battery_pct")
    if batt is not None and batt <= 15 and not m.get("battery_plugged"):
        add("low_battery", "low", "Battery low", f"Battery at {batt:.0f}% and unplugged")

    health = _f(m, "battery_health_pct")
    if health is not None and health < 70:
        add("battery_worn", "medium", "Battery worn out",
            f"Battery health {health:.0f}% — consider replacement")

    latency = _f(m, "network_latency_ms")
    if latency is not None and latency >= 300:
        add("slow_network", "medium", "Slow network", f"Latency {latency:.0f} ms")

    boot = _f(m, "boot_seconds")
    if boot is not None and boot >= 120:
        add("slow_boot", "medium", "Slow startup", f"Boot took {boot:.0f}s")

    # ---------- OS ----------
    if platform in MIN_OS:
        major = _major(device.get("os_version"))
        if major is not None and major < MIN_OS[platform]:
            add("os_outdated", "high", "OS out of date",
                f"{platform} {device.get('os_version')} is below {MIN_OS[platform]}")

    patch = _f(m, "patch_age_days")
    if patch is not None and patch >= PATCH_MAX_DAYS:
        add("os_patch_overdue", "high" if patch >= 60 else "medium", "Security patches overdue",
            f"Last OS update {patch:.0f} days ago", "install_updates" if managed else None)

    os_err = _f(m, "os_errors_24h")
    if os_err is not None and os_err >= 20:
        add("os_errors", "medium", "OS reporting errors", f"{os_err:.0f} system errors in 24h")

    # ---------- VDI ----------
    if kind == "vdi":
        rtt = _f(m, "session_latency_ms")
        if rtt is not None and rtt >= 200:
            add("vdi_latency", "high", "Virtual desktop lagging", f"Session round-trip {rtt:.0f} ms")
        logon = _f(m, "logon_seconds")
        if logon is not None and logon >= 60:
            add("vdi_slow_logon", "medium", "Slow virtual desktop logon", f"Logon took {logon:.0f}s")

    # ---------- applications ----------
    for a in apps or []:
        name = a.get("name")
        if not name:
            continue
        if (a.get("crashes_24h") or 0) >= 3:
            add(f"app_crash:{name}", "high", f"{name} keeps crashing",
                f"{a['crashes_24h']} crashes in 24h (v{a.get('version') or '?'})",
                "repair_app" if managed else None, name)
        if (a.get("latency_ms") or 0) >= 1500:
            add(f"app_slow:{name}", "medium", f"{name} is slow",
                f"Response time {a['latency_ms']:.0f} ms", None, name)
        if (a.get("mem_mb") or 0) >= 2500:
            add(f"app_memory:{name}", "medium", f"{name} using too much memory",
                f"{a['mem_mb']:.0f} MB in use", "restart_app" if managed else None, name)
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
