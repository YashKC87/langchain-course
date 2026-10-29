// Device notification box, remote access, adding devices (agent download, Azure VMs), demo-data removal.

// ---------- notification box (monitored devices only) ----------
const BELL_ICON = { issue: "⚠️", alert: "🚨", executed: "✅", failed: "❌", resolved: "💚", enroll: "🆕", offline: "🔌",
  online: "🟢", conversation: "💬" };
const bell = { items: [], kind: "", seen: 0 };
try { bell.seen = +localStorage.getItem("dwip-bell-seen") || 0; } catch { /* per-viewer convenience */ }
async function loadBell() {
  const r = await api("/api/device-notifications?limit=80");
  if (!r || !r.items) return;
  bell.items = r.items;
  const unread = r.items.filter((i) => i.id > bell.seen).length;
  $("#bell-n").textContent = unread ? (unread > 99 ? "99+" : unread) : "";
  $("#bell").classList.toggle("ring", unread > 0);
  $("#bell-sub").textContent = `${r.monitored} monitored device${r.monitored === 1 ? "" : "s"}`;
  if (!$("#bellbox").hidden) renderBell();
}
function renderBell() {
  const list = bell.items.filter((i) => !bell.kind || i.kind === bell.kind || (bell.kind === "executed" && i.kind === "failed"));
  $("#bell-list").innerHTML = list.map((i) => `<div class="bell-item${i.id > bell.seen ? " new" : ""}" data-dev="${esc(i.device_id)}">
      <span>${BELL_ICON[i.kind] || "•"}</span><div><b>${esc(i.hostname)}</b> ${esc(i.message.replace(`${i.hostname}: `, ""))}
      <div class="muted small">${ago(i.ts)}</div></div></div>`).join("") ||
    `<p class="muted center">No notifications from monitored devices.</p>`;
  $$(".bell-item", $("#bell-list")).forEach((el) => el.onclick = () => { $("#bellbox").hidden = true; openDrawer(el.dataset.dev); });
}
function markBellRead() {
  bell.seen = bell.items.length ? bell.items[0].id : bell.seen;
  try { localStorage.setItem("dwip-bell-seen", bell.seen); } catch { /* ignore */ }
  loadBell();
}
$("#bell").onclick = () => { const b = $("#bellbox"); b.hidden = !b.hidden; if (!b.hidden) renderBell(); };
$("#bell-read").onclick = markBellRead;
$$(".bell-tabs button").forEach((t) => t.onclick = () => {
  bell.kind = t.dataset.bk;
  $$(".bell-tabs button").forEach((x) => x.classList.toggle("on", x === t));
  renderBell();
});
document.addEventListener("click", (e) => {
  if (!$("#bellbox").hidden && !e.target.closest("#bellbox, #bell, .drawer")) $("#bellbox").hidden = true;
});

// ---------- remote access ----------
async function openRemote(id) {
  const box = $("#d-remote-box");
  const r = await api(`/api/devices/${id}/remote`);
  if (!r || !r.options) return;
  box.innerHTML = `<div class="card remote-box"><h3>🖥️ Remote access · ${esc(r.hostname)} ${r.online ? "🟢 online" : "⚪ offline"}</h3>
    ${r.ip_addresses.length ? `<p class="muted small">IP: ${r.ip_addresses.map(esc).join(", ")}</p>` : ""}
    ${r.unsupported ? `<p class="muted">${esc(r.unsupported)}</p>` : r.options.map((o) => `<div class="insight"><div class="t">${esc(o.label)}</div>
      <div class="ai-text">${esc(o.note)}</div><div class="btns"><button class="btn go sm" data-remote="${o.id}"${o.url ? ` data-url="${esc(o.url)}"` : ""}>
      ${o.id === "rdp" ? "⬇ Download .rdp and connect" : o.id === "assist" ? "📨 Send request to user" : "↗ Open in Azure"}</button></div></div>`).join("")}
    <p class="muted small">Every remote session request is recorded in the audit log.</p></div>`;
  $$("[data-remote]", box).forEach((b) => b.onclick = async () => {
    if (b.dataset.remote === "rdp") {
      const res = await fetch(`/api/devices/${id}/remote.rdp`, { headers: { "X-DWIP-Token": authToken() } });
      if (!res.ok) return toast("🔒 Not allowed or not available");
      const url = URL.createObjectURL(await res.blob()), a = document.createElement("a");
      a.href = url; a.download = `${r.hostname}.rdp`; a.click(); URL.revokeObjectURL(url);
      toast("⬇ Open the .rdp file to start Remote Desktop");
    } else if (b.dataset.remote === "assist") {
      const x = await post(`/api/devices/${id}/remote/assist`);
      toast(x.sent ? "📨 Request sent. The user will open Quick Assist." : "Couldn't send");
    } else window.open(b.dataset.url, "_blank", "noopener");
  });
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// ---------- add devices: agent package + Azure VMs ----------
$("#add-dev").onclick = async () => {
  const p = await api("/api/agent-package");
  const server = `${location.protocol}//${location.host}`;
  state.openId = null; state.openApp = null;
  $("#drawer-body").innerHTML = `<h2>➕ Add a device</h2>
    <p class="muted">Install the DWIP agent on any Windows laptop, desktop or VM, including Azure VMs, for real-time data.</p>
    <h3>1. Download the agent</h3>
    ${p.available ? `<p><a class="btn go" href="${p.url}">⬇ dwip-agent.exe (${p.size_mb} MB)</a> <span class="muted small">built ${ago(p.built_at)}</span></p>`
      : `<p class="err">The agent package hasn't been built yet. On the DWIP server run <code>packaging\\build_agent.ps1</code>.</p>`}
    <h3>2. Install it (administrator PowerShell on the device)</h3>
    <pre class="code">.\\dwip-agent.exe install --server ${esc(server)} --token &lt;enrolment token&gt; --location "&lt;site&gt;"</pre>
    <p class="muted small">It installs to C:\\Program Files\\DWIP, runs at start-up as SYSTEM and appears here within a minute.
      Use an address the device can reach: <code>localhost</code> or <code>127.0.0.1</code> only work on this PC.
      ${p.default_token ? "The enrolment token is still the default <code>dev-token</code>; set DWIP_ENROLL_TOKEN before wider use." : ""}</p>
    <h3>Remove it</h3><pre class="code">& "C:\\Program Files\\DWIP\\dwip-agent.exe" uninstall</pre>
    <h3>Azure VMs</h3><p class="muted small">Push the agent to Azure VMs without signing in to them: <button class="btn ghost sm" id="az-open2">☁️ Open Azure VMs</button></p>`;
  $("#az-open2").onclick = openAzure;
  openPanel();
};
$("#az-open").onclick = () => openAzure();
async function openAzure() {
  state.openId = null; state.openApp = null;
  const body = $("#drawer-body");
  body.innerHTML = `<h2>☁️ Azure virtual machines</h2><div class="bubble ai typing"><i></i><i></i><i></i></div><p class="muted small">Reading your subscription…</p>`;
  openPanel();
  const mon = await api("/api/azure/monitor");
  const monHtml = `<div class="card remote-box"><h3>🔗 Connected subscription</h3>
    <div class="sc-row"><label class="small grow2">Subscription ID<input id="az-sub" value="${esc(mon.subscription_id || "")}" placeholder="00000000-0000-0000-0000-000000000000"></label>
      <label class="small">Every<select id="az-int">${[60, 300, 900].map((v) => `<option value="${v}"${v === mon.interval_s ? " selected" : ""}>${v / 60} min</option>`).join("")}</select></label>
      <button class="btn go sm" id="az-connect">${mon.subscription_id ? "Save" : "Connect"}</button>
      ${mon.subscription_id ? `<button class="btn ghost sm" id="az-collect">⟳ Collect now</button>` : ""}</div>
    <p class="muted small">${mon.subscription_id ? `${mon.enabled ? "🟢 Collecting" : "⚪ Paused"} agentless telemetry (Azure Monitor) from the VMs in this subscription only.
      ${mon.last_ok ? `Last collected ${ago(mon.last_ok)}.` : ""} ${mon.error ? `<span class="err">${esc(mon.error)}</span>` : ""}`
      : "Connect one subscription: DWIP then reads CPU, memory, disk IOPS, network, availability and CPU credits for its VMs, with no agent needed."}</p></div>`;
  const r = await api("/api/azure/vms");
  if (!r.ok) {
    body.innerHTML = `<h2>☁️ Azure virtual machines</h2><p class="err">${esc(r.error)}</p>
      <p class="muted small">Either run <code>az login</code> on the DWIP server, or set DWIP_ENTRA_TENANT_ID, DWIP_ENTRA_CLIENT_ID, DWIP_ENTRA_CLIENT_SECRET
      and DWIP_AZURE_SUBSCRIPTION_ID. The identity needs Reader to list VMs and Virtual Machine Contributor to install the agent.</p>`;
    body.insertAdjacentHTML("beforeend", monHtml); bindMonitor();
    return;
  }
  const server = `${location.protocol}//${location.host}`;
  body.innerHTML = `<h2>☁️ Azure virtual machines</h2>${monHtml}
    <p class="muted small">Subscription ${esc(r.subscription)} · signed in with ${esc(r.auth)} · ${r.vms.length} VMs</p>
    <div class="table"><table><tr><th></th><th>VM</th><th>Region</th><th>Size</th><th>Power</th><th>DWIP</th></tr>
    ${r.vms.map((v) => `<tr><td>${v.device_id ? "" : `<input type="checkbox" class="az-pick" value="${esc(v.id)}"${v.power.includes("running") && v.os === "Windows" ? "" : " disabled"}>`}</td>
      <td><b>${esc(v.name)}</b><div class="muted small">${esc(v.resource_group)} · ${esc(v.os || "")}</div></td><td>${esc(v.location)}</td><td class="small">${esc(v.size || "")}</td>
      <td>${esc(v.power)}</td><td>${v.device_id ? `<a href="#" data-dev="${esc(v.device_id)}">🟢 monitored · DEX ${v.dex ?? "–"}</a>` : '<span class="muted">not monitored</span>'}</td></tr>`).join("")}
    </table></div>
    <label class="small">DWIP address the VMs can reach<input id="az-server" value="${esc(server)}"></label>
    <p class="muted small">Azure Run Command downloads the agent from this address and installs it. A private address such as 192.168.x.x only works if the VMs reach your network (VPN, ExpressRoute) or DWIP runs in Azure.</p>
    <button class="btn go" id="az-deploy">Install agent on selected VMs</button><div id="az-res"></div>`;
  $$("[data-dev]", body).forEach((a) => a.onclick = (e) => { e.preventDefault(); openDrawer(a.dataset.dev); });
  bindMonitor();
  $("#az-deploy").onclick = async () => {
    const ids = $$(".az-pick:checked", body).map((c) => c.value);
    if (!ids.length) return toast("Pick at least one running Windows VM");
    if (!confirm(`Install the DWIP agent on ${ids.length} VM(s) using Azure Run Command?`)) return;
    const res = await post("/api/azure/vms/deploy", { resource_ids: ids, server_url: $("#az-server").value.trim() });
    $("#az-res").innerHTML = (res.results || []).map((x) => `<div class="ev ${x.accepted ? "fact" : "gap"}"><b>${esc(x.name || x.id)}</b> ${esc(x.detail)}</div>`).join("") ||
      `<p class="err">${esc(res.detail || "Failed")}</p>`;
  };
}

function bindMonitor() {
  $("#az-connect").onclick = async () => {
    const r = await post("/api/azure/monitor", { subscription_id: $("#az-sub").value.trim(), enabled: true, interval_s: +$("#az-int").value });
    if (!r.subscription_id) return toast(`❌ ${esc(r.detail || "Not saved")}`);
    toast("🔗 Subscription connected. Collecting now…");
    await post("/api/azure/monitor/collect"); openAzure();
  };
  if ($("#az-collect")) $("#az-collect").onclick = async () => {
    const r = await post("/api/azure/monitor/collect");
    toast(r.ok ? `⟳ Collected ${r.vms.length} VM(s)` : `❌ ${esc(r.detail || "Failed")}`); openAzure();
  };
}

// ---------- governance: remove synthetic data ----------
const _govLoad = LOADERS.governance;
LOADERS.governance = async () => {
  await _govLoad();
  if ($("#purge-demo")) return;
  $("#gov-policy").insertAdjacentHTML("afterend", `<h3 style="margin-top:18px">🧹 Demo data</h3>
    <p class="muted small">Removes every simulated (DEMO) device and its history. Real monitored devices are kept. Stop the simulator first.</p>
    <button class="btn no sm" id="purge-demo">Remove demo data (admin)</button>`);
  $("#purge-demo").onclick = async () => {
    if (!confirm("Remove all demo devices and their data? This can't be undone.")) return;
    const r = await post("/api/admin/purge-demo");
    if (r.removed_devices != null) { toast(`🧹 Removed ${r.removed_devices} demo devices`); refresh(true); }
  };
};

document.addEventListener("DOMContentLoaded", () => { loadBell(); setInterval(loadBell, 15000); });
