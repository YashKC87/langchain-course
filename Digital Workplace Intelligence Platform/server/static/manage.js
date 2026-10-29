// Alert thresholds (a meter per parameter) and the script library.

// ---------- thresholds ----------
const TH = { scope: "device", data: null, dirty: {} };
const fmtN = (v, u) => v == null ? "–" : `${Math.round(v * 10) / 10}${u ? ` ${u}` : ""}`;
async function loadThresholds() {
  const d = TH.data = await api(`/api/thresholds?scope=${encodeURIComponent(TH.scope)}`);
  if (!d || !d.params) return;
  const sel = $("#th-scope");
  sel.innerHTML = [["device", "All devices (global)"], ["kind:laptop", "Laptops"], ["kind:desktop", "Desktops"],
    ["kind:mobile", "Mobiles"], ["kind:vdi", "Virtual desktops / VMs"], ["app:*", "All applications"],
    ...d.apps.map((a) => [`app:${a}`, `App: ${a}`])].map(([v, l]) => `<option value="${esc(v)}"${v === TH.scope ? " selected" : ""}>${esc(l)}</option>`).join("");
  $("#th-note").textContent = TH.scope === "device" ? "Device-type and app scopes override these." :
    TH.scope.startsWith("kind:") ? "Overrides the global values for this device type." : "Overrides the defaults for this application.";
  TH.dirty = {};
  $("#th-list").innerHTML = d.params.map((p) => {
    const below = p.dir === "below", max = p.max;
    const pct = (v) => v == null ? 0 : Math.min(100, (v / max) * 100);
    return `<div class="card th" data-p="${esc(p.param)}">
      <div class="th-head"><b>${esc(p.label)}</b><span class="muted small">${below ? "alerts when below" : "alerts when above"}</span>
        ${p.breaching_crit ? `<span class="tag high">${p.breaching_crit} critical</span>` : ""}${p.breaching_warn ? `<span class="tag medium">${p.breaching_warn} warning</span>` : ""}</div>
      <div class="meterbar${below ? " below" : ""}" style="--w:${pct(p.warn)}%;--c:${pct(p.crit ?? (below ? 0 : max))}%">
        ${p.current_min != null ? `<i class="range" style="left:${pct(p.current_min)}%;width:${Math.max(1, pct(p.current_max) - pct(p.current_min))}%" title="your devices now"></i>` : ""}
        <i class="mk w" style="left:${pct(p.warn)}%"></i>${p.crit != null ? `<i class="mk c" style="left:${pct(p.crit)}%"></i>` : ""}</div>
      <div class="muted small">${p.samples ? `Now: ${fmtN(p.current_min, p.unit)} – ${fmtN(p.current_max, p.unit)} (avg ${fmtN(p.current_avg, p.unit)}, ${p.samples} reporting)` : "No device reports this yet"}</div>
      <div class="th-inputs">
        <label>Warning<input type="range" name="warn" min="0" max="${max}" step="${max > 200 ? 10 : 1}" value="${p.warn ?? 0}"><output>${fmtN(p.warn, p.unit)}</output></label>
        <label>Critical<input type="range" name="crit" min="0" max="${max}" step="${max > 200 ? 10 : 1}" value="${p.crit ?? (below ? 0 : max)}"><output>${p.crit == null ? "off" : fmtN(p.crit, p.unit)}</output></label>
        <label class="sus">Sustained<input type="number" name="sustain_min" min="0" max="240" value="${p.sustain_min || 0}" ${p.sustain_supported ? "" : "disabled title='Sustained checks need per-sample history (CPU, memory, disk, battery)'"}> min</label>
        <button type="button" class="btn ghost sm" data-critoff>${p.crit == null ? "Add critical" : "No critical"}</button>
      </div>
      <div class="muted small">Default: warning ${fmtN(p.default.warn, p.unit)}${p.default.crit != null ? `, critical ${fmtN(p.default.crit, p.unit)}` : ""}</div></div>`;
  }).join("");
  $$(".th", $("#th-list")).forEach((card) => {
    const k = card.dataset.p, p = d.params.find((x) => x.param === k), max = p.max, bar = $(".meterbar", card);
    const mark = (cls, v) => { const el = $(`.mk.${cls}`, card); if (el) el.style.left = `${Math.min(100, v / max * 100)}%`; };
    const set = (f, v) => { TH.dirty[k] = { ...(TH.dirty[k] || {}), [f]: v }; card.classList.add("changed"); };
    $$("input", card).forEach((i) => i.oninput = () => {
      const v = +i.value;
      if (i.name === "warn") { i.nextElementSibling.textContent = fmtN(v, p.unit); bar.style.setProperty("--w", `${v / max * 100}%`); mark("w", v); }
      if (i.name === "crit") {
        if (!$(".mk.c", card)) bar.insertAdjacentHTML("beforeend", '<i class="mk c"></i>');
        i.nextElementSibling.textContent = fmtN(v, p.unit); bar.style.setProperty("--c", `${v / max * 100}%`); mark("c", v);
      }
      set(i.name, v);
    });
    $("[data-critoff]", card).onclick = (e) => {
      const on = !$(".mk.c", card);
      if (on) { const v = +$("input[name=crit]", card).value; bar.insertAdjacentHTML("beforeend", '<i class="mk c"></i>'); mark("c", v); set("crit", v); e.target.textContent = "No critical"; }
      else { $(".mk.c", card).remove(); $("input[name=crit]", card).nextElementSibling.textContent = "off"; set("crit", null); e.target.textContent = "Add critical"; }
    };
  });
}
$("#th-scope").onchange = (e) => { TH.scope = e.target.value; loadThresholds(); };
$("#th-save").onclick = async () => {
  if (!Object.keys(TH.dirty).length) return toast("Nothing changed");
  const r = await post("/api/thresholds", { scope: TH.scope, params: TH.dirty });
  if (r.ok) { toast(`🎚️ Saved. Applies ${r.applies}.`); loadThresholds(); } else toast(`❌ ${esc(r.detail || "Not saved")}`);
};
$("#th-reset").onclick = async () => {
  if (!confirm("Reset this scope to the defaults?")) return;
  await post("/api/thresholds", { scope: TH.scope, reset: true });
  toast("Reset to defaults"); loadThresholds();
};

// ---------- scripts ----------
const SC = { meta: null, cur: null, list: [] };
const SC_STATUS = { draft: ["🟡", "Draft: needs approval"], approved: ["🟢", "Approved"], rejected: ["🔴", "Rejected"] };
async function loadScripts() {
  if (!SC.meta) {
    SC.meta = await api("/api/scripts/meta");
    $("#sc-form").language.innerHTML = Object.entries(SC.meta.languages).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  }
  $("#sc-form").app.innerHTML = SC.meta.apps.map((a) => `<option>${esc(a)}</option>`).join("") || "<option value=''>No apps reported yet</option>";
  SC.list = await api("/api/scripts");
  $("#sc-list").innerHTML = SC.list.map((s) => `<div class="insight sc-item${SC.cur && SC.cur.id === s.id ? " on" : ""}" data-sid="${s.id}">
    <div class="t">${SC_STATUS[s.status][0]} ${esc(s.name)} <span class="tag">${esc(SC.meta.languages[s.language])}</span></div>
    <div class="ai-text">${s.target === "app" ? `App: ${esc(s.app)} · ` : ""}${esc(s.risk)} risk · v${s.version}${s.last_run ? ` · last run ${esc(s.last_run.status)} ${ago(s.last_run.created_at)}` : ""}</div></div>`).join("");
  $$("[data-sid]", $("#sc-list")).forEach((el) => el.onclick = () => openScript(+el.dataset.sid));
  const pend = await api("/api/script-runs/pending");
  $("#n-sruns").textContent = pend.length || "";
  $("#sc-pending").innerHTML = pend.map((r) => `<div class="insight appr" data-rid="${r.id}"><div class="t">${esc(r.name)} <span class="tag high">high risk</span></div>
    <div class="ai-text">${esc(r.hostname)} · requested by ${esc(r.requested_by)} ${ago(r.created_at)}</div>
    <div class="btns"><button class="btn go sm" data-d="approve">Approve</button><button class="btn no sm" data-d="reject">Reject</button></div></div>`).join("") ||
    `<p class="muted small">Nothing waiting.</p>`;
  $$("[data-rid] [data-d]").forEach((b) => b.onclick = async () => {
    const r = await post(`/api/script-runs/${b.closest("[data-rid]").dataset.rid}/${b.dataset.d}`);
    toast(r.status ? `Run ${r.status}` : `❌ ${esc(r.detail)}`); loadScripts();
  });
  if (!SC.cur && SC.list.length) openScript(SC.list[0].id); else if (SC.cur?.id) loadRuns2();
}
async function openScript(id) {
  SC.cur = await api(`/api/scripts/${id}`);
  fillScriptForm();
  $$("[data-sid]").forEach((el) => el.classList.toggle("on", +el.dataset.sid === id));
  loadRuns2(); fillWhich();
}
function fillScriptForm() {
  const f = $("#sc-form"), s = SC.cur || { name: "", description: "", language: "powershell", target: "device", risk: "low", body: "" };
  for (const k of ["name", "description", "language", "target", "risk", "body"]) f[k].value = s[k] ?? "";
  if (s.app) f.app.value = s.app;
  $("#sc-app-wrap").style.display = f.target.value === "app" ? "" : "none";
  const st = s.id ? SC_STATUS[s.status] : ["⚪", "New script"];
  $("#sc-status").innerHTML = `${st[0]} <b>${st[1]}</b>${s.id ? ` · v${s.version} · written by ${esc(s.created_by)}${s.approved_by ? ` · ${s.status} by ${esc(s.approved_by)} ${ago(s.approved_at)}` : ""}
    <div class="muted small">SHA-256 ${esc(s.sha256.slice(0, 16))}… (the agent refuses any other body)</div>` : ""}`;
  $("#sc-approve").style.display = $("#sc-reject").style.display = s.id && s.status === "draft" ? "" : "none";
}
$("#sc-form").target.onchange = (e) => ($("#sc-app-wrap").style.display = e.target.value === "app" ? "" : "none");
$("#sc-new").onclick = () => { SC.cur = null; fillScriptForm(); $("#sc-runs").innerHTML = ""; $$("[data-sid]").forEach((el) => el.classList.remove("on")); };
$("#sc-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target, body = { name: f.name.value, description: f.description.value, language: f.language.value,
    target: f.target.value, app: f.target.value === "app" ? f.app.value : null, risk: f.risk.value, body: f.body.value };
  const r = await api(SC.cur?.id ? `/api/scripts/${SC.cur.id}` : "/api/scripts", { method: SC.cur?.id ? "PUT" : "POST",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.id) return toast(`❌ ${esc(r.detail || "Not saved")}`);
  SC.cur = r; toast(`📜 Saved v${r.version}. It needs approval before it can run.`); fillScriptForm(); loadScripts();
};
for (const [id, d] of [["#sc-approve", "approve"], ["#sc-reject", "reject"]]) $(id).onclick = async () => {
  if (d === "approve" && !confirm(`Approve "${SC.cur.name}" v${SC.cur.version}? Read the script first: once approved it can run on devices.`)) return;
  const r = await post(`/api/scripts/${SC.cur.id}/review/${d}`);
  if (!r.id) return toast(`❌ ${esc(r.detail)}`);
  SC.cur = r; fillScriptForm(); loadScripts();
};
async function fillWhich() {
  const scope = $("#sc-scope").value, which = $("#sc-which");
  if (scope === "device") {
    const devs = await api("/api/devices?data=live");
    which.innerHTML = devs.map((d) => `<option value="${esc(d.id)}">${ICON[d.kind] || ""} ${esc(d.hostname)} (${esc(d.platform)})</option>`).join("");
  } else if (scope === "kind") which.innerHTML = ["laptop", "desktop", "vdi"].map((k) => `<option>${k}</option>`).join("");
  else if (scope === "location") which.innerHTML = (await api("/api/filters")).location.map((l) => `<option>${esc(l)}</option>`).join("");
  else which.innerHTML = SC.meta.apps.map((a) => `<option${SC.cur?.app === a ? " selected" : ""}>${esc(a)}</option>`).join("");
}
$("#sc-scope").onchange = fillWhich;
$("#sc-run").onclick = async () => {
  if (!SC.cur?.id) return toast("Save the script first");
  if (SC.cur.status !== "approved") return toast("Approve this version before running it");
  const scope = $("#sc-scope").value, v = $("#sc-which").value, dry = $("#sc-dry").checked;
  const body = { dry_run: dry, ...(scope === "device" ? { device_ids: [v] } : { [scope]: v }) };
  if (!dry && !confirm(`Run "${SC.cur.name}" for real on the selected ${scope === "device" ? "device" : "devices"}?`)) return;
  const r = await post(`/api/scripts/${SC.cur.id}/run`, body);
  if (!r.results) return ($("#sc-runmsg").textContent = `❌ ${r.detail}`);
  const c = r.results.reduce((a, x) => ({ ...a, [x.status]: (a[x.status] || 0) + 1 }), {});
  $("#sc-runmsg").textContent = `${r.results.length} device(s): ` + Object.entries(c).map(([k, n]) => `${n} ${k.replace("_", " ")}`).join(", ");
  loadRuns2(); loadScripts();
};
async function loadRuns2() {
  const runs = await api(`/api/scripts/${SC.cur.id}/runs`);
  $("#sc-runs").innerHTML = runs.length ? `<table><tr><th>#</th><th>Device</th><th>Status</th><th>Exit</th><th>By</th><th>When</th></tr>
    ${runs.map((r) => `<tr class="sc-run" data-out="${esc(r.output || "")}"><td>${r.id}</td><td>${esc(r.hostname || "")}</td>
      <td><span class="tag ${r.status === "done" ? "low" : ["failed", "refused", "rejected"].includes(r.status) ? "high" : ""}">${esc(r.status.replace("_", " "))}</span></td>
      <td>${r.exit_code ?? ""}</td><td class="muted small">${esc(r.requested_by)}${r.source !== "console" ? ` · ${esc(r.source)}` : ""}</td><td class="muted small">${ago(r.updated_at)}</td></tr>`).join("")}</table>
    <pre class="code" id="sc-out" hidden></pre>` : `<p class="muted">No runs yet. Try a dry run.</p>`;
  $$(".sc-run").forEach((tr) => tr.onclick = () => { const o = $("#sc-out"); o.hidden = !tr.dataset.out; o.textContent = tr.dataset.out; });
}

Object.assign(LOADERS, {
  thresholds: () => $(".th.changed") ? Promise.resolve() : loadThresholds(),
  scripts: () => $("#sc-form").contains(document.activeElement) ? Promise.resolve() : loadScripts(),
});
