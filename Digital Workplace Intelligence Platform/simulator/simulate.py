"""Simulated end-user fleet (laptops, desktops, mobiles, Citrix/AVD sessions) for local testing.

Simulates device, OS, application and VDI telemetry, app crash waves across the fleet,
slowly filling disks (for predictions), employees chatting with IT, completing guides
and answering pulse surveys.

    python simulator/simulate.py --server http://127.0.0.1:8000 --interval 3
"""
import argparse
import random
import sys
import time

import httpx

FLEET = [
    # hostname, kind, platform, os_version, model, user, department
    ("LT-ASHA-01", "laptop", "windows", "11 23H2", "Dell Latitude 7440", "Asha", "Finance"),
    ("LT-RAHUL-02", "laptop", "windows", "11 24H2", "Lenovo ThinkPad T14", "Rahul", "Sales"),
    ("MB-MEERA-03", "laptop", "macos", "14.5", "MacBook Air M3", "Meera", "Design"),
    ("LT-JOHN-04", "laptop", "windows", "10 22H2", "HP EliteBook 840", "John", "Engineering"),
    ("DT-FIN-01", "desktop", "windows", "11 23H2", "Dell OptiPlex 7010", "Finance kiosk", "Finance"),
    ("DT-DESIGN-02", "desktop", "macos", "14.4", "iMac 24", "Kiran", "Design"),
    ("PH-ASHA-P8", "mobile", "android", "14", "Pixel 8", "Asha", "Finance"),
    ("PH-RAHUL-S23", "mobile", "android", "12", "Galaxy S23", "Rahul", "Sales"),
    ("PH-MEERA-15", "mobile", "ios", "17.5", "iPhone 15", "Meera", "Design"),
    ("PH-JOHN-12", "mobile", "ios", "16.7", "iPhone 12", "John", "Engineering"),
    ("CTX-CALLC-01", "vdi", "citrix", "Win 11 MS", "Citrix VDA 2402", "Lina", "Support"),
    ("CTX-CALLC-02", "vdi", "citrix", "Win 11 MS", "Citrix VDA 2402", "Omar", "Support"),
    ("AVD-DEV-01", "vdi", "avd", "Win 11 EVD", "AVD D4s_v5", "Sam", "Engineering"),
    ("AVD-DEV-02", "vdi", "avd", "Win 11 EVD", "AVD D4s_v5", "Priya", "Engineering"),
]

# office per device (drives the location heatmap and benchmarks)
LOCATION = {"LT-ASHA-01": "Bangalore", "LT-RAHUL-02": "London", "MB-MEERA-03": "Bangalore", "LT-JOHN-04": "New York",
            "DT-FIN-01": "Bangalore", "DT-DESIGN-02": "London", "PH-ASHA-P8": "Bangalore", "PH-RAHUL-S23": "London",
            "PH-MEERA-15": "Bangalore", "PH-JOHN-12": "New York", "CTX-CALLC-01": "Bangalore",
            "CTX-CALLC-02": "Bangalore", "AVD-DEV-01": "London", "AVD-DEV-02": "New York"}

APPS = {
    "laptop": [("Teams", "24.1"), ("Outlook", "16.0.17"), ("Chrome", "128.0"), ("Excel", "16.0.17"), ("Zoom", "6.1")],
    "desktop": [("Teams", "24.1"), ("Outlook", "16.0.17"), ("Edge", "128.0"), ("SAP GUI", "8.0")],
    "mobile": [("Teams", "6.12"), ("Outlook", "4.24"), ("WhatsApp", "2.24"), ("Slack", "24.08")],
    "vdi": [("Teams", "24.1"), ("Outlook", "16.0.17"), ("Edge", "128.0"), ("SAP GUI", "8.0"), ("Citrix Workspace", "2402")],
}
COMPLAINTS = [
    ("Laptop is really slow", "Everything takes ages to open this morning."),
    ("Outlook keeps freezing", "Outlook hangs every time I open an attachment."),
    ("Teams calls dropping", "My Teams calls keep dropping after a few minutes."),
    ("Battery drains fast", "My battery is empty by lunchtime."),
    ("Virtual desktop laggy", "Typing in the virtual desktop has a big delay."),
]
COMMENTS = ["", "", "", "Much faster since the fix, thanks!", "Teams is still a bit laggy.",
            "Love the quick tips.", "Wi-Fi in the office is poor.", "Battery could be better."]

DEVICE_FAULTS = {
    "disk_full": lambda d: d.s.update(disk_pct=random.uniform(91, 98)),
    "high_cpu": lambda d: d.s.update(cpu_pct=random.uniform(92, 99)),
    "high_memory": lambda d: d.s.update(mem_pct=random.uniform(93, 98)),
    "slow_network": lambda d: d.s.update(network_latency_ms=random.uniform(320, 600)),
    "low_battery": lambda d: d.s.update(battery_pct=random.uniform(5, 14), battery_plugged=False),
    "os_errors": lambda d: d.s.update(os_errors_24h=random.randint(25, 60)),
    "app_slow": lambda d: d.app_fault("latency_ms", random.uniform(1600, 3200)),
    "app_memory": lambda d: d.app_fault("mem_mb", random.uniform(2600, 3600)),
}
# what a successful remediation does to the simulated device
FIXES = {
    "clean_temp": lambda d, t: d.s.update(disk_pct=random.uniform(55, 70)),
    "top_processes": lambda d, t: d.s.update(cpu_pct=random.uniform(15, 35)),
    "repair_app": lambda d, t: d.reset_app(t),
    "restart_app": lambda d, t: d.reset_app(t),
    "install_updates": lambda d, t: d.s.update(patch_age_days=0),
    "schedule_reboot": lambda d, t: d.s.update(uptime_hours=0.2, mem_pct=random.uniform(35, 50)),
}


class SimDevice:
    def __init__(self, spec, server, token, http):
        self.host, self.kind, self.platform, self.os_version, self.model, self.user, self.dept = spec
        self.server, self.http = server, http
        r = http.post(f"{server}/api/enroll", json={
            "token": token, "hostname": self.host, "kind": self.kind, "platform": self.platform,
            "os_version": self.os_version, "model": self.model, "user": self.user, "department": self.dept,
            "location": LOCATION.get(self.host), "demo": True, "device_id": "sim-" + self.host.lower()})
        r.raise_for_status()
        self.key = r.json()["key"]
        mobile, vdi = self.kind == "mobile", self.kind == "vdi"
        self.s = {
            "cpu_pct": random.uniform(10, 40), "mem_pct": random.uniform(40, 70),
            "disk_pct": random.uniform(40, 78), "crashes_24h": 0,
            "network_latency_ms": random.uniform(20, 90),
            "uptime_hours": random.uniform(1, 30) if mobile or vdi else random.uniform(5, 200),
            "os_errors_24h": random.randint(0, 8),
        }
        if not mobile:
            self.s["patch_age_days"] = random.choice([3, 8, 12, 21, 35])
        if self.kind in ("laptop", "mobile"):
            self.s.update(battery_pct=random.uniform(40, 100), battery_plugged=random.random() < .3,
                          battery_health_pct=random.uniform(65, 100))
        if self.kind in ("laptop", "desktop"):
            self.s["boot_seconds"] = random.uniform(25, 140)
        if vdi:
            self.s.update(session_latency_ms=random.uniform(40, 110), logon_seconds=random.uniform(15, 40),
                          protocol="HDX" if self.platform == "citrix" else "RDP",
                          session_host=f"{self.platform.upper()}-HOST-{random.randint(1, 3):02d}")
        self.filling = random.random() < .3 and not vdi   # slowly fills its disk -> predictions
        self.apps = {n: {"name": n, "version": v, "cpu_pct": random.uniform(1, 15), "mem_mb": random.uniform(150, 900),
                         "crashes_24h": 0, "hangs_24h": 0, "latency_ms": random.uniform(150, 600)}
                     for n, v in APPS[self.kind]}
        self.conversation = None

    @property
    def h(self):
        return {"X-Device-Key": self.key}

    def app_fault(self, field, value, name=None):
        a = self.apps[name or random.choice(list(self.apps))]
        a[field] = value
        return a["name"]

    def reset_app(self, name):
        if name in self.apps:
            self.apps[name].update(crashes_24h=0, hangs_24h=0, mem_mb=random.uniform(200, 700),
                                   latency_ms=random.uniform(150, 500))

    def drift(self):
        s = self.s
        walk = lambda v, d, lo, hi: max(lo, min(hi, v + random.uniform(-d, d)))  # noqa: E731
        s["cpu_pct"] = walk(s["cpu_pct"], 8, 3, 85)
        s["mem_pct"] = walk(s["mem_pct"], 4, 25, 88)
        if s["disk_pct"] < 90:
            # filling disks rise steadily (time-compressed: ~1%/min); the rest wobble
            s["disk_pct"] = min(99, s["disk_pct"] + (random.uniform(.03, .07) if self.filling else random.uniform(-.15, .15)))
        if s["network_latency_ms"] < 300:
            s["network_latency_ms"] = walk(s["network_latency_ms"], 15, 10, 200)
        s["uptime_hours"] += 0.5
        if "battery_pct" in s:
            if s["battery_plugged"]:
                s["battery_pct"] = min(100, s["battery_pct"] + 2)
            elif s["battery_pct"] > 15:
                s["battery_pct"] = max(16, s["battery_pct"] - random.uniform(0, 1.5))
            if random.random() < .05:
                s["battery_plugged"] = not s["battery_plugged"]
        if "session_latency_ms" in s and s["session_latency_ms"] < 200:
            s["session_latency_ms"] = walk(s["session_latency_ms"], 12, 30, 160)
        for a in self.apps.values():
            a["cpu_pct"] = walk(a["cpu_pct"], 3, .5, 40)
            if a["mem_mb"] < 2500:
                a["mem_mb"] = walk(a["mem_mb"], 40, 120, 1500)
            if a["latency_ms"] < 1500:
                a["latency_ms"] = walk(a["latency_ms"], 60, 100, 1100)

        if random.random() < .035:
            fault = random.choice(list(DEVICE_FAULTS))
            if self.kind == "mobile" and fault == "high_cpu":
                fault = "slow_network"
            DEVICE_FAULTS[fault](self)
            print(f"  ⚡ fault on {self.host}: {fault}")
        elif random.random() < .08:
            # transient problems heal on their own
            if s["mem_pct"] > 90:
                s["mem_pct"] = 60
            if s["network_latency_ms"] > 300:
                s["network_latency_ms"] = 60
            if s["os_errors_24h"] > 20 and random.random() < .4:
                s["os_errors_24h"] = random.randint(0, 6)
            for a in self.apps.values():
                if a["latency_ms"] >= 1500 and random.random() < .4:
                    a["latency_ms"] = random.uniform(200, 500)
            if self.kind == "mobile" and random.random() < .3:
                s["disk_pct"] = min(s["disk_pct"], 70)   # user cleared photos after the guide
                for a in self.apps.values():
                    a["crashes_24h"] = 0                 # user updated the crashing app
            if self.kind == "vdi" and s["session_latency_ms"] >= 200 and random.random() < .5:
                s["session_latency_ms"] = random.uniform(50, 100)

    def tick(self):
        self.drift()
        self.http.post(f"{self.server}/api/telemetry",
                       json={"metrics": self.s, "apps": list(self.apps.values())}, headers=self.h)
        cmds = self.http.get(f"{self.server}/api/agent/commands", headers=self.h).json()
        for a in cmds["actions"]:
            ok = random.random() > .1
            if ok and a["action"] in FIXES:
                FIXES[a["action"]](self, a.get("target"))
            self.http.post(f"{self.server}/api/agent/actions/{a['id']}/result", headers=self.h,
                           json={"ok": ok, "output": "simulated run" if ok else "simulated failure"})
        for n in cmds["notifications"]:
            if n["kind"] in ("survey", "pulse") and random.random() < .75:
                good = all(a["crashes_24h"] == 0 for a in self.apps.values()) and self.s["disk_pct"] < 90
                rating = random.choice([4, 5, 5] if good else [2, 3, 4])
                self.http.post(f"{self.server}/api/agent/survey", headers=self.h,
                               json={"rating": rating, "comment": random.choice(COMMENTS),
                                     "campaign_id": (n.get("payload") or {}).get("campaign_id")})
            elif n["kind"] == "guide" and random.random() < .6:
                did = (n.get("payload") or {}).get("delivery_id")
                if did:
                    self.http.post(f"{self.server}/api/agent/guides/{did}", headers=self.h,
                                   json={"status": "completed"})
            elif n["kind"] == "message" and self.conversation and random.random() < .7:
                self.http.post(f"{self.server}/api/agent/conversations/{self.conversation}/messages",
                               headers=self.h, json={"text": random.choice(
                                   ["Thanks, that worked! 🙏", "Still happening, sorry.", "Ok, I'll try that now."])})
        # occasionally an employee asks IT for help
        if random.random() < .006:
            subject, text = random.choice(COMPLAINTS)
            r = self.http.post(f"{self.server}/api/agent/conversations", headers=self.h,
                               json={"subject": subject, "text": text})
            self.conversation = r.json().get("id")
            print(f"  💬 {self.host} opened a conversation: {subject}")


def crash_wave(fleet):
    """Simulate a bad app release: one version starts crashing on several devices at once."""
    app = random.choice(["Teams", "Outlook"])
    targets = [d for d in fleet if app in d.apps and d.kind != "mobile"]
    hit = random.sample(targets, k=min(len(targets), random.randint(3, 5)))
    bad = {"Teams": "24.3.1", "Outlook": "16.0.18"}[app]
    for d in hit:
        d.apps[app].update(version=bad, crashes_24h=random.randint(3, 7), hangs_24h=random.randint(1, 4))
    print(f"  🌊 crash wave: {app} {bad} on {', '.join(d.host for d in hit)}")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows consoles default to cp1252
    ap = argparse.ArgumentParser(description="DWIP fleet simulator")
    ap.add_argument("--server", default="http://127.0.0.1:8000")
    ap.add_argument("--token", default="dev-token")
    ap.add_argument("--interval", type=float, default=3)
    a = ap.parse_args()
    http = httpx.Client(timeout=30)
    for _ in range(30):   # wait for the server
        try:
            http.get(f"{a.server}/api/summary")
            break
        except httpx.HTTPError:
            time.sleep(1)
    fleet = []
    for spec in FLEET:
        fleet.append(SimDevice(spec, a.server, a.token, http))
        time.sleep(.25)  # staggered so the dashboard animates them in
    print(f"simulating {len(fleet)} devices — Ctrl+C to stop")
    tick = 0
    try:
        while True:
            tick += 1
            if tick % 60 == 20:
                crash_wave(fleet)
            if tick % 80 == 40:   # shared VDI infrastructure degrades -> every session lags
                for d in fleet:
                    if d.kind == "vdi":
                        d.s["session_latency_ms"] = random.uniform(230, 400)
                print("  🌊 VDI infrastructure slowdown")
            for d in fleet:
                try:
                    d.tick()
                except httpx.HTTPError as e:
                    print(f"  ! {d.host}: {e}")
            time.sleep(a.interval)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
