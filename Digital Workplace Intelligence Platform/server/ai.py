"""AI layer: local LLM (Ollama) for insights and conversations, with a rule-based fallback.

Env:
  DWIP_AI=off             disable the LLM (rules only)
  DWIP_OLLAMA_URL         default http://127.0.0.1:11434
  DWIP_LLM_MODEL          default gemma3:4b
"""
import asyncio
import json
import os
import re
import time

import httpx

IT_SYSTEM = (
    "You are DWIP Copilot, an assistant for IT support staff running a digital employee experience "
    "platform. Answer using ONLY the JSON fleet context provided. Be concise (max ~120 words), use "
    "short bullet points, name specific devices/apps/numbers, and finish with one recommended next step. "
    "Never invent device names, versions or numbers that are not in the data. "
    "If the context does not contain the answer, say so."
)
EMPLOYEE_SYSTEM = (
    "You are DWIP Helper, a friendly assistant that helps an employee with their own work device. "
    "Use ONLY the JSON device context provided. Reply in plain, warm language (max ~90 words), no jargon. "
    "Give 1-3 simple steps the user can try. If it needs IT, suggest tapping 'Talk to IT'."
)
INSIGHT_SYSTEM = (
    "You are an SRE analysing an end-user computing alert. In at most 3 short sentences explain the "
    "likely root cause and the single best remediation. Be specific and use the numbers provided. "
    "Respect the device kind (a physical laptop/desktop is not a VM). Never invent versions, hosts "
    "or numbers that are not in the context — e.g. say 'roll back to the previous version', not a made-up one."
)


class AI:
    def __init__(self, enabled: bool | None = None):
        if enabled is None:
            enabled = os.environ.get("DWIP_AI", "on").lower() != "off"
        self.enabled = enabled
        self.url = os.environ.get("DWIP_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
        self.model = os.environ.get("DWIP_LLM_MODEL", "gemma3:4b")
        self._up: tuple[float, bool] = (0.0, False)
        # Ollama serves requests roughly one at a time, so people chatting go first:
        # background work (alert insights, triage) runs one at a time, yields to chats,
        # and is dropped when the backlog grows (the rule-based text is kept).
        self._interactive = 0
        self._bg_lock = asyncio.Lock()
        self._bg_waiting = 0
        self.max_backlog = 3
        self.ledger = None   # callable(purpose, model, prompt_tokens, completion_tokens, latency_ms, ok)

    async def background(self, system: str, prompt: str, timeout: float = 60,
                         purpose: str = "background") -> str | None:
        if self._bg_waiting >= self.max_backlog:
            return None
        self._bg_waiting += 1
        try:
            async with self._bg_lock:
                while self._interactive:
                    await asyncio.sleep(0.5)
                return await self.generate(system, prompt, timeout, purpose=purpose)
        finally:
            self._bg_waiting -= 1

    async def available(self) -> bool:
        if not self.enabled:
            return False
        ts, up = self._up
        if time.time() - ts < (60 if up else 10):   # re-check sooner after a failure
            return up
        try:
            async with httpx.AsyncClient(timeout=8) as c:   # Ollama answers slowly while generating
                r = await c.get(f"{self.url}/api/tags")
                names = {m["name"] for m in r.json().get("models", [])}
                up = self.model in names or f"{self.model}:latest" in names
        except (httpx.HTTPError, ValueError, KeyError):
            up = False
        self._up = (time.time(), up)
        return up

    async def generate(self, system: str, prompt: str, timeout: float = 90,
                       history: list[dict] | None = None, purpose: str = "chat") -> str | None:
        if not await self.available():
            return None
        messages = [{"role": "system", "content": system}]
        messages += [{"role": "assistant" if h.get("role") == "assistant" else "user", "content": str(h.get("text", ""))}
                     for h in (history or [])[-6:]]
        messages.append({"role": "user", "content": prompt})
        start, data = time.perf_counter(), {}
        try:
            async with httpx.AsyncClient(timeout=timeout) as c:
                r = await c.post(f"{self.url}/api/chat", json={
                    "model": self.model, "stream": False, "keep_alive": "30m",
                    "options": {"temperature": 0.2, "num_predict": 300}, "messages": messages})
                r.raise_for_status()
                data = r.json()
                text = data["message"]["content"]
        except (httpx.HTTPError, ValueError, KeyError):
            text = None
        if self.ledger:
            self.ledger(purpose, self.model, data.get("prompt_eval_count"), data.get("eval_count"),
                        (time.perf_counter() - start) * 1000, text is not None)
        if text is None:
            return None
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
        # small models sometimes echo the context instead of answering
        if not text or text.startswith(("```json", "{", "[")):
            return None
        return text

    async def interactive(self, system: str, prompt: str, purpose: str = "assist") -> str | None:
        """A request someone is waiting for: background work yields to it."""
        self._interactive += 1
        try:
            return await self.generate(system, prompt, purpose=purpose)
        finally:
            self._interactive -= 1

    # ---------- public helpers ----------
    async def insight(self, alert: dict, context: dict) -> tuple[str, str]:
        prompt = f"Alert: {alert['title']}\nContext: {json.dumps(context, default=str)[:2000]}"
        text = await self.background(INSIGHT_SYSTEM, prompt, purpose="insight")
        return (text, "llm") if text else (rule_insight(alert, context), "rules")

    async def chat(self, question: str, context: dict, role: str = "it",
                   history: list[dict] | None = None, background: bool = False) -> tuple[str, str]:
        system = ((IT_SYSTEM if role == "it" else EMPLOYEE_SYSTEM)
                  + "\n\nREFERENCE DATA (JSON). Use it to answer; never repeat or print it:\n"
                  + json.dumps(context, default=str, separators=(",", ":"))[:4500])
        prompt = f"{question}\n\nAnswer in plain sentences or short bullets, not JSON."
        if background:
            text = await self.background(system, prompt, purpose="triage")
        else:
            self._interactive += 1
            try:
                text = await self.generate(system, prompt, history=history)
            finally:
                self._interactive -= 1
        if text:
            return text, "llm"
        return (rule_it_answer(question, context) if role == "it"
                else rule_employee_answer(question, context)), "rules"


# ---------- rule-based fallbacks ----------
def rule_insight(alert: dict, ctx: dict) -> str:
    t = alert.get("type", "")
    n = ctx.get("devices_affected", 1)
    if t.startswith("app_crash:"):
        app = t.split(":", 1)[1]
        vers = ctx.get("versions") or {}
        top = max(vers, key=vers.get) if vers else "?"
        return (f"{app} is crashing on {n} devices, most on version {top}. A shared version points to an "
                f"app regression rather than device faults — pause the rollout of {top} and repair or roll back.")
    if t.startswith("app_slow:"):
        return (f"{t.split(':', 1)[1]} is slow on {n} devices at once, which suggests a backend or network "
                "dependency. Check the service health and the network path before touching endpoints.")
    if t == "vdi_latency":
        return (f"{n} virtual desktop sessions are lagging together — likely session-host load or the WAN "
                "link. Check host CPU/session density and move users to a less busy host.")
    if t == "os_patch_overdue":
        return f"{n} devices are behind on patches. Approve the update action in bulk during the next maintenance window."
    if t == "anomaly":
        return ("This device's experience dropped well below its own normal baseline. Compare the vitals "
                "with the previous hour — a new app, update or resource spike is the usual cause.")
    return (f"The same issue ({alert.get('title')}) is open on {n} devices. A common cause is likely; "
            "check recent changes affecting all of them.")


def _devices_matching(ctx, key):
    return [d for d in ctx.get("worst_devices", []) if key(d)]


def rule_it_answer(q: str, ctx: dict) -> str:
    ql = q.lower()
    s = ctx.get("summary", {})
    if any(w in ql for w in ("app", "application", "teams", "outlook", "crash")):
        apps = ctx.get("apps", [])[:5]
        if not apps:
            return "No application data yet."
        lines = [f"• {a['app']}: score {a['score']}, {a['crashes']} crashes, {a['avg_latency_ms']} ms on {a['devices']} devices"
                 for a in apps]
        return "Least healthy applications:\n" + "\n".join(lines) + "\nNext step: open the worst app in Applications to see affected versions."
    if any(w in ql for w in ("predict", "forecast", "will", "soon", "risk")):
        p = ctx.get("predictions", [])[:5]
        if not p:
            return "No risks predicted right now. 🎉"
        return "Upcoming risks:\n" + "\n".join(f"• {x['hostname']}: {x['title']} ({x['eta']})" for x in p)
    if any(w in ql for w in ("alert", "incident", "problem", "issue", "wrong")):
        al = ctx.get("alerts", [])[:5]
        if not al:
            return f"No open alerts. {s.get('open_issues', 0)} device-level issues are being handled."
        return "Open alerts:\n" + "\n".join(f"• [{a['severity']}] {a['title']}" for a in al)
    if any(w in ql for w in ("vdi", "citrix", "avd", "virtual")):
        v = _devices_matching(ctx, lambda d: d["kind"] == "vdi")
        return ("VDI sessions needing attention:\n" + "\n".join(f"• {d['hostname']}: DEX {d['dex']}" for d in v)
                if v else "All VDI sessions look healthy.")
    if any(w in ql for w in ("worst", "slow", "unhappy", "bad", "device")):
        w = ctx.get("worst_devices", [])[:5]
        return "Devices with the lowest experience:\n" + "\n".join(
            f"• {d['hostname']} ({d['kind']}): DEX {d['dex']}, {d['open_issues']} issues" for d in w)
    return (f"Fleet DEX is {s.get('dex')} across {s.get('devices')} devices ({s.get('online')} online), with "
            f"{s.get('open_issues')} open issues and {s.get('pending_approvals')} fixes awaiting approval. "
            "Ask me about apps, alerts, predictions, VDI or the worst devices.")


def rule_employee_answer(q: str, ctx: dict) -> str:
    ql = q.lower()
    m = ctx.get("metrics", {})
    issues = ctx.get("issues", [])
    if any(w in ql for w in ("slow", "lag", "freez", "hang")):
        tips = []
        if (m.get("cpu_pct") or 0) > 80:
            tips.append("close apps you are not using — your processor is very busy")
        if (m.get("mem_pct") or 0) > 85:
            tips.append("restart heavy apps like your browser — memory is nearly full")
        if (m.get("disk_pct") or 0) > 88:
            tips.append("free up some storage — it is almost full")
        if not tips:
            tips.append("restart the app that feels slow, and your device if it has been on for days")
        return "Here's what I'd try: " + "; ".join(tips) + ". If it is still slow, tap 'Talk to IT'."
    if any(w in ql for w in ("battery", "charge")):
        return (f"Your battery is at {m.get('battery_pct', '?')}%. Lower screen brightness and close video apps. "
                "If it drains fast every day, tap 'Talk to IT' — it may need replacing.")
    if any(w in ql for w in ("storage", "space", "disk", "full")):
        return f"You are using {m.get('disk_pct', '?')}% of your storage. Check the 'Free up storage' guide in Guides."
    if issues:
        return "I can see: " + "; ".join(i["title"] for i in issues[:3]) + \
               ". IT is already on it. Tap 'Talk to IT' if you need help now."
    return "Your device looks healthy right now 👍. Describe what's bothering you, or tap 'Talk to IT'."
