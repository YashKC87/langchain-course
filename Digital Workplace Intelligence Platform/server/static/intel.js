// DWIP Release 1 views: DEX, RCA, remediation, AI Assist, integrations, reports, governance.
// Uses helpers from app.js ($, api, post, esc, ago, color, countUp, setRing, hbars, toast, openDrawer...).

// ---------- global filters ----------
const filt = { location: "", department: "", kind: "", data: "", period: "1h" };
try { Object.assign(filt, JSON.parse(localStorage.getItem("dwip-filters") || "{}")); } catch { /* per-viewer convenience only */ }
function filterQs(keys = ["location", "department", "kind", "data"], extra = {}) {
  const p = new URLSearchParams();
  keys.forEach((k) => filt[k] && p.set(k, filt[k]));
  Object.entries(extra).forEach(([k, v]) => p.set(k, v));
  const s = p.toString();
  return s ? `?${s}` : "";
}
async function loadFilterOptions() {
  const o = await api("/api/filters");
  for (const k of ["location", "department"]) {
    const sel = $(`#filters [name=${k}]`), first = sel.options[0].outerHTML;
    sel.innerHTML = first + (o[k] || []).map((v) => `<option>${esc(v)}</option>`).join("");
  }
  for (const [k, v] of Object.entries(filt)) $(`#filters [name=${k}]`).value = v;
}
$("#filters").addEventListener("change", (e) => {
  filt[e.target.name] = e.target.value;
  try { localStorage.setItem("dwip-filters", JSON.stringify(filt)); } catch { /* ignore */ }
  LOADERS[state.view]();
});
function freshness(sec) {
  const el = $("#freshness");
  if (sec == null) { el.textContent = "No data yet"; el.className = "fresh stale"; return; }
  el.textContent = `Data ${sec < 60 ? `${sec}s` : `${Math.round(sec / 60)}m`} old`;
  el.className = `fresh ${sec > 120 ? "stale" : "ok"}`;
}
const fresh = (s) => s == null ? "" : `<span class="age">${s < 90 ? "🟢" : "🟠"} ${s < 60 ? `${s}s` : `${Math.round(s / 60)}m`} old</span>`;
const empty = (msg) => `<p class="muted">${msg}</p>`;
const LBL = { fact: "Observed fact", prediction: "Prediction", correlation: "Correlation", hypothesis: "Hypothesis" };

// ---------- sign-in (only when the server requires tokens) ----------
function showSignin() {
  const f = $("#signin");
  if (!f.hidden) return;
  f.hidden = false;
  $("#signin-token").focus();
}
$("#signin").addEventListener("submit", (e) => {
  e.preventDefault();
  try { localStorage.setItem("dwip-token", $("#signin-token").value.trim()); } catch { /* ignore */ }
  location.reload();
});
async function loadMe() {
  const me = await api("/api/me");
  if (!me || !me.role) return;
  $("#who").textContent = me.auth === "dev" ? "👤 local dev (admin)" : `👤 ${me.name} · ${me.role}`;
  document.body.dataset.role = me.role;
}

// ---------- incidents (shared by DEX + RCA) ----------
const impactColor = (v) => v >= 60 ? "var(--bad)" : v >= 35 ? "var(--warn)" : "var(--good)";
const incHtml = (i, full) => `
  <div class="${full ? "card inc" : "insight"}" data-inc="${esc(i.id)}">
    <div class="t"><span class="impact" style="--c:${impactColor(i.impact)}">${i.impact}</span> ${esc(i.title)}
      <span class="tag ${esc(i.severity)}">${esc(i.severity)}</span>
      <span class="tag">👥 ${i.employees} employee${i.employees === 1 ? "" : "s"}</span>
      <span class="tag">${i.devices} device${i.devices === 1 ? "" : "s"}</span>
      ${i.data !== "live" ? `<span class="tag demo">${i.data === "demo" ? "DEMO" : "MIXED"}</span>` : ""}
      ${full ? fresh(i.freshness_s) : ""}</div>
    <div class="ai-text">${Object.entries(i.locations).map(([k, v]) => `📍${esc(k)} ${v}`).join(" · ")}
      ${i.app && Object.keys(i.versions).length ? ` · versions ${Object.entries(i.versions).map(([k, v]) => `${esc(k)}×${v}`).join(", ")}` : ""}</div>
    ${full ? `
      <div class="evidence">
        ${i.facts.slice(0, 4).map((f) => `<div class="ev fact"><b>${LBL.fact}</b> ${esc(f.text)} <i>${esc(f.source)}</i></div>`).join("")}
        ${i.correlated.map((c) => `<div class="ev correlation"><b>${LBL.correlation}</b> ${c.devices} of ${i.devices} devices also have “${esc(c.type)}” (co-occurrence, not proof)</div>`).join("")}
        ${i.hypothesis ? `<div class="ev hypothesis"><b>${esc(i.hypothesis.label)}</b> ${esc(i.hypothesis.text)}</div>`
          : `<div class="ev hypothesis"><b>Hypothesis</b> None yet: no fleet-level explanation has been generated for this incident.</div>`}
      </div>
      <div class="inc-foot"><span class="status">⏳ ${esc(i.status)}</span>
        <button class="btn ghost" data-why>Why this score?</button>
        <button class="btn ghost" data-assist="${esc(`Investigate ${i.title}`)}">✨ Investigate</button></div>` : ""}
  </div>`;
function bindIncidents(box) {
  $$("[data-inc]", box).forEach((el) => {
    el.style.cursor = "pointer";
    el.onclick = (e) => {
      const a = e.target.closest("[data-assist]");
      if (a) { e.stopPropagation(); return askAssist(a.dataset.assist); }
      openIncident(el.dataset.inc);
    };
  });
}
async function openIncident(id) {
  const i = await api(`/api/incidents/${encodeURIComponent(id)}${filterQs()}`);
  if (!i || !i.id) return toast("That incident has just cleared ✅");
  state.openId = null; state.openApp = null;
  $("#drawer-body").innerHTML = `
    <h2 class="d-title"><span class="impact big" style="--c:${impactColor(i.impact)}">${i.impact}</span> ${esc(i.title)}</h2>
    <p class="muted">${i.employees} of ${i.total_employees} employees · ${i.devices} devices · first seen ${ago(i.first_seen)} · ${fresh(i.freshness_s)}</p>
    <h3>⚖️ Employee Impact Score breakdown</h3>
    <div class="table"><table><tr><th>Factor</th><th>Weight</th><th>Value</th><th>Points</th><th>Why</th></tr>
      ${i.breakdown.map((b) => `<tr><td>${esc(b.factor)}</td><td>${b.weight}</td><td>${b.value}</td><td><b>${b.points}</b></td><td class="muted">${esc(b.why)}</td></tr>`).join("")}
    </table></div>
    <p class="muted small">Weights are set by an admin in Governance and Audit.</p>
    <h3>🧪 Evidence</h3>
    <div class="evidence">${i.facts.map((f) => `<div class="ev fact"><b>${LBL.fact}</b> ${esc(f.text)} <i>${esc(f.source)}</i></div>`).join("")}
      ${i.predictions.map((p) => `<div class="ev prediction"><b>${LBL.prediction}</b> ${esc(p.hostname)}: ${esc(p.title)} ${esc(p.eta)} (confidence ${p.confidence}%, ${esc(p.model || "")})</div>`).join("")}
      ${i.hypothesis ? `<div class="ev hypothesis"><b>${esc(i.hypothesis.label)}</b> ${esc(i.hypothesis.text)}</div>` : ""}</div>
    <h3>📊 Spread</h3>
    <div class="ai-text">By OS: ${Object.entries(i.os_versions).map(([k, v]) => `${esc(k)} ×${v}`).join(", ")}<br>
      By department: ${Object.entries(i.departments).map(([k, v]) => `${esc(k)} ×${v}`).join(", ")}</div>
    <h3>💻 Affected devices</h3>
    <div class="stack">${i.device_list.map((d) => `<div class="insight" data-dev="${esc(d.id)}" style="cursor:pointer">
      <div class="t">${ICON[d.kind] || ""} ${esc(d.hostname)} ${d.demo ? '<span class="tag demo">DEMO</span>' : ""}
      <span class="tag" style="color:${color(d.dex)}">DEX ${d.dex ?? "–"}</span></div>
      <div class="ai-text">${esc(d.user || "")} · ${esc(d.location || "Unassigned")} · ${esc(d.department || "")}</div></div>`).join("")}</div>`;
  $$("[data-dev]", $("#drawer-body")).forEach((el) => el.onclick = () => openDrawer(el.dataset.dev));
  openPanel();
}

// ---------- DEX ----------
function trendSvg(points) {
  if (points.length < 2) return empty("Collecting history for this period…");
  const W = 500, H = 140, vals = points.map((p) => p.dex);
  const lo = Math.max(0, Math.min(...vals) - 5), hi = Math.min(100, Math.max(...vals) + 5);
  const x = (i) => (i / (points.length - 1)) * W, y = (v) => H - 8 - ((v - lo) / (hi - lo || 1)) * (H - 16);
  const line = `M${points.map((p, i) => `${x(i).toFixed(1)},${y(p.dex).toFixed(1)}`).join("L")}`;
  const t = (ts) => new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
    <path class="a" d="${line}L${W},${H}L0,${H}Z" fill="var(--accent)"/><path class="l" d="${line}" stroke="var(--accent)"/></svg>
    <div class="legend"><span>${t(points[0].t)}</span><span>DEX ${lo.toFixed(0)}–${hi.toFixed(0)}</span><span>${t(points[points.length - 1].t)}</span></div>`;
}
async function loadDex() {
  const d = await api(`/api/dex${filterQs(undefined, { period: filt.period })}`);
  freshness(d.freshness_s);
  countUp($("#dx-dex"), d.dex, 0);
  $("#dx-sub").textContent = `${d.devices} devices · ${d.online} online${d.demo_devices ? ` · ${d.demo_devices} demo` : ""}`;
  [["#dx-emp", d.impacted_employees], ["#dx-crit", d.critical_issues], ["#dx-alerts", d.proactive_alerts],
    ["#dx-pred", d.predicted_risks]].forEach(([s, v]) => countUp($(s), v, 0));
  $("#dx-trend").innerHTML = trendSvg(d.trend);
  const top = $("#dx-top");
  top.innerHTML = d.top_problems.map((i) => incHtml(i, false)).join("") || empty("No open experience problems in this scope. 🎉");
  bindIncidents(top);
  const locs = [...new Set(d.heatmap.map((c) => c.location))], kinds = [...new Set(d.heatmap.map((c) => c.kind))];
  $("#dx-heat").innerHTML = d.heatmap.length ? `<table><tr><th></th>${kinds.map((k) => `<th>${ICON[k] || ""} ${esc(KIND_LABEL[k] || k)}</th>`).join("")}</tr>
    ${locs.map((l) => `<tr><th>${esc(l)}</th>${kinds.map((k) => {
      const c = d.heatmap.find((x) => x.location === l && x.kind === k);
      return c ? `<td class="cell" data-loc="${esc(l)}" data-kind="${esc(k)}" style="--c:${color(c.dex)}"><b>${c.dex ?? "–"}</b><small>${c.devices} dev</small></td>` : "<td></td>";
    }).join("")}</tr>`).join("")}</table>` : empty("No devices in this scope.");
  $$("#dx-heat .cell").forEach((c) => c.onclick = () => {
    filt.location = c.dataset.loc; $("#filters [name=location]").value = c.dataset.loc;
    state.kind = c.dataset.kind; location.hash = "devices";
    setTimeout(() => $(`.tab[data-kind="${c.dataset.kind}"]`)?.click(), 50);
  });
  hbars($("#dx-apps"), d.apps.map((a) => ({ label: `${appIcon(a.app)} ${a.app}`, pct: a.score, value: `${a.score} · ${a.devices} dev` })));
}

// ---------- monitoring coverage ----------
const COV_LABEL = { live: "Live", demo_only: "Demo only", not_collected: "Not collected" };
async function loadCoverage() {
  const list = await api("/api/monitoring/coverage");
  const domains = [...new Set(list.map((c) => c.domain))];
  $("#coverage").innerHTML = domains.map((d) => `<h4>${esc(d)}</h4>${list.filter((c) => c.domain === d).map((c) => `
    <div class="cov ${c.status}"><span class="pill">${COV_LABEL[c.status]}</span><span>${esc(c.signal)}</span>
      <small class="muted">${c.status === "not_collected" ? `Needs: ${esc(c.requires)}` : `${c.real_devices} real · ${c.demo_devices} demo`}</small></div>`).join("")}`).join("");
}

// ---------- RCA ----------
async function loadRca() {
  const list = await api(`/api/incidents${filterQs()}`);
  const box = $("#rca");
  box.innerHTML = list.map((i) => incHtml(i, true)).join("") ||
    `<div class="card panel">${empty("No open incidents in this scope. The engine re-checks every report.")}</div>`;
  bindIncidents(box);
}

// ---------- remediation ----------
async function loadRemediation() {
  await loadApprovals();
  const r = await api("/api/remediation");
  [["#rm-exec", r.stats.executed], ["#rm-ver", r.stats.verified], ["#rm-rate", r.stats.success_rate], ["#rm-fail", r.stats.failed]]
    .forEach(([s, v]) => countUp($(s), v, 0));
  $("#approvals2").innerHTML ||= empty("Nothing waiting. 🎉");
  $("#rm-recent").innerHTML = r.recent.length ? `<table><tr><th>Device</th><th>Action</th><th>Mode</th><th>Status</th><th>Verification</th><th></th></tr>
    ${r.recent.map((a) => `<tr><td>${esc(a.hostname)} ${a.demo ? '<span class="tag demo">DEMO</span>' : ""}</td>
      <td>${esc(a.action)}${a.target ? ` (${esc(a.target)})` : ""}<div class="muted small">${esc(a.title || "")}</div></td>
      <td class="muted">${esc(a.mode)}</td><td><span class="tag ${a.status === "done" ? "low" : a.status === "failed" ? "high" : ""}">${esc(a.status)}</span></td>
      <td class="muted">${esc(a.verification)}</td><td class="muted small">${ago(a.updated_at)}</td></tr>`).join("")}</table>` : empty("No actions yet.");
  $("#rm-catalog").innerHTML = r.catalog.map((c) => `<div class="insight"><div class="t">${esc(c.action)}
    <span class="tag ${c.risk === "low" ? "low" : c.risk === "high" ? "high" : "medium"}">${esc(c.risk)} risk</span></div>
    <div class="ai-text">${esc(c.mode)} · ${esc(c.effect)}</div></div>`).join("") +
    `<div class="insight"><div class="t">🔒 Safety policy</div><div class="ai-text">${esc(r.policy.execution)}. ${esc(r.policy.approval)}. The AI cannot run actions.</div></div>`;
}

// ---------- AI Assist ----------
$("#as-form").addEventListener("submit", (e) => { e.preventDefault(); const q = $("#as-q").value.trim(); if (q) askAssist(q); });
$$("#as-chips button").forEach((b) => b.onclick = () => askAssist(b.textContent));
async function askAssist(q) {
  if (location.hash !== "#assist") location.hash = "assist";
  $("#as-q").value = q;
  const out = $("#as-out");
  out.innerHTML = `<div class="card panel"><div class="bubble ai typing"><i></i><i></i><i></i></div>
    <p class="muted small">Collecting evidence from rules, statistics and telemetry first. The local AI only runs if there is evidence to explain.</p></div>`;
  const filters = { location: filt.location, department: filt.department, kind: filt.kind, data: filt.data };
  const r = await post("/api/assist", { question: q, filters });
  if (!r || !r.question) { out.innerHTML = `<div class="card panel">${empty("Couldn't run the investigation.")}</div>`; return; }
  const sec = (title, items, kind) => items.length ? `<h3>${title}</h3><div class="evidence">${items.map((x) =>
    `<div class="ev ${kind}"><b>${esc(x.label || LBL[kind])}</b> ${esc(x.text)}${x.confidence != null ? ` <i>confidence ${x.confidence}% · ${esc(x.model)}</i>` : ""}${x.source ? ` <i>${esc(x.source)}</i>` : ""}${x.freshness_s != null ? ` ${fresh(x.freshness_s)}` : ""}</div>`).join("")}</div>` : "";
  out.innerHTML = `<div class="card panel assist-out">
    <div class="t-row"><h3>🔎 ${esc(r.question)}</h3>
      <span class="conf-pill ${r.confidence}">Confidence: ${r.confidence}</span></div>
    <p class="muted small">${esc(r.confidence_basis)} · scope: ${esc(r.scope.join(", ") || "selected filters / whole fleet")} ·
      ${r.source === "llm" ? `✨ explained by ${esc(r.model)} (local)` : "rules + statistics only (no LLM call)"} · ${r.latency_ms} ms</p>
    <p>${esc(r.summary)}</p>
    ${r.gaps.length ? `<h3>⚠️ Data gaps</h3><div class="evidence">${r.gaps.map((g) => `<div class="ev gap"><b>Not available</b> ${esc(g)}</div>`).join("")}</div>` : ""}
    ${sec("📌 Observed facts", r.facts, "fact")}
    ${sec("🔮 Statistical predictions", r.predictions, "prediction")}
    ${sec("🔗 Correlations", r.correlations, "correlation")}
    ${sec("💭 Hypotheses (not confirmed)", r.hypotheses, "hypothesis")}
    ${r.actions.length ? `<h3>🛠️ Approved actions (read-only suggestion)</h3><div class="evidence">${r.actions.map((a) =>
      `<div class="ev action"><b>${esc(a.action || "Advice only")}</b> for ${esc(a.for)} · ${esc(a.mode)} · ${a.devices} device(s) · ${esc(a.status || "")}</div>`).join("")}</div>
      <p class="muted small">To run a fix, approve it in Intelligent Remediation.</p>` : ""}
    ${r.incidents.length ? `<div class="btns">${r.incidents.map((id) => `<button class="btn ghost" data-inc-open="${esc(id)}">Open incident: ${esc(id)}</button>`).join("")}</div>` : ""}
  </div>`;
  $$("[data-inc-open]", out).forEach((b) => b.onclick = () => openIncident(b.dataset.incOpen));
}

// ---------- integrations ----------
const CON_STATUS = { connected: ["🟢", "Connected"], stale: ["🟠", "Stale"], no_data: ["⚪", "No data"],
  configured: ["🟡", "Configured (sign-in test only)"], not_configured: ["⚫", "Not configured"] };
async function loadConnectors() {
  const list = await api("/api/connectors");
  $("#connectors").innerHTML = list.map((c) => {
    const [ico, lbl] = CON_STATUS[c.status] || ["❔", c.status];
    return `<div class="card con ${c.status}"><div class="t"><b>${esc(c.name)}</b><span class="tag">${esc(c.domain)}</span></div>
      <div class="con-status">${ico} ${lbl}</div>
      <dl><dt>Auth</dt><dd>${esc(c.auth)}</dd><dt>Frequency</dt><dd>${esc(c.frequency)}</dd>
        <dt>Last sync</dt><dd>${c.last_sync ? ago(c.last_sync) : "—"}</dd>
        <dt>Freshness</dt><dd>${c.freshness_s != null ? `${c.freshness_s}s` : "—"}</dd>
        <dt>Ingested (1 h)</dt><dd>${c.volume_1h ?? "—"}</dd><dt>Rate limit</dt><dd>${c.rate_limit ?? "—"}</dd></dl>
      <div class="muted small">Capabilities: ${c.capabilities.map(esc).join(", ")}</div>
      ${c.missing_settings.length ? `<div class="muted small">Settings needed: <code>${c.missing_settings.map(esc).join("</code> <code>")}</code></div>` : ""}
      ${c.errors.length ? `<div class="err small">${c.errors.map(esc).join("<br>")}</div>` : ""}
      <p class="muted small">${esc(c.note)}</p>
      ${c.status === "configured" ? `<button class="btn ghost" data-test="${esc(c.id)}">Test sign-in</button>` : ""}</div>`;
  }).join("");
  $$("[data-test]").forEach((b) => b.onclick = async () => {
    b.disabled = true;
    const r = await post(`/api/connectors/${b.dataset.test}/test`);
    toast(`${r.ok ? "✅" : "❌"} ${esc(r.detail)}`);
    b.disabled = false;
  });
}

// ---------- reports ----------
$("#bm-dim").addEventListener("change", () => loadReports());
async function loadReports() {
  const [b, ins, ai] = await Promise.all([api(`/api/benchmarks${filterQs(undefined, { dimension: $("#bm-dim").value })}`),
    api(`/api/benchmarks/insights${filterQs()}`), api("/api/reports/ai")]);
  const d = (v) => v == null ? "—" : `<span style="color:${v < 0 ? "var(--bad)" : "var(--good)"}">${v > 0 ? "+" : ""}${v}</span>`;
  $("#bm-table").innerHTML = b.rows.length ? `<table><tr><th>${esc($("#bm-dim").selectedOptions[0].text)}</th><th>Devices</th><th>DEX</th>
    <th>vs enterprise (${b.enterprise_dex ?? "–"})</th><th>vs prev 7 days</th><th>Issues/dev</th><th>Crashes/dev</th></tr>
    ${b.rows.map((r) => `<tr><td>${esc(r.group)}</td><td>${r.devices}</td><td style="color:${color(r.dex)}"><b>${r.dex}</b></td>
      <td>${d(r.delta_vs_enterprise)}</td><td>${d(r.delta_vs_prev_7d)}</td><td>${r.issues_per_device}</td><td>${r.crashes_per_device}</td></tr>`).join("")}</table>` : empty("No devices in this scope.");
  $("#bm-note").textContent = [b.history_note, "Baselines are internal (your own fleet). No external benchmark data is used."].filter(Boolean).join(" ");
  $("#bm-insights").innerHTML = ins.map((i) => `<div class="ev fact"><b>${LBL.fact}</b> ${esc(i.text)}</div>`).join("") ||
    empty("No group differs noticeably from the enterprise baseline.");
  const tok = (v) => v == null ? "—" : v.toLocaleString();
  $("#ai-report").innerHTML = `<div class="kpis four mini-kpis">
      <div class="kpi"><span class="num">${ai.investigations}</span><span class="cap">AI Assist investigations (24 h)</span></div>
      <div class="kpi"><span class="num">${ai.resolved_without_llm_pct ?? "–"}${ai.resolved_without_llm_pct != null ? "%" : ""}</span><span class="cap">Answered without an LLM</span></div>
      <div class="kpi"><span class="num">${ai.alerts_llm_enriched}/${ai.alerts}</span><span class="cap">Alerts explained by the LLM</span></div>
      <div class="kpi"><span class="num">$${ai.local_model_cost.toFixed(2)}</span><span class="cap">AI cost</span></div></div>
    <p class="muted small">${esc(ai.cost_note)}</p>
    ${ai.calls.length ? `<div class="table"><table><tr><th>Purpose</th><th>Model</th><th>Calls</th><th>OK</th><th>Prompt tokens</th><th>Completion tokens</th><th>Avg latency</th></tr>
      ${ai.calls.map((c) => `<tr><td>${esc(c.purpose)}</td><td>${esc(c.model)}</td><td>${c.calls}</td><td>${c.ok}</td><td>${tok(c.prompt_tokens)}</td><td>${tok(c.completion_tokens)}</td><td>${c.avg_latency_ms} ms</td></tr>`).join("")}</table></div>`
      : empty("No LLM calls in the last 24 h.")}`;
}

// ---------- governance ----------
async function loadGovernance() {
  const [g, cfg, log] = await Promise.all([api("/api/governance"), api("/api/impact/config"), api("/api/audit?limit=80")]);
  $("#gov-warn").innerHTML = g.warnings.map((w) => `<div class="card warn-card">⚠️ ${esc(w)}</div>`).join("");
  $("#gov-roles").innerHTML = `<table><tr><th>Role</th><th>Can</th></tr>${g.roles.map((r) =>
    `<tr${r.role === g.you.role ? ' class="me"' : ""}><td><b>${esc(r.role)}</b></td><td class="muted">${esc(r.can)}</td></tr>`).join("")}</table>
    <p class="muted small">Signed in as <b>${esc(g.you.name)}</b> (${esc(g.you.role)}) · auth mode: ${g.auth === "dev" ? "local dev (no sign-in)" : "access tokens"}</p>`;
  const rd = g.retention_days;
  $("#gov-policy").innerHTML = `<dl class="kv"><dt>Raw telemetry kept</dt><dd>${rd.raw_telemetry} day</dd>
    <dt>Hourly rollups kept</dt><dd>${rd.hourly_rollups} days</dd><dt>Audit log kept</dt><dd>${rd.audit_log} days</dd>
    <dt>Local AI model</dt><dd>${esc(g.ai.local_model)} at ${esc(g.ai.endpoint)}${g.ai.enabled ? "" : " (off)"}</dd>
    <dt>External LLM</dt><dd>${esc(g.ai.external_llm)}</dd><dt>AI can execute actions</dt><dd>${g.ai.llm_can_execute_actions ? "yes" : "No, never"}</dd></dl>`;
  const f = $("#gov-weights");
  f.innerHTML = Object.entries(cfg.weights).map(([k, v]) => `<label class="wrow"><span>${esc(k)}</span>
      <input type="range" min="0" max="50" name="${esc(k)}" value="${v}"><b>${v}</b></label>`).join("") +
    `<label class="muted small">Business-critical apps<input name="critical_apps" value="${esc(cfg.critical_apps.join(", "))}"></label>
     <button class="btn go">Save weights (admin)</button>`;
  $$("input[type=range]", f).forEach((i) => i.oninput = () => (i.nextElementSibling.textContent = i.value));
  f.onsubmit = async (e) => {
    e.preventDefault();
    const weights = Object.fromEntries($$("input[type=range]", f).map((i) => [i.name, +i.value]));
    const critical_apps = f.critical_apps.value.split(",").map((s) => s.trim()).filter(Boolean);
    const r = await post("/api/impact/config", { weights, critical_apps });
    if (r && r.weights) toast("⚖️ Impact weights saved");
    loadGovernance();
  };
  $("#gov-audit").innerHTML = Array.isArray(log) && log.length ? `<table><tr><th>When</th><th>Who</th><th>Role</th><th>Action</th><th>Target</th><th>Result</th></tr>
    ${log.map((a) => `<tr><td class="muted small">${ago(a.ts)}</td><td>${esc(a.actor)}</td><td>${esc(a.role)}</td><td>${esc(a.action)}</td>
      <td class="muted">${esc(a.target)}${a.detail ? `<div class="small">${esc(a.detail)}</div>` : ""}</td>
      <td><span class="tag ${a.status === "ok" || a.status === "queued" ? "low" : "high"}">${esc(a.status)}</span></td></tr>`).join("")}</table>`
    : empty(Array.isArray(log) ? "No audited actions yet." : "Your role can't read the audit log (engineer or admin).");
}

// ---------- wire up ----------
Object.assign(LOADERS, {
  dex: () => loadDex(),
  alerts: () => Promise.all([loadAlerts(), loadCoverage()]),
  rca: () => loadRca(),
  remediation: () => loadRemediation(),
  assist: () => Promise.resolve(),
  integrations: () => loadConnectors(),
  reports: () => loadReports(),
  // live refreshes must not reset the weights form while someone is editing it
  governance: () => $("#gov-weights").contains(document.activeElement) ? Promise.resolve() : loadGovernance(),
});
document.addEventListener("DOMContentLoaded", () => { loadFilterOptions(); loadMe(); });
