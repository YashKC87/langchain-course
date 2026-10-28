// Flows: low-code visual workflow designer (drag nodes, drag from an output dot to a node to link,
// click a link to remove it). Runs are executed by the server engine; this page only edits and replays them.

const FL = { meta: null, flow: null, sel: null, dragging: null, linking: null, runs: [] };
const NODE_W = 230;
const NODE_ICON = { start: "▶", condition: "◇", action: "⚙️", notify_user: "💬", notify_it: "📣", guide: "🧭",
  service_api: "☁️", end: "⏹" };
const flCanvas = () => $("#fl-canvas");
const uid = () => Math.random().toString(36).slice(2, 8);

function nodeSummary(n) {
  const c = n.config || {};
  switch (n.type) {
    case "start": { const t = FL.flow.trigger; return t.type === "manual" ? "Run manually" : `When ${t.type.replace("_", " ")}: ${t.match || "any"}`; }
    case "condition": return c.field ? `${c.field} ${(c.op || "").replace("_", " ")} ${c.value ?? ""}` : "Set a condition";
    case "action": return c.action ? `${c.action}${c.target ? ` (${c.target})` : ""} · ${FL.meta.actions.find((a) => a.action === c.action)?.risk || ""} risk` : "Pick an approved action";
    case "notify_user": case "notify_it": return c.message || "Write a message";
    case "guide": return FL.meta.guides.find((g) => g.id == c.guide_id)?.title || "Pick a guide";
    case "service_api": return c.url ? `${c.method || "GET"} ${c.url}` : "Set the URL";
    case "end": return c.outcome || "";
  }
  return "";
}

// ---------- render ----------
function drawFlow() {
  const cv = flCanvas();
  $$(".fnode", cv).forEach((n) => n.remove());
  for (const n of FL.flow.graph.nodes) {
    const el = document.createElement("div");
    el.className = `fnode t-${n.type}${FL.sel === n.id ? " sel" : ""}`;
    el.dataset.id = n.id;
    el.style.left = `${n.x}px`; el.style.top = `${n.y}px`;
    const ports = FL.meta.node_types[n.type].ports;
    el.innerHTML = `${n.type !== "start" ? '<i class="pin in"></i>' : ""}
      <div class="fh"><span class="fi">${NODE_ICON[n.type]}</span>
        <div class="ft"><small>${esc(FL.meta.node_types[n.type].label)}</small><b>${esc(n.title || FL.meta.node_types[n.type].label)}</b></div>
        ${n.type !== "start" ? '<button class="trash" title="Delete">🗑</button>' : ""}</div>
      ${n.type !== "start" && n.type !== "end" || nodeSummary(n) ? `<div class="fb">${esc(nodeSummary(n))}</div>` : ""}
      <div class="ports">${ports.map((p) => `<i class="pin out" data-port="${p}">${ports.length > 1 ? `<em>${p === "yes" ? "Yes" : "No"}</em>` : ""}</i>`).join("")}</div>`;
    cv.appendChild(el);
  }
  drawEdges();
  drawMini();
}
function portXY(id, port) {
  const el = $(`.fnode[data-id="${id}"]`, flCanvas());
  if (!el) return null;
  const n = FL.flow.graph.nodes.find((x) => x.id === id);
  if (port === "in") return [n.x + NODE_W / 2, n.y];
  const pin = $(`.pin.out[data-port="${port}"]`, el);
  return [n.x + pin.offsetLeft + 7, n.y + el.offsetHeight];
}
const curve = ([x1, y1], [x2, y2]) => {
  const my = (y1 + y2) / 2;
  return `M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}`;
};
function drawEdges(temp) {
  const svg = $("#fl-svg"), visited = FL.highlight || new Set();
  svg.innerHTML = FL.flow.graph.edges.map((e, i) => {
    const a = portXY(e.from, e.port), b = portXY(e.to, "in");
    if (!a || !b) return "";
    const lit = visited.has(e.from) && visited.has(e.to);
    return `<path class="edge ${e.port}${lit ? " lit" : ""}" data-i="${i}" d="${curve(a, b)}"/>`;
  }).join("") + (temp ? `<path class="edge temp" d="${curve(temp[0], temp[1])}"/>` : "");
  $$(".edge[data-i]", svg).forEach((p) => p.onclick = () => {
    FL.flow.graph.edges.splice(+p.dataset.i, 1);
    drawEdges(); toast("Link removed (Save to keep)");
  });
}
function drawMini() {
  const nodes = FL.flow.graph.nodes, mm = $("#fl-mini"), s = 0.12;
  mm.innerHTML = nodes.map((n) => `<i class="t-${n.type}" style="left:${n.x * s}px;top:${n.y * s}px"></i>`).join("");
}

// ---------- interaction ----------
flCanvas().addEventListener("pointerdown", (e) => {
  const nodeEl = e.target.closest(".fnode");
  if (!nodeEl) { select(null); return; }
  const id = nodeEl.dataset.id, n = FL.flow.graph.nodes.find((x) => x.id === id);
  if (e.target.closest(".trash")) {
    FL.flow.graph.nodes = FL.flow.graph.nodes.filter((x) => x.id !== id);
    FL.flow.graph.edges = FL.flow.graph.edges.filter((x) => x.from !== id && x.to !== id);
    if (FL.sel === id) FL.sel = null;
    drawFlow(); inspect(); return;
  }
  const out = e.target.closest(".pin.out");
  if (out) { FL.linking = { from: id, port: out.dataset.port }; e.preventDefault(); return; }
  select(id);
  FL.dragging = { n, dx: e.clientX - n.x, dy: e.clientY - n.y, el: nodeEl };
  nodeEl.setPointerCapture(e.pointerId);
});
flCanvas().addEventListener("pointermove", (e) => {
  const r = flCanvas().getBoundingClientRect();
  if (FL.dragging) {
    const d = FL.dragging;
    d.n.x = Math.max(0, Math.round((e.clientX - d.dx) / 10) * 10);
    d.n.y = Math.max(0, Math.round((e.clientY - d.dy) / 10) * 10);
    d.el.style.left = `${d.n.x}px`; d.el.style.top = `${d.n.y}px`;
    drawEdges(); drawMini();
  } else if (FL.linking) {
    drawEdges([portXY(FL.linking.from, FL.linking.port), [e.clientX - r.left, e.clientY - r.top]]);
  }
});
window.addEventListener("pointerup", (e) => {
  if (FL.linking) {
    const target = document.elementFromPoint(e.clientX, e.clientY)?.closest(".fnode");
    const { from, port } = FL.linking;
    FL.linking = null;
    if (target && target.dataset.id !== from && !target.classList.contains("t-start")) {
      FL.flow.graph.edges = FL.flow.graph.edges.filter((x) => !(x.from === from && x.port === port));
      FL.flow.graph.edges.push({ from, port, to: target.dataset.id });
    }
    drawEdges();
  }
  FL.dragging = null;
});
$$(".flow-toolbar [data-add]").forEach((b) => b.onclick = () => {
  if (!FL.flow) return;
  const wrap = $("#fl-wrap"), type = b.dataset.add;
  const n = { id: `${type}-${uid()}`, type, x: Math.round((wrap.scrollLeft + 60) / 10) * 10,
    y: Math.round((wrap.scrollTop + 80) / 10) * 10, title: FL.meta.node_types[type].label, config: {} };
  FL.flow.graph.nodes.push(n);
  FL.sel = n.id;
  drawFlow(); inspect();
});
function select(id) {
  FL.sel = id;
  $$(".fnode", flCanvas()).forEach((el) => el.classList.toggle("sel", el.dataset.id === id));
  inspect();
}

// ---------- inspector ----------
const opt = (list, cur, label = (x) => x, val = (x) => x) =>
  list.map((x) => `<option value="${esc(val(x))}"${String(val(x)) === String(cur ?? "") ? " selected" : ""}>${esc(label(x))}</option>`).join("");
function inspect() {
  const box = $("#fl-inspect"), f = FL.flow;
  if (!f) { box.innerHTML = ""; return; }
  const n = f.graph.nodes.find((x) => x.id === FL.sel);
  if (!n) {
    box.innerHTML = `<h3>⚙️ Flow settings</h3><form class="form" id="fi-form">
      <label class="small">Name<input name="name" value="${esc(f.name)}"></label>
      <label class="small">Description<textarea name="description" rows="3">${esc(f.description || "")}</textarea></label>
      <label class="small">Trigger<select name="ttype">${opt(FL.meta.triggers, f.trigger.type, (t) => ({ manual: "Manual", issue_opened: "When an issue opens", alert_raised: "When an alert is raised" }[t]))}</select></label>
      <label class="small">Match (type starts with, e.g. app_crash:Teams)<input name="tmatch" value="${esc(f.trigger.match || "")}"></label>
      <label class="small">Max automatic runs per hour<input type="number" name="max" min="1" max="1000" value="${f.max_runs_per_hour}"></label>
      <label class="small check"><input type="checkbox" name="enabled"${f.enabled ? " checked" : ""}> Enabled (runs automatically on its trigger)</label>
    </form><p class="muted small">Version ${f.version || 1} · last edited by ${esc(f.updated_by || "—")}</p>
    <p class="muted small">Tip: drag from a node's bottom dot to another node to link them. Click a link to remove it.</p>
    ${f.id ? '<button class="btn no sm" id="fi-del">Delete flow</button>' : ""}`;
    const form = $("#fi-form");
    form.oninput = () => {
      f.name = form.name.value; f.description = form.description.value;
      f.trigger = { type: form.ttype.value, ...(form.tmatch.value ? { match: form.tmatch.value } : {}) };
      f.max_runs_per_hour = +form.max.value || 50; f.enabled = form.enabled.checked;
      drawFlow();
    };
    if ($("#fi-del")) $("#fi-del").onclick = async () => {
      if (!confirm(`Delete flow "${f.name}"?`)) return;
      await api(`/api/flows/${f.id}`, { method: "DELETE" });
      FL.flow = null; loadFlows();
    };
    return;
  }
  const c = n.config = n.config || {};
  const fields = {
    condition: `<label class="small">Field<input name="field" list="fl-fields" value="${esc(c.field || "")}"></label>
      <datalist id="fl-fields">${FL.meta.fields.map((x) => `<option value="${esc(x)}">`).join("")}</datalist>
      <label class="small">Operator<select name="op">${opt(FL.meta.ops, c.op, (o) => o.replace("_", " "))}</select></label>
      <label class="small">Value<input name="value" value="${esc(c.value ?? "")}"></label>`,
    action: `<label class="small">Approved action<select name="action"><option value="">Choose…</option>${opt(FL.meta.actions, c.action, (a) => `${a.action} (${a.risk} risk)`, (a) => a.action)}</select></label>
      <label class="small">Target app (optional, supports {{issue.type}})<input name="target" value="${esc(c.target || "")}"></label>
      <p class="muted small">Low risk runs automatically. Medium and high risk wait for an engineer's approval. Phones can't run scripts.</p>`,
    notify_user: `<label class="small">Message to the employee<textarea name="message" rows="3">${esc(c.message || "")}</textarea></label>`,
    notify_it: `<label class="small">Message to IT<textarea name="message" rows="3">${esc(c.message || "")}</textarea></label>
      <p class="muted small">${FL.meta.teams_webhook ? "Also posted to Teams." : "Set DWIP_TEAMS_WEBHOOK to also post to Teams."}</p>`,
    guide: `<label class="small">Guide<select name="guide_id"><option value="">Choose…</option>${opt(FL.meta.guides, c.guide_id, (g) => `${g.icon || ""} ${g.title}`, (g) => g.id)}</select></label>`,
    service_api: `<label class="small">Method<select name="method">${opt(["GET", "POST", "PUT", "PATCH"], c.method || "GET")}</select></label>
      <label class="small">URL<input name="url" value="${esc(c.url || "")}"></label>
      <label class="small">Headers (JSON, secrets as {{secret.NAME}})<textarea name="headers" rows="2">${esc(JSON.stringify(c.headers || {}))}</textarea></label>
      <label class="small">Body<textarea name="body" rows="2">${esc(c.body || "")}</textarea></label>
      <p class="muted small">Allowed hosts: ${FL.meta.allowed_hosts.length ? FL.meta.allowed_hosts.map(esc).join(", ") : "none. Set DWIP_FLOW_ALLOWED_HOSTS."} The response is available to later nodes as {{steps.${esc(n.id)}.json…}}.</p>`,
    end: `<label class="small">Outcome<input name="outcome" value="${esc(c.outcome || "")}"></label>`,
    start: `<p class="muted small">Set the trigger in Flow settings (click empty canvas).</p>`,
  }[n.type];
  box.innerHTML = `<h3>${NODE_ICON[n.type]} ${esc(FL.meta.node_types[n.type].label)}</h3><form class="form" id="fi-node">
    <label class="small">Title<input name="title" value="${esc(n.title || "")}"></label>${fields}</form>
    <p class="muted small">Use {{device.hostname}}, {{device.location}}, {{issue.title}}, {{input.incident_number}} in text.</p>`;
  const form = $("#fi-node");
  form.oninput = () => {
    n.title = form.title.value;
    for (const el of form.elements) {
      if (!el.name || el.name === "title") continue;
      if (el.name === "headers") { try { c.headers = JSON.parse(el.value || "{}"); el.classList.remove("bad"); } catch { el.classList.add("bad"); } }
      else c[el.name] = el.value;
    }
    const el = $(`.fnode[data-id="${n.id}"]`, flCanvas());
    if (el) { $(".ft b", el).textContent = n.title; const fb = $(".fb", el); if (fb) fb.textContent = nodeSummary(n); }
  };
}

// ---------- list, save, run ----------
async function loadFlows() {
  if (!FL.meta) FL.meta = await api("/api/flows/meta");
  const list = await api("/api/flows");
  $("#fl-list").innerHTML = list.map((f) => `<div class="insight flow-item${FL.flow && FL.flow.id === f.id ? " on" : ""}" data-fid="${f.id}">
    <div class="t">${f.enabled ? "🟢" : "⚪"} ${esc(f.name)}</div>
    <div class="ai-text">${esc(f.trigger.type === "manual" ? "Manual" : `${f.trigger.type.replace("_", " ")}: ${f.trigger.match || "any"}`)}
      ${f.last_run ? ` · last ${f.last_run.dry_run ? "dry " : ""}run ${esc(f.last_run.status)} ${ago(f.last_run.started_at)}` : ""}</div></div>`).join("") ||
    `<p class="muted">No flows yet.</p>`;
  $$("[data-fid]", $("#fl-list")).forEach((el) => el.onclick = () => openFlow(+el.dataset.fid));
  const devs = await api("/api/devices");
  $("#fl-dev").innerHTML = `<option value="">No device</option>` + devs.map((d) =>
    `<option value="${esc(d.id)}">${ICON[d.kind] || ""} ${esc(d.hostname)}${d.demo ? " (demo)" : ""}</option>`).join("");
  if (!FL.flow && list.length) openFlow(list[0].id);
}
async function openFlow(id) {
  FL.flow = await api(`/api/flows/${id}`);
  FL.sel = null; FL.highlight = null;
  $$("[data-fid]").forEach((el) => el.classList.toggle("on", +el.dataset.fid === id));
  drawFlow(); inspect(); loadRuns();
}
$("#fl-new").onclick = () => {
  FL.flow = { name: "New flow", description: "", trigger: { type: "manual" }, enabled: false, max_runs_per_hour: 50,
    graph: { nodes: [{ id: "start", type: "start", x: 260, y: 20, title: "Start", config: {} },
      { id: "end", type: "end", x: 260, y: 160, title: "End state", config: {} }],
      edges: [{ from: "start", port: "out", to: "end" }] } };
  FL.sel = null; drawFlow(); inspect(); $("#fl-runs").innerHTML = "";
};
$("#fl-save").onclick = async () => {
  const f = FL.flow;
  if (!f) return;
  const body = { name: f.name, description: f.description, trigger: f.trigger, graph: f.graph, enabled: f.enabled,
    max_runs_per_hour: f.max_runs_per_hour };
  const r = await api(f.id ? `/api/flows/${f.id}` : "/api/flows", { method: f.id ? "PUT" : "POST",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (r.detail) { $("#fl-msg").textContent = `❌ ${(r.detail.errors || [r.detail]).join(" · ")}`; return; }
  FL.flow = r;
  $("#fl-msg").textContent = r.errors.length ? `⚠️ Saved as draft: ${r.errors.join(" · ")}` : `✅ Saved version ${r.version}`;
  toast("🔀 Flow saved");
  loadFlows();
};
$("#fl-run").onclick = async () => {
  if (!FL.flow?.id) return toast("Save the flow first");
  const input = $("#fl-inc").value.trim() ? { incident_number: $("#fl-inc").value.trim() } : {};
  const r = await post(`/api/flows/${FL.flow.id}/run`, { device_id: $("#fl-dev").value || null, dry_run: $("#fl-dry").checked, input });
  if (r.detail) { $("#fl-msg").textContent = `❌ ${(r.detail.errors || [r.detail]).join(" · ")}`; return; }
  $("#fl-msg").textContent = `${r.status === "completed" ? "✅" : "❌"} ${r.dry_run ? "Dry run" : "Run"} #${r.id} ${r.status}`;
  replay(r.steps);
  loadRuns();
};
function replay(steps) {
  FL.highlight = new Set();
  $$(".fnode", flCanvas()).forEach((el) => el.classList.remove("ran", "fail"));
  steps.forEach((s, i) => setTimeout(() => {
    FL.highlight.add(s.node);
    $(`.fnode[data-id="${s.node}"]`, flCanvas())?.classList.add(s.status === "ok" ? "ran" : "fail");
    drawEdges();
  }, i * 350));
}
async function loadRuns() {
  if (!FL.flow?.id) return;
  const runs = await api(`/api/flows/${FL.flow.id}/runs`);
  $("#fl-runs").innerHTML = runs.map((r) => `<div class="insight run" data-run="${r.id}">
    <div class="t"><span class="tag ${r.status === "completed" ? "low" : r.status === "failed" ? "high" : ""}">${esc(r.status)}</span>
      #${r.id} ${r.dry_run ? '<span class="tag">dry run</span>' : ""} <span class="tag">${esc(r.trigger)}</span>
      ${esc(r.hostname || "no device")} <span class="muted small">${ago(r.started_at)} · v${r.flow_version} · ${esc(r.actor)}</span></div>
    <ol class="steps">${r.steps.map((s) => `<li class="${s.status}"><b>${esc(s.title)}</b> ${esc(s.result)} <i>${s.ms} ms</i></li>`).join("")}</ol></div>`).join("") ||
    `<p class="muted">No runs yet. Try a dry run.</p>`;
  $$("[data-run]").forEach((el) => el.onclick = () => replay(runs.find((r) => r.id === +el.dataset.run).steps));
}

LOADERS.flows = () => FL.flow ? loadRuns() : loadFlows();
