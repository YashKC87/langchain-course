// DWIP console — live, animated, no build step.
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const C = 2 * Math.PI * 52; // ring circumference
const ICON = { laptop: "💻", desktop: "🖥️", mobile: "📱", vdi: "☁️" };
const KIND_LABEL = { laptop: "Laptops", desktop: "Desktops", mobile: "Mobiles", vdi: "Virtual desktops" };
const APP_ICON = { Teams: "💬", Outlook: "📧", Chrome: "🌐", Edge: "🌊", Excel: "📊", Word: "📝", Zoom: "🎥",
  "SAP GUI": "🏭", Slack: "💼", WhatsApp: "🟢", "Citrix Workspace": "☁️", Explorer: "📁", Safari: "🧭", Code: "🧑‍💻" };
const FEED_ICON = { enroll: "🆕", issue: "⚠️", decision: "🧠", executed: "✅", failed: "❌", resolved: "💚",
  survey: "⭐", approval: "🛡️", alert: "🚨", guide: "🧭", conversation: "💬", pulse: "📣" };
const state = { view: "overview", kind: "", openId: null, openApp: null, thread: null, values: {}, cpHistory: [] };

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
// console access token (only needed when the server has DWIP_IT_TOKENS set)
const authToken = () => { try { return localStorage.getItem("dwip-token") || ""; } catch { return ""; } };
const api = (p, opt = {}) => fetch(p, { ...opt, headers: { ...(opt.headers || {}), "X-DWIP-Token": authToken() } })
  .then((r) => {
    if (r.status === 401 && typeof showSignin === "function") showSignin();
    if (r.status === 403) toast("🔒 Your role can't do that");
    return r.json();
  });
const post = (p, body) => api(p, { method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body || {}) });
const color = (v) => v == null ? "var(--muted)" : v >= 80 ? "var(--good)" : v >= 60 ? "var(--warn)" : "var(--bad)";
const ago = (ts) => {
  const s = Math.max(0, Date.now() / 1000 - ts);
  return s < 60 ? `${s | 0}s ago` : s < 3600 ? `${(s / 60) | 0}m ago` : s < 86400 ? `${(s / 3600) | 0}h ago` : `${(s / 86400) | 0}d ago`;
};
const appIcon = (n) => APP_ICON[n] || "🧩";

// ---------- animation helpers ----------
function countUp(el, to, dec = 0) {
  if (!el) return;
  if (to == null) { el.textContent = "–"; return; }
  const key = el.dataset.k || el.id || el.dataset.uid;
  const from = state.values[key] ?? 0;
  state.values[key] = to;
  if (from === to) { el.textContent = (+to).toFixed(dec); return; }
  if (from !== 0) { el.classList.remove("bump"); void el.offsetWidth; el.classList.add("bump"); }
  const t0 = performance.now(), dur = 900;
  const tick = (t) => {
    const p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 3);
    el.textContent = (from + (to - from) * e).toFixed(dec);
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}
function setRing(circle, v) {
  circle.style.strokeDasharray = C;
  circle.style.strokeDashoffset = C * (1 - (v ?? 0) / 100);
  circle.style.stroke = color(v);
  circle.style.color = color(v);
}
const ringSvg = (uid) => `<div class="mini"><svg class="ring" viewBox="0 0 120 120"><circle class="track" cx="60" cy="60" r="52"/>
  <circle class="bar" cx="60" cy="60" r="52"/></svg><span data-uid="${uid}">–</span></div>`;
function lightStep(kind) {
  const map = { issue: ["issue"], alert: ["issue", "telemetry"], decision: ["decision"], executed: ["executed", "notify"],
    telemetry: ["telemetry"], survey: ["notify"], guide: ["notify"], conversation: ["notify"] };
  (map[kind] || []).forEach((k) => $$(`.step[data-step="${k}"]`).forEach((s) => {
    s.classList.add("lit");
    setTimeout(() => s.classList.remove("lit"), 1200);
  }));
}
function toast(msg) {
  const t = document.createElement("div");
  t.className = "toast";
  t.innerHTML = msg;
  $("#toasts").appendChild(t);
  setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 400); }, 4200);
  const all = $("#toasts").children;
  if (all.length > 4) all[0].remove();
}
function hbars(box, rows) {
  box.innerHTML = rows.map((r, i) => `<div class="hbar" style="animation-delay:${i * 60}ms">
    <span class="lbl" title="${esc(r.label)}">${esc(r.label)}</span><div class="meter"><b data-w="${r.pct}"></b></div>
    <span style="color:${r.color || color(r.pct)}">${esc(r.value)}</span></div>`).join("") || `<p class="muted">No data yet</p>`;
  requestAnimationFrame(() => $$("b[data-w]", box).forEach((b) => {
    b.style.width = `${b.dataset.w}%`;
    if (b.dataset.w < 60) b.classList.add("hot");
  }));
}

// ---------- routing ----------
const LOADERS = {
  overview: () => Promise.all([loadSummary(), loadInsights(), loadOvPredict(), loadKindBars(), loadOvApps(), loadApprovals()]),
  devices: () => loadDevices(),
  apps: () => loadApps(),
  alerts: () => loadAlerts(),
  predict: () => loadPredict(),
  collab: () => loadThreads(),
  guides: () => loadGuides(),
  engage: () => loadEngagement(),
};
function show(view) {
  if (!LOADERS[view]) view = "overview";
  state.view = view;
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${view}`));
  $$(".nav").forEach((n) => n.classList.toggle("active", n.dataset.view === view));
  if (view === "devices") requestAnimationFrame(() => moveInk($(".tab.active")));
  LOADERS[view]();
}
window.addEventListener("hashchange", () => show(location.hash.slice(1)));
$$(".kpi[data-go]").forEach((k) => k.addEventListener("click", () => (location.hash = k.dataset.go)));

// ---------- overview ----------
async function loadSummary() {
  const s = await api("/api/summary");
  countUp($("#fleet-dex"), s.dex, 0);
  setRing($("#fleet-ring"), s.dex);
  $$(".kpi .num[data-k]").forEach((el) => countUp(el, s[el.dataset.k], +(el.dataset.dec || 0)));
  $("#online-sub").textContent = `${s.online} online · 💻${s.by_kind.laptop} 🖥️${s.by_kind.desktop} 📱${s.by_kind.mobile} ☁️${s.by_kind.vdi}`;
  $("#n-alerts").textContent = s.alerts || "";
  $("#n-unread").textContent = s.unread || "";
}
const alertHtml = (a, full) => `
  <div class="${full ? "card alert-card" : "insight"} ${esc(a.severity)} ${a.status === "ack" ? "ack" : ""} ${a.insight_source === "llm" ? "llm" : ""}" data-id="${a.id}">
    <div class="t">${a.scope === "fleet" ? "🌐" : "📍"} ${esc(a.title)}
      <span class="tag ${esc(a.severity)}">${esc(a.severity)}</span>
      ${a.scope === "fleet" ? `<span class="tag">${a.devices} devices</span>` : ""}
      <span class="tag ${a.insight_source === "llm" ? "ai" : ""}">${a.insight_source === "llm" ? "✨ AI insight" : "rule insight"}</span>
      ${full ? `<span class="muted small">${ago(a.ts)}</span>` : ""}</div>
    <div class="ai-text">${esc(a.insight)}</div>
    ${full ? `<div class="btns">${a.status === "open" ? `<button class="btn ghost" data-op="ack">👀 Acknowledge</button>` : ""}
      <button class="btn go" data-op="resolve">✔ Resolve</button>
      ${a.device_id ? `<button class="btn ghost" data-dev="${esc(a.device_id)}">Open device</button>` : ""}
      <button class="btn ghost" data-ask="${esc(a.title)}">✨ Ask Copilot</button></div>` : ""}
  </div>`;
async function loadInsights() {
  const list = await api("/api/alerts");
  $("#ov-insights").innerHTML = list.slice(0, 4).map((a) => alertHtml(a, false)).join("") ||
    `<p class="muted">No active alerts. The AI is watching. 👀</p>`;
}
const predHtml = (p, full) => `
  <div class="${full ? "card pred" : "insight"}" ${p.device_id ? `data-dev="${esc(p.device_id)}"` : ""} style="cursor:${p.device_id ? "pointer" : "default"}">
    <div class="t">${p.kind === "app" ? "🧩" : ICON[p.kind] || "🔮"} ${esc(p.title)}</div>
    ${full ? `<div class="eta">${esc(p.eta)}</div>` : ""}
    <div class="ai-text">${esc(p.hostname)} · ${esc(p.detail)}${full ? "" : ` · <b>${esc(p.eta)}</b>`}</div>
    ${full ? `<div class="conf">Confidence ${p.confidence}%</div><div class="meter"><b data-w="${p.confidence}"></b></div>` : ""}
  </div>`;
async function loadOvPredict() {
  const list = await api("/api/predictions");
  const box = $("#ov-predict");
  box.innerHTML = list.slice(0, 4).map((p) => predHtml(p, false)).join("") || `<p class="muted">No risks forecast. 🌤️</p>`;
}
async function loadKindBars() {
  const devs = await api("/api/devices");
  const rows = Object.keys(KIND_LABEL).map((k) => {
    const d = devs.filter((x) => x.kind === k && x.dex != null);
    const avg = d.length ? d.reduce((a, x) => a + x.dex, 0) / d.length : null;
    return avg == null ? null : { label: `${ICON[k]} ${KIND_LABEL[k]}`, pct: avg, value: Math.round(avg) };
  }).filter(Boolean);
  hbars($("#ov-kinds"), rows);
}
async function loadOvApps() {
  const apps = await api("/api/apps");
  hbars($("#ov-apps"), apps.slice(0, 5).map((a) => ({ label: `${appIcon(a.app)} ${a.app}`, pct: a.score, value: Math.round(a.score) })));
}

// ---------- approvals & feed ----------
function renderApprovals(box, list) {
  const ids = new Set(list.map((a) => String(a.id)));
  [...box.children].forEach((c) => { if (!ids.has(c.dataset.id) && !c.classList.contains("gone")) c.remove(); });
  list.forEach((a) => {
    if (box.querySelector(`[data-id="${a.id}"]`)) return;
    const el = document.createElement("div");
    el.className = "appr";
    el.dataset.id = a.id;
    el.innerHTML = `<div class="t">${esc(a.action)}${a.target ? ` · ${esc(a.target)}` : ""} <span class="risk ${esc(a.risk)}">${esc(a.risk)}</span></div>
      <div class="d">${esc(a.hostname)} · ${esc(a.title)} — ${esc(a.detail)}</div>
      <div class="btns"><button class="btn go">Approve</button><button class="btn no">Reject</button></div>`;
    $(".go", el).onclick = () => decide(el, a.id, "approve");
    $(".no", el).onclick = () => decide(el, a.id, "reject");
    box.appendChild(el);
  });
}
async function loadApprovals() {
  const list = await api("/api/approvals");
  renderApprovals($("#approvals"), list);
  renderApprovals($("#approvals2"), list);
  $("#appr-count").textContent = list.length;
  $("#n-appr").textContent = list.length || "";
  $("#appr-empty").style.display = list.length ? "none" : "";
}
async function decide(el, id, decision) {
  $$(`.appr[data-id="${id}"]`).forEach((x) => x.classList.add("gone"));
  await api(`/api/actions/${id}/${decision}`, { method: "POST" });
  toast(decision === "approve" ? "🛡️ Approved. The agent will run it at its next check-in." : "Rejected");
  setTimeout(() => { $$(`.appr[data-id="${id}"]`).forEach((x) => x.remove()); refresh(); }, 450);
}
function feedItem(e) {
  const li = document.createElement("li");
  li.innerHTML = `<span>${FEED_ICON[e.kind] || "•"}</span>
    <div>${esc(e.message)}<div class="when" data-ts="${e.ts}">${ago(e.ts)}</div></div>`;
  return li;
}
async function loadFeed() {
  const list = await api("/api/events?limit=30");
  const feed = $("#feed");
  feed.innerHTML = "";
  list.forEach((e, i) => { const li = feedItem(e); li.style.animationDelay = `${i * 30}ms`; feed.appendChild(li); });
}

// ---------- devices ----------
function deviceCard(d) {
  const el = document.createElement("div");
  el.className = "card dev";
  el.dataset.id = d.id;
  el.innerHTML = `
    <div class="head">
      <div class="emoji">${ICON[d.kind] || "❔"}</div>
      <div style="min-width:0"><div class="name"></div><div class="meta"><span class="dot"></span><span class="sub"></span></div></div>
      ${ringSvg(`dex-${d.id}`)}
    </div>
    <div class="bars">
      ${[["cpu", "CPU"], ["mem", "Memory"], ["disk", "Disk"], ["battery", "Battery"], ["session", "Session"]].map(([k, l]) => `
        <div class="bar-row" data-m="${k}"><span>${l}</span><div class="meter"><b></b></div><span class="v">–</span></div>`).join("")}
    </div>
    <span class="chip"></span>`;
  el.addEventListener("click", () => openDrawer(d.id));
  return el;
}
function updateCard(el, d) {
  $(".name", el).innerHTML = `${esc(d.hostname)}${d.demo ? ' <span class="tag demo">DEMO</span>' : ""}`;
  $(".sub", el).textContent = `${d.platform} ${d.os_version || ""} · ${d.user || "—"}`;
  $(".dot", el).classList.toggle("on", d.online);
  setRing($(".mini .bar", el), d.dex);
  countUp($(".mini span", el), d.dex, 0);
  const m = d.metrics || {};
  const vals = { cpu: m.cpu_pct, mem: m.mem_pct, disk: m.disk_pct, battery: m.battery_pct,
    session: m.session_latency_ms != null ? Math.min(100, m.session_latency_ms / 3) : null };
  for (const [k, v] of Object.entries(vals)) {
    const row = $(`[data-m="${k}"]`, el);
    row.style.display = v == null ? "none" : "";
    if (v == null) continue;
    const b = $("b", row);
    b.style.width = `${v}%`;
    const hot = { battery: v <= 20, session: v >= 66 }[k] ?? v >= 85;
    b.classList.toggle("hot", hot);
    $(".v", row).textContent = k === "session" ? `${Math.round(m.session_latency_ms)}ms` : `${Math.round(v)}%`;
  }
  const chip = $(".chip", el);
  chip.textContent = d.open_issues ? `${d.open_issues} open issue${d.open_issues > 1 ? "s" : ""}` : "Healthy";
  chip.classList.toggle("ok", !d.open_issues);
  el.classList.toggle("alert", d.open_issues > 0);
  el.classList.toggle("hidden", !!state.kind && d.kind !== state.kind);
}
async function loadDevices() {
  const list = await api("/api/devices" + filterQs(["location", "department", "data"]));
  const box = $("#devices");
  const keep = new Set(list.map((d) => d.id));
  $$(".dev", box).forEach((el) => { if (!keep.has(el.dataset.id)) el.remove(); });
  $("#empty").style.display = list.length ? "none" : "";
  list.forEach((d, i) => {
    let el = box.querySelector(`[data-id="${d.id}"]`);
    if (!el) {
      el = deviceCard(d);
      el.style.animationDelay = `${Math.min(i, 14) * 50}ms`;
      box.appendChild(el);
    }
    updateCard(el, d);
  });
}
function moveInk(btn) {
  if (!btn || !btn.offsetWidth) return;
  const ink = $(".tab-ink");
  ink.style.left = `${btn.offsetLeft}px`;
  ink.style.width = `${btn.offsetWidth}px`;
}
$$(".tab").forEach((b) => b.addEventListener("click", () => {
  $$(".tab").forEach((t) => t.classList.remove("active"));
  b.classList.add("active");
  moveInk(b);
  state.kind = b.dataset.kind;
  // replay the staggered entrance for the newly visible cards
  $$(".dev").forEach((el, i) => {
    el.style.animation = "none"; void el.offsetWidth;
    el.style.animation = ""; el.style.animationDelay = `${i * 40}ms`;
  });
  loadDevices();
}));
window.addEventListener("resize", () => moveInk($(".tab.active")));

// ---------- device drawer ----------
function spark(history) {
  const W = 500, H = 120, series = [["dex", "var(--accent)"], ["cpu", "var(--accent-2)"], ["mem", "#ec4899"]];
  if (history.length < 2) return `<p class="muted">Collecting history…</p>`;
  const x = (i) => (i / (history.length - 1)) * W;
  const y = (v) => H - 6 - ((v ?? 0) / 100) * (H - 12);
  const paths = series.map(([k, col]) => {
    const pts = history.map((h, i) => `${x(i).toFixed(1)},${y(h[k]).toFixed(1)}`);
    const line = `M${pts.join("L")}`;
    const area = k === "dex" ? `<path class="a" d="${line}L${W},${H}L0,${H}Z" fill="${col}"/>` : "";
    return `${area}<path class="l" d="${line}" stroke="${col}"/>`;
  }).join("");
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${paths}</svg>
    <div class="legend"><span><i style="background:var(--accent)"></i>DEX</span>
    <span><i style="background:var(--accent-2)"></i>CPU</span><span><i style="background:#ec4899"></i>Memory</span></div>`;
}
const fmt = (v, u = "") => v == null ? "—" : `${typeof v === "number" ? Math.round(v * 10) / 10 : esc(v)}${u}`;
function openPanel() { $("#drawer").classList.add("open"); $("#scrim").classList.add("open"); }
let guideCache = [];
async function openDrawer(id, keepOpen = false) {
  state.openId = id; state.openApp = null;
  const d = await api(`/api/devices/${id}`);
  if (!guideCache.length) guideCache = await api("/api/guides");
  const m = d.metrics || {}, s = d.scores || {};
  const vitals = [
    ["CPU", fmt(m.cpu_pct, "%")], ["Memory", fmt(m.mem_pct, "%")], ["Storage used", fmt(m.disk_pct, "%")],
    ["Free", fmt(m.disk_free_gb, " GB")], ["Battery", `${fmt(m.battery_pct, "%")}${m.battery_plugged ? " ⚡" : ""}`],
    ["Battery health", fmt(m.battery_health_pct, "%")], ["Uptime", fmt(m.uptime_hours, " h")], ["Crashes 24h", fmt(m.crashes_24h)],
    ["OS errors 24h", fmt(m.os_errors_24h)], ["Last patch", fmt(m.patch_age_days, " days ago")],
    ["Latency", fmt(m.network_latency_ms, " ms")], ["Boot", fmt(m.boot_seconds, " s")],
    ["Session RTT", fmt(m.session_latency_ms, " ms")], ["Logon", fmt(m.logon_seconds, " s")],
    ["Session host", fmt(m.session_host)], ["Protocol", fmt(m.protocol)],
  ].filter(([, v]) => !v.startsWith("—"));
  $("#drawer-body").innerHTML = `
    <div class="d-head"><span class="emoji">${ICON[d.kind]}</span>
      <div><h2>${esc(d.hostname)}</h2><div class="muted"><span class="dot ${d.online ? "on" : ""}"></span>
      ${esc(d.platform)} ${esc(d.os_version)} · ${esc(d.model)} · ${esc(d.user || "—")}${d.department ? ` · ${esc(d.department)}` : ""}</div></div></div>
    <h3>Experience score ${fmt(d.dex)}</h3>
    <div class="scores">${["performance", "stability", "responsiveness", "sentiment"].map((k, i) =>
      `<div class="score" style="animation-delay:${i * 70}ms"><b style="color:${color(s[k])}">${fmt(s[k])}</b><small>${k}</small></div>`).join("")}</div>
    <h3>Trend</h3>${spark(d.history)}
    <h3>Vitals: device, OS${d.kind === "vdi" ? ", session" : ""}</h3>
    <div class="kv">${vitals.map(([k, v]) => `<span>${k}</span><b>${v}</b>`).join("")}</div>
    <h3>Applications</h3>${d.apps.length ? `<table class="tbl"><tr><th>App</th><th>Ver</th><th>CPU</th><th>Mem</th><th>Crashes</th><th>Resp.</th></tr>
      ${d.apps.map((a, i) => `<tr style="animation-delay:${i * 40}ms"><td>${appIcon(a.app)} ${esc(a.app)}</td><td>${esc(a.version)}</td>
      <td>${fmt(a.cpu, "%")}</td><td>${fmt(a.mem_mb, "MB")}</td><td class="${a.crashes >= 3 ? "bad-txt" : ""}">${fmt(a.crashes)}</td>
      <td class="${a.latency_ms >= 1500 ? "bad-txt" : ""}">${fmt(a.latency_ms, "ms")}</td></tr>`).join("")}</table>` : `<p class="muted">No app data</p>`}
    <h3>Issues</h3><div class="list">${d.issues.map((i) =>
      `<div class="item"><div><b>${esc(i.title)}</b><div class="muted">${esc(i.detail)} · ${ago(i.opened_at)}</div></div><span class="s ${esc(i.status)}">${esc(i.status)}</span></div>`).join("") || `<p class="muted">No issues 🎉</p>`}</div>
    <h3>Actions</h3><div class="list">${d.actions.map((a) =>
      `<div class="item"><div><b>${esc(a.action)}${a.target ? ` · ${esc(a.target)}` : ""}</b> <span class="risk ${esc(a.risk)}">${esc(a.risk)}</span>
      <div class="muted">${esc((a.result || "").slice(0, 140))}</div></div><span class="s ${esc(a.status)}">${esc(a.status.replace("_", " "))}</span></div>`).join("") || `<p class="muted">No actions yet</p>`}</div>
    <h3>Guidance delivered</h3><div class="list">${d.guides.map((g) =>
      `<div class="item"><div>${esc(g.icon)} <b>${esc(g.title)}</b><div class="muted">${esc(g.source)} · ${ago(g.ts)}</div></div><span class="s ${g.status === "completed" ? "done" : "sent"}">${esc(g.status)}</span></div>`).join("") || `<p class="muted">None yet</p>`}</div>
    <h3>User feedback</h3><div class="list">${d.surveys.map((v) =>
      `<div class="item"><div>${"★".repeat(v.rating)}${"☆".repeat(5 - v.rating)} ${esc(v.comment)}</div><span class="muted">${ago(v.ts)}</span></div>`).join("") || `<p class="muted">No ratings yet</p>`}</div>
    <div class="row-btns">
      <button class="btn ghost" id="d-ask">⭐ Ask for feedback</button>
      <button class="btn ghost" id="d-msg">💬 Message user</button>
      <select id="d-guide" class="btn ghost"><option value="">🧭 Send a guide…</option>${guideCache.map((g) => `<option value="${g.id}">${esc(g.icon)} ${esc(g.title)}</option>`).join("")}</select>
      <button class="btn ghost" id="d-ai">✨ Ask Copilot about this device</button>
    </div>`;
  $("#d-ask").onclick = async () => {
    const r = await post(`/api/devices/${id}/survey`);
    toast(r.sent ? "📨 Survey sent to the user" : "⏳ Notification limit reached for this hour");
  };
  $("#d-msg").onclick = async () => {
    const text = prompt(`Message to ${d.user || d.hostname}:`);
    if (!text) return;
    const r = await post(`/api/devices/${id}/conversations`, { subject: `IT check-in: ${d.hostname}`, text });
    toast("💬 Message sent");
    closeDrawer(); location.hash = "collab"; setTimeout(() => openThread(r.id), 300);
  };
  $("#d-guide").onchange = async (e) => {
    if (!e.target.value) return;
    const r = await post(`/api/guides/${e.target.value}/push`, { device_id: id });
    toast(r.sent ? "🧭 Guide sent" : "Already sent today");
    e.target.value = "";
  };
  $("#d-ai").onclick = () => askCopilot(`Why does ${d.hostname} have DEX ${fmt(d.dex)}, and what should I do?`);
  if (!keepOpen) openPanel();
}
function closeDrawer() {
  state.openId = null; state.openApp = null;
  $("#drawer").classList.remove("open");
  $("#scrim").classList.remove("open");
}
$("#close").onclick = closeDrawer;
$("#scrim").onclick = closeDrawer;
document.addEventListener("keydown", (e) => e.key === "Escape" && (closeDrawer(), $("#copilot").classList.remove("open")));
document.addEventListener("click", (e) => {
  const dev = e.target.closest("[data-dev]");
  if (dev) openDrawer(dev.dataset.dev);
  const ask = e.target.closest("[data-ask]");
  if (ask) askCopilot(`Explain this alert and what I should do: ${ask.dataset.ask}`);
});

// ---------- applications ----------
async function loadApps() {
  const apps = await api("/api/apps");
  const box = $("#apps");
  if (!apps.length) { box.innerHTML = `<p class="muted">No application data yet</p>`; return; }
  const seen = new Set();
  apps.forEach((a, i) => {
    seen.add(a.app);
    let el = box.querySelector(`[data-app="${CSS.escape(a.app)}"]`);
    if (!el) {
      el = document.createElement("div");
      el.className = "card dev app-card";
      el.dataset.app = a.app;
      el.style.animationDelay = `${i * 50}ms`;
      el.innerHTML = `<div class="head"><div class="emoji">${appIcon(a.app)}</div><div style="min-width:0"><div class="name">${esc(a.app)}</div>
        <div class="meta sub"></div></div>${ringSvg(`app-${a.app}`)}</div><div class="stats"></div><div class="versions"></div>`;
      el.onclick = () => openApp(a.app);
      box.appendChild(el);
    }
    $(".sub", el).textContent = `${a.devices} device${a.devices > 1 ? "s" : ""} · ${a.versions.length} version${a.versions.length > 1 ? "s" : ""}`;
    setRing($(".mini .bar", el), a.score);
    countUp($(".mini span", el), a.score, 0);
    $(".stats", el).innerHTML = `<div class="stat"><b class="${a.crashes ? "bad-txt" : ""}">${a.crashes}</b><small>crashes</small></div>
      <div class="stat"><b>${a.avg_latency_ms}<small>ms</small></b><small>response</small></div>
      <div class="stat"><b>${a.avg_cpu}<small>%</small></b><small>CPU</small></div>`;
    $(".versions", el).innerHTML = a.versions.map((v) => `<span class="tag">v${esc(v)}</span>`).join("");
    el.classList.toggle("alert", a.score < 60);
    el.style.order = i;
  });
  $$(".app-card", box).forEach((el) => { if (!seen.has(el.dataset.app)) el.remove(); });
}
async function openApp(name, keepOpen = false) {
  state.openApp = name; state.openId = null;
  const a = await api(`/api/apps/${encodeURIComponent(name)}`);
  const t = a.trend;
  let trend = `<p class="muted">Collecting history…</p>`;
  if (t.length > 1) {
    const W = 500, H = 120, max = Math.max(...t.map((p) => p.latency || 0), 1);
    const pts = t.map((p, i) => `${((i / (t.length - 1)) * W).toFixed(1)},${(H - 6 - ((p.latency || 0) / max) * (H - 12)).toFixed(1)}`);
    trend = `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><path class="a" d="M${pts.join("L")}L${W},${H}L0,${H}Z" fill="var(--accent-2)"/>
      <path class="l" d="M${pts.join("L")}" stroke="var(--accent-2)"/></svg><div class="legend"><span><i style="background:var(--accent-2)"></i>Avg response time (peak ${Math.round(max)} ms)</span></div>`;
  }
  $("#drawer-body").innerHTML = `
    <div class="d-head"><span class="emoji">${appIcon(name)}</span><div><h2>${esc(name)}</h2>
      <div class="muted">${a.devices.length} devices · ${a.versions.length} versions</div></div></div>
    <h3>Response time, last hour</h3>${trend}
    <h3>By version</h3><table class="tbl"><tr><th>Version</th><th>Devices</th><th>Crashes</th><th>Avg resp.</th></tr>
      ${a.versions.map((v) => `<tr><td>v${esc(v.version)}</td><td>${v.devices}</td><td class="${v.crashes >= 3 ? "bad-txt" : ""}">${v.crashes}</td><td>${v.avg_latency_ms} ms</td></tr>`).join("")}</table>
    <h3>Devices</h3><table class="tbl"><tr><th>Device</th><th>Ver</th><th>CPU</th><th>Mem</th><th>Crashes</th><th>Resp.</th></tr>
      ${a.devices.map((d, i) => `<tr style="animation-delay:${i * 30}ms;cursor:pointer" data-dev="${esc(d.device_id)}"><td>${ICON[d.kind]} ${esc(d.hostname)}</td><td>${esc(d.version)}</td>
      <td>${fmt(d.cpu, "%")}</td><td>${fmt(d.mem_mb, "MB")}</td><td class="${d.crashes >= 3 ? "bad-txt" : ""}">${fmt(d.crashes)}</td>
      <td class="${d.latency_ms >= 1500 ? "bad-txt" : ""}">${fmt(d.latency_ms, "ms")}</td></tr>`).join("")}</table>
    <div class="row-btns"><button class="btn ghost" id="a-ai">✨ Ask Copilot about ${esc(name)}</button></div>`;
  $("#a-ai").onclick = () => askCopilot(`How is ${name} performing across the fleet, and what should I do?`);
  if (!keepOpen) openPanel();
}

// ---------- alerts ----------
async function loadAlerts() {
  const list = await api("/api/alerts");
  const box = $("#alerts");
  box.innerHTML = list.map((a) => alertHtml(a, true)).join("") ||
    `<div class="card panel"><p class="muted">No active alerts. The AI keeps watching every device, app and session. 👀</p></div>`;
  $$("[data-op]", box).forEach((b) => b.onclick = async () => {
    const card = b.closest("[data-id]");
    card.classList.add("gone");
    await post(`/api/alerts/${card.dataset.id}/${b.dataset.op}`);
    refresh();
  });
}

// ---------- predictions ----------
async function loadPredict() {
  const list = await api("/api/predictions");
  const box = $("#predict");
  box.innerHTML = list.map((p) => predHtml(p, true)).join("") || `<p class="muted">No risks forecast right now. 🌤️</p>`;
  requestAnimationFrame(() => $$("b[data-w]", box).forEach((b) => (b.style.width = `${b.dataset.w}%`)));
}

// ---------- conversations ----------
async function loadThreads() {
  const list = await api("/api/conversations");
  $("#threads").innerHTML = list.map((c) => `
    <div class="th ${c.status} ${state.thread === c.id ? "active" : ""}" data-cid="${c.id}">
      <div class="s1"><span>${ICON[c.kind]} ${esc(c.subject)}</span>${c.unread_it ? `<span class="unread">${c.unread_it}</span>` : ""}</div>
      <div class="s2">${esc(c.hostname)} · ${esc(c.user || "")} · ${ago(c.updated_at)}</div>
      <div class="s2">${esc(c.last || "")}</div></div>`).join("") || `<p class="muted center">No conversations yet</p>`;
  $$(".th").forEach((t) => (t.onclick = () => openThread(+t.dataset.cid)));
  if (state.thread) openThread(state.thread, true);
}
const bubble = (m) => `<div class="bubble ${m.sender}">${esc(m.text)}<small>${{ user: "Employee", it: "IT", ai: "✨ DWIP AI" }[m.sender]} · ${ago(m.ts)}</small></div>`;
async function openThread(id, quiet = false) {
  state.thread = id;
  const c = await api(`/api/conversations/${id}`);
  const box = $("#thread");
  const known = quiet ? $$(".bubble", box).length : 0;
  if (!quiet || !$(".msgs", box)) {
    box.innerHTML = `<header><div><b>${esc(c.subject)}</b><div class="muted small">${ICON[c.kind]} ${esc(c.hostname)} · ${esc(c.user || "")} · ${esc(c.status)}</div></div>
      <div class="btns"><button class="btn ghost" data-dev="${esc(c.device_id)}">Device</button>
      ${c.status === "open" ? `<button class="btn go" id="t-close">✔ Close</button>` : ""}</div></header>
      <div class="msgs"></div>
      <form class="reply"><input placeholder="Reply to ${esc(c.user || "employee")}…" required><button class="btn go">Send</button></form>`;
    $(".reply", box).onsubmit = async (e) => {
      e.preventDefault();
      const inp = $("input", e.target);
      const text = inp.value.trim();
      if (!text) return;
      inp.value = "";
      await post(`/api/conversations/${id}/messages`, { text });
    };
    const close = $("#t-close");
    if (close) close.onclick = async () => { await post(`/api/conversations/${id}/close`); loadThreads(); openThread(id); };
  }
  const msgs = $(".msgs", box);
  if (!quiet) msgs.innerHTML = c.messages.map(bubble).join("");
  else c.messages.slice(known).forEach((m) => msgs.insertAdjacentHTML("beforeend", bubble(m)));
  msgs.scrollTop = msgs.scrollHeight;
  $$(".th").forEach((t) => t.classList.toggle("active", +t.dataset.cid === id));
}

// ---------- guidance ----------
async function loadGuides() {
  const list = guideCache = await api("/api/guides");
  const box = $("#guides");
  box.innerHTML = list.map((g, i) => `
    <div class="card dev guide" style="animation-delay:${i * 50}ms">
      <div class="head"><span class="gi">${esc(g.icon)}</span><div style="min-width:0"><div class="name">${esc(g.title)}</div>
      <div class="meta">${esc(g.summary)}</div></div></div>
      <ol>${g.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>
      <div>${g.trigger_issue ? `<span class="tag ai">⚡ auto: ${esc(g.trigger_issue)}</span>` : `<span class="tag">manual</span>`}
        ${g.target_kind ? `<span class="tag">${ICON[g.target_kind]} ${esc(g.target_kind)} only</span>` : ""}</div>
      <div class="gfoot"><span class="muted small">Sent ${g.sent} · completed ${g.completed}</span>
        <span><select data-g="${g.id}"><option value="">Push to…</option><option value="all">Everyone</option>
        ${Object.keys(KIND_LABEL).map((k) => `<option value="${k}">${KIND_LABEL[k]}</option>`).join("")}</select></span></div>
    </div>`).join("");
  $$("select[data-g]", box).forEach((s) => (s.onchange = async () => {
    if (!s.value) return;
    const r = await post(`/api/guides/${s.dataset.g}/push`, s.value === "all" ? {} : { kind: s.value });
    toast(`🧭 Guide sent to ${r.sent} devices`);
    s.value = "";
    loadGuides();
  }));
}
$("#guide-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  const steps = f.get("steps").split("\n").map((s) => s.trim()).filter(Boolean);
  await post("/api/guides", { title: f.get("title"), summary: f.get("summary"), icon: f.get("icon") || "💡",
    steps, trigger_issue: f.get("trigger_issue") || null });
  e.target.reset();
  toast("🧭 Guide created");
  loadGuides();
};

// ---------- engagement ----------
async function loadEngagement() {
  const [e, camps] = await Promise.all([api("/api/engagement"), api("/api/campaigns")]);
  countUp($("#eng-score"), e.score);
  countUp($("#eng-rate"), e.response_rate);
  countUp($("#eng-resp"), e.responses);
  countUp($("#eng-guide"), e.guide_completion);
  hbars($("#eng-dept"), e.departments.map((d) => ({ label: d.department, pct: d.rating * 20, value: `${d.rating}★` })));
  hbars($("#eng-kind"), e.kinds.map((d) => ({ label: `${ICON[d.kind]} ${KIND_LABEL[d.kind]}`, pct: d.rating * 20, value: `${d.rating}★` })));
  $("#campaigns").innerHTML = camps.map((c) => `
    <div class="insight"><div class="t">📣 ${esc(c.question)}</div>
      <div class="ai-text">${c.sent} sent · ${c.responses} answered${c.response_rate != null ? ` (${c.response_rate}%)` : ""}${c.rating ? ` · avg ${c.rating}★` : ""} · ${ago(c.created_at)}</div>
      <div class="meter" style="margin-top:8px"><b data-w="${c.response_rate || 0}"></b></div></div>`).join("") || `<p class="muted">No campaigns yet</p>`;
  requestAnimationFrame(() => $$("#campaigns b[data-w]").forEach((b) => (b.style.width = `${b.dataset.w}%`)));
  $("#eng-comments").innerHTML = e.comments.map((c) => `
    <div class="insight"><div class="t">${"★".repeat(c.rating)}${"☆".repeat(5 - c.rating)} <span class="muted small">${esc(c.hostname)} · ${ago(c.ts)}</span></div>
    <div class="ai-text">“${esc(c.comment)}”</div></div>`).join("") || `<p class="muted">No comments yet</p>`;
}
$("#camp-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  const r = await post("/api/campaigns", { question: f.get("question"), target_kind: f.get("target_kind") || null });
  e.target.reset();
  toast(`📣 Pulse sent to ${r.sent} devices`);
  loadEngagement();
};

// ---------- AI copilot ----------
const cp = $("#copilot");
$("#orb").onclick = () => { cp.classList.toggle("open"); if (cp.classList.contains("open")) $("#cp-q").focus(); };
$("#cp-close").onclick = () => cp.classList.remove("open");
$$("#cp-chips button").forEach((b) => (b.onclick = () => askCopilot(b.textContent)));
$("#cp-form").onsubmit = (e) => {
  e.preventDefault();
  const q = $("#cp-q").value.trim();
  if (q) askCopilot(q);
  $("#cp-q").value = "";
};
async function askCopilot(q) {
  cp.classList.add("open");
  const body = $("#cp-body");
  body.insertAdjacentHTML("beforeend", `<div class="bubble me">${esc(q)}</div>`);
  const typing = document.createElement("div");
  typing.className = "bubble ai typing";
  typing.innerHTML = "<i></i><i></i><i></i>";
  body.appendChild(typing);
  body.scrollTop = body.scrollHeight;
  try {
    const r = await post("/api/assistant/chat", { question: q, history: state.cpHistory });
    typing.remove();
    state.cpHistory.push({ role: "user", text: q }, { role: "assistant", text: r.answer });
    state.cpHistory = state.cpHistory.slice(-8);
    const el = document.createElement("div");
    el.className = "bubble ai";
    body.appendChild(el);
    typewrite(el, r.answer, r.source === "llm" ? `✨ ${r.model}` : "rules engine");
  } catch (err) {
    typing.remove();
    body.insertAdjacentHTML("beforeend", `<div class="bubble ai">Sorry, I couldn't reach the server.</div>`);
  }
}
function typewrite(el, text, src) {
  const body = $("#cp-body");
  let i = 0;
  const step = Math.max(2, Math.ceil(text.length / 120));
  const tick = () => {
    i = Math.min(text.length, i + step);
    el.textContent = text.slice(0, i);
    body.scrollTop = body.scrollHeight;
    if (i < text.length) requestAnimationFrame(tick);
    else el.insertAdjacentHTML("beforeend", `<small>${esc(src)}</small>`);
  };
  tick();
}
async function aiStatus() {
  const s = await api("/api/assistant/status");
  $("#ai-status").textContent = s.llm ? `AI: ✨ ${s.model} (local)` : "AI: rules engine (LLM offline)";
  $("#cp-model").textContent = s.llm ? `Powered by ${s.model}, running locally` : "Rules engine (start Ollama for LLM answers)";
}

// ---------- live updates ----------
// throttled: with many devices reporting, a debounce would never fire
let pending = null, drawerDirty = false;
function refresh(force = false) {
  if (force) drawerDirty = true;
  if (pending) return;
  pending = setTimeout(() => {
    pending = null;
    loadSummary();
    LOADERS[state.view]();
    if (drawerDirty && state.openId) openDrawer(state.openId, true);
    if (drawerDirty && state.openApp) openApp(state.openApp, true);
    drawerDirty = false;
  }, 800);
}
function connect() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws?token=${encodeURIComponent(authToken())}`);
  ws.onopen = () => { $(".live").classList.add("on"); $("#live-text").textContent = "Live"; };
  ws.onclose = () => {
    $(".live").classList.remove("on");
    $("#live-text").textContent = "Reconnecting…";
    setTimeout(connect, 2000);
  };
  ws.onmessage = (msg) => {
    const m = JSON.parse(msg.data);
    const devId = m.device_id || (m.event && m.event.device_id);
    if (state.openId && devId === state.openId && m.type === "event") drawerDirty = true;
    if (m.type === "event") {
      const e = m.event, feed = $("#feed");
      feed.prepend(feedItem(e));
      while (feed.children.length > 40) feed.lastChild.remove();
      lightStep(e.kind);
      if (["alert", "executed", "conversation", "enroll"].includes(e.kind)) toast(`${FEED_ICON[e.kind]} ${esc(e.message)}`);
    } else if (m.type === "telemetry") {
      lightStep("telemetry");
    } else if (m.type === "message" && state.view === "collab") {
      loadThreads();
      return;
    }
    if (m.type === "telemetry" && !["overview", "devices", "apps"].includes(state.view) && !state.openId) return;
    refresh();
  };
}
setInterval(() => $$(".when").forEach((w) => (w.textContent = ago(+w.dataset.ts))), 10000);
setInterval(() => refresh(true), 20000); // catches devices going offline; refreshes open drawers

// start once every script (including intel.js views) has loaded
document.addEventListener("DOMContentLoaded", () => {
  show(location.hash.slice(1) || "overview");
  loadFeed();
  aiStatus();
  setInterval(aiStatus, 60000);
  connect();
});
