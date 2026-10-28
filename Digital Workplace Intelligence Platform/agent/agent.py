"""DWIP endpoint agent for laptops and desktops (Windows, macOS, Linux).

Collects health telemetry, runs remediation actions sent by the server and shows
user notifications. Actions are DRY-RUN unless --allow-actions is passed, and
reboot/repair are always simulated.

    python agent/agent.py --server http://127.0.0.1:8000
"""
import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
import time
import uuid

import httpx
import psutil

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".agent_state.json")
TEMP_AGE_DAYS = 7
OS_CACHE_SECONDS = 600

# process name -> friendly application name (only these are reported as "applications")
KNOWN_APPS = {
    "ms-teams": "Teams", "teams": "Teams", "outlook": "Outlook", "olk": "Outlook", "chrome": "Chrome",
    "msedge": "Edge", "excel": "Excel", "winword": "Word", "powerpnt": "PowerPoint", "zoom": "Zoom",
    "slack": "Slack", "saplogon": "SAP GUI", "code": "Code", "explorer": "Explorer", "onedrive": "OneDrive",
    "firefox": "Firefox", "safari": "Safari", "wfica32": "Citrix Workspace", "msrdc": "Remote Desktop",
    "acrobat": "Acrobat", "acrord32": "Acrobat",
}

# One PowerShell call gathers OS health and per-app crash counts (cached for OS_CACHE_SECONDS).
OS_PROBE = r"""
$since = (Get-Date).AddDays(-1)
$crash = Get-WinEvent -FilterHashtable @{LogName='Application';Id=1000,1002;StartTime=$since} -ErrorAction SilentlyContinue
$apps = @{}
foreach ($e in $crash) { $n = [IO.Path]::GetFileNameWithoutExtension([string]$e.Properties[0].Value).ToLower(); $apps[$n] = 1 + [int]$apps[$n] }
$err = (Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2;StartTime=$since} -ErrorAction SilentlyContinue | Measure-Object).Count
$hf = Get-HotFix -ErrorAction SilentlyContinue | Where-Object InstalledOn | Sort-Object InstalledOn -Descending | Select-Object -First 1
$age = if ($hf) { [int]((Get-Date) - $hf.InstalledOn).TotalDays } else { $null }
@{ crashes = $crash.Count; apps = $apps; os_errors = $err; patch_age = $age } | ConvertTo-Json -Compress
"""


class Agent:
    def __init__(self, server: str, token: str, interval: int, allow_actions: bool, kind: str | None,
                 location: str | None = None, department: str | None = None):
        self.server = server.rstrip("/")
        self.token = token
        self.interval = interval
        self.allow_actions = allow_actions
        self.kind = kind
        self.location, self.department = location, department
        self.http = httpx.Client(timeout=10)
        self.state = self._load_state()
        self._os_cache: tuple[float, dict] = (0.0, {})
        self._latency = None
        self._procs: dict[int, psutil.Process] = {}
        psutil.cpu_percent(None)  # prime the counter

    # ---------- state & enrolment ----------
    def _load_state(self) -> dict:
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _save_state(self):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.state, f)

    def _platform(self) -> tuple[str, str]:
        system = platform.system()
        if system == "Windows":
            return "windows", platform.version()
        if system == "Darwin":
            return "macos", platform.mac_ver()[0]
        return system.lower(), platform.release()

    @staticmethod
    def _vdi() -> tuple[str, str] | None:
        """Detect a Citrix or AVD/RDS session from the session environment."""
        session = os.environ.get("SESSIONNAME", "")
        if session.upper().startswith("ICA") or os.environ.get("CITRIX_SESSION_ID"):
            return "citrix", "HDX"
        if session.upper().startswith("RDP"):
            return "avd", "RDP"
        return None

    def enroll(self):
        plat, ver = self._platform()
        vdi = self._vdi()
        if vdi and not self.kind:
            plat = vdi[0]
        kind = self.kind or ("vdi" if vdi else "laptop" if psutil.sensors_battery() else "desktop")
        body = {"token": self.token, "hostname": socket.gethostname(), "kind": kind,
                "platform": plat, "os_version": ver, "model": platform.machine(),
                "user": os.environ.get("USERNAME") or os.environ.get("USER", ""),
                "location": self.location, "department": self.department,
                "device_id": self.state.get("device_id") or uuid.uuid5(uuid.NAMESPACE_DNS,
                                                                       f"{socket.gethostname()}-{uuid.getnode()}").hex[:16]}
        r = self.http.post(f"{self.server}/api/enroll", json=body)
        r.raise_for_status()
        self.state.update(r.json())
        self._save_state()
        print(f"[dwip] enrolled as {body['hostname']} ({kind}) id={self.state['device_id']}")
        print(f"[dwip] feedback page: {self.server}/companion?device={self.state['device_id']}&key={self.state['key']}")

    @property
    def headers(self):
        return {"X-Device-Key": self.state["key"]}

    # ---------- telemetry ----------
    def _os_health(self) -> dict:
        """Crash counts per app, OS errors and patch age (Windows only, cached)."""
        if platform.system() != "Windows":
            return {}
        ts, cached = self._os_cache
        if time.time() - ts < OS_CACHE_SECONDS:
            return cached
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-Command", OS_PROBE],
                                 capture_output=True, text=True, timeout=60).stdout.strip()
            data = json.loads(out) if out else {}
        except (OSError, ValueError, subprocess.TimeoutExpired):
            data = {}
        self._os_cache = (time.time(), data)
        return data

    def _apps(self, crashes: dict) -> list[dict]:
        """Aggregate known applications from running processes."""
        apps: dict[str, dict] = {}
        live = set()
        for p in psutil.process_iter(["name"]):
            stem = os.path.splitext((p.info["name"] or "").lower())[0]
            friendly = KNOWN_APPS.get(stem)
            if not friendly:
                continue
            live.add(p.pid)
            proc = self._procs.setdefault(p.pid, p)   # reuse so cpu_percent has a baseline
            try:
                cpu = proc.cpu_percent(None) / psutil.cpu_count()
                mem = proc.memory_info().rss / 1e6
                version = None
                if friendly not in apps and platform.system() == "Windows":
                    version = self._file_version(proc)
            except psutil.Error:
                continue
            a = apps.setdefault(friendly, {"name": friendly, "version": version, "cpu_pct": 0.0, "mem_mb": 0.0,
                                           "crashes_24h": 0})
            a["cpu_pct"] += cpu
            a["mem_mb"] += mem
        for pid in set(self._procs) - live:
            self._procs.pop(pid, None)
        for stem, count in (crashes or {}).items():
            friendly = KNOWN_APPS.get(stem)
            if friendly:
                apps.setdefault(friendly, {"name": friendly, "version": None, "cpu_pct": 0.0, "mem_mb": 0.0})
                apps[friendly]["crashes_24h"] = int(count)
        for a in apps.values():
            a["cpu_pct"] = round(a["cpu_pct"], 1)
            a["mem_mb"] = round(a["mem_mb"])
        return list(apps.values())

    _versions: dict[str, str | None] = {}

    def _file_version(self, proc: psutil.Process) -> str | None:
        try:
            exe = proc.exe()
        except psutil.Error:
            return None
        if exe not in self._versions:
            quoted = exe.replace("'", "''")
            cmd = f"(Get-Item -LiteralPath '{quoted}').VersionInfo.ProductVersion"
            try:
                self._versions[exe] = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True,
                                                     text=True, timeout=10).stdout.strip() or None
            except (OSError, subprocess.TimeoutExpired):
                self._versions[exe] = None
        return self._versions[exe]

    def collect(self) -> tuple[dict, list[dict]]:
        osh = self._os_health()
        vm = psutil.virtual_memory()
        root = os.environ.get("SystemDrive", "C:") + "\\" if platform.system() == "Windows" else "/"
        du = psutil.disk_usage(root)
        m = {
            "cpu_pct": psutil.cpu_percent(None),
            "mem_pct": vm.percent,
            "disk_pct": du.percent,
            "disk_free_gb": round(du.free / 1e9, 1),
            "uptime_hours": round((time.time() - psutil.boot_time()) / 3600, 1),
            "crashes_24h": osh.get("crashes"),
            "os_errors_24h": osh.get("os_errors"),
            "patch_age_days": osh.get("patch_age"),
            "network_latency_ms": self._latency,
        }
        batt = psutil.sensors_battery()
        if batt:
            m["battery_pct"] = round(batt.percent)
            m["battery_plugged"] = bool(batt.power_plugged)
        vdi = self._vdi()
        if vdi:
            m["protocol"] = vdi[1]
            m["session_host"] = socket.gethostname()
            m["session_latency_ms"] = self._latency
        return {k: v for k, v in m.items() if v is not None}, self._apps(osh.get("apps") or {})

    def send(self):
        t0 = time.perf_counter()
        try:
            self.http.get(f"{self.server}/api/ping")
            self._latency = round((time.perf_counter() - t0) * 1000)
        except httpx.HTTPError:
            self._latency = None
        metrics, apps = self.collect()
        r = self.http.post(f"{self.server}/api/telemetry", json={"metrics": metrics, "apps": apps},
                           headers=self.headers)
        if r.status_code == 401:
            self.enroll()
            return
        r.raise_for_status()
        res = r.json()
        print(f"[dwip] telemetry sent — DEX {res['dex']} ({res['findings']} findings, {len(apps)} apps)", flush=True)

    # ---------- actions ----------
    def _clean_temp(self) -> tuple[bool, str]:
        tmp = tempfile.gettempdir()
        cutoff = time.time() - TEMP_AGE_DAYS * 86400
        total, files, removed = 0, 0, 0
        for dirpath, _, names in os.walk(tmp):
            for n in names:
                p = os.path.join(dirpath, n)
                try:
                    st = os.stat(p)
                    if st.st_mtime >= cutoff:
                        continue
                    total += st.st_size
                    files += 1
                    if self.allow_actions:
                        os.remove(p)
                        removed += 1
                except OSError:
                    continue
        mb = total / 1e6
        if self.allow_actions:
            return True, f"Removed {removed}/{files} temp files older than {TEMP_AGE_DAYS}d ({mb:.0f} MB) from {tmp}"
        return True, f"[dry-run] Would remove {files} temp files ({mb:.0f} MB) from {tmp}"

    def _top_processes(self) -> tuple[bool, str]:
        procs = []
        for p in psutil.process_iter(["name"]):
            try:
                procs.append((p.cpu_percent(None), p.info["name"]))
            except psutil.Error:
                pass
        time.sleep(1)
        sample = []
        for p in psutil.process_iter(["name"]):
            try:
                sample.append((p.cpu_percent(None), p.info["name"]))
            except psutil.Error:
                pass
        top = sorted(sample, reverse=True)[:5]
        return True, "Top CPU: " + ", ".join(f"{n} {c:.0f}%" for c, n in top)

    def run_action(self, name: str, target: str | None = None) -> tuple[bool, str]:
        if name == "clean_temp":
            return self._clean_temp()
        if name == "top_processes":
            return self._top_processes()
        if name == "repair_app":
            return True, f"[simulated] Would reset {target or 'the app'}'s cache and re-register it"
        if name == "restart_app":
            return True, f"[simulated] Would ask the user, then restart {target or 'the app'}"
        if name == "install_updates":
            return True, "[simulated] Would trigger a Windows Update scan and install, deferring the restart"
        if name == "schedule_reboot":
            return True, "[simulated] Would schedule a restart for 02:00 with a 15-minute user warning"
        return False, f"Unknown action {name}"

    def poll(self):
        r = self.http.get(f"{self.server}/api/agent/commands", headers=self.headers)
        if r.status_code != 200:
            return
        data = r.json()
        for a in data["actions"]:
            print(f"[dwip] running action #{a['id']}: {a['action']} {a.get('target') or ''}", flush=True)
            try:
                ok, out = self.run_action(a["action"], a.get("target"))
            except Exception as e:  # never let a fix crash the agent
                ok, out = False, str(e)
            print(f"[dwip]   -> {'ok' if ok else 'FAILED'}: {out}")
            self.http.post(f"{self.server}/api/agent/actions/{a['id']}/result",
                           json={"ok": ok, "output": out}, headers=self.headers)
        for n in data["notifications"]:
            print(f"\n  🔔 DWIP: {n['message']}\n", flush=True)

    # ---------- loop ----------
    def run(self):
        if "key" not in self.state:
            self.enroll()
        mode = "LIVE actions" if self.allow_actions else "dry-run actions"
        print(f"[dwip] reporting every {self.interval}s to {self.server} ({mode}) — Ctrl+C to stop")
        while True:
            try:
                self.send()
                self.poll()
            except httpx.HTTPError as e:
                print(f"[dwip] server unreachable ({e}); retrying")
            time.sleep(self.interval)


def main():
    ap = argparse.ArgumentParser(description="DWIP endpoint agent")
    ap.add_argument("--server", default=os.environ.get("DWIP_SERVER", "http://127.0.0.1:8000"))
    ap.add_argument("--token", default=os.environ.get("DWIP_ENROLL_TOKEN", "dev-token"))
    ap.add_argument("--interval", type=int, default=15)
    ap.add_argument("--location", default=os.environ.get("DWIP_LOCATION"), help="office/site, e.g. Bangalore")
    ap.add_argument("--department", default=os.environ.get("DWIP_DEPARTMENT"))
    ap.add_argument("--kind", choices=["laptop", "desktop", "vdi"], help="override auto-detection")
    ap.add_argument("--allow-actions", action="store_true", help="really delete old temp files")
    ap.add_argument("--once", action="store_true", help="send one sample and exit")
    a = ap.parse_args()
    agent = Agent(a.server, a.token, a.interval, a.allow_actions, a.kind, a.location, a.department)
    if a.once:
        if "key" not in agent.state:
            agent.enroll()
        agent.send()
        agent.poll()
        return
    try:
        agent.run()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
