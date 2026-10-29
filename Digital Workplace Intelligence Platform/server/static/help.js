// Help Guide: searchable in-console user guide. Content is static HTML kept next to the features it describes.

const HELP = [
  { id: "overview", title: "What is DWIP?", go: "overview", tags: "about n-dude-n loop devices", body: `
    <p>DWIP watches every employee device, finds experience problems before users raise tickets, fixes safe ones automatically and asks employees how their device feels. It runs on your own server with an optional local AI model, so no telemetry leaves your network.</p>
    <table><tr><th>Device type</th><th>What DWIP reads</th></tr>
      <tr><td>Laptops and desktops (Windows, macOS)</td><td>CPU, memory, disk, battery, boot time, crashes, patch age, OS errors, apps</td></tr>
      <tr><td>Mobile phones (Android, iOS)</td><td>Storage, battery, OS version, apps, network latency</td></tr>
      <tr><td>Virtual desktops (Citrix, AVD)</td><td>Session latency, logon time, session host, protocol, apps</td></tr></table>
    <p><b>The N-DUDE-N loop</b> runs on every device report:</p>
    <ol><li><b>Notice</b>: the agent reports telemetry.</li><li><b>Discover</b>: rules find problems.</li><li><b>Understand</b>: DWIP compares with the device's history and the fleet.</li>
      <li><b>Decide</b>: it picks an approved fix and decides whether it needs approval.</li><li><b>Execute</b>: low-risk fixes run; others wait for an engineer.</li><li><b>Notify</b>: the employee gets a message, guide or survey; IT sees it in the console.</li></ol>` },
  { id: "start", title: "Getting started", tags: "install run setup server agent simulator settings environment variables", body: `
    <ol><li><code>pip install -r requirements.txt</code></li><li>Optional AI: <code>ollama pull gemma3:4b</code></li>
      <li>Server: <code>python -m uvicorn server.main:app --host 0.0.0.0 --port 8000</code></li>
      <li>Demo fleet: <code>python simulator/simulate.py</code> (14 devices, marked DEMO)</li>
      <li>Real PC: <code>python agent/agent.py --location Bangalore --department IT</code> (dry-run by default)</li>
      <li>Console: <code>http://127.0.0.1:8000</code> · employee app: <code>/companion</code></li></ol>
    <p>On Windows use <code>127.0.0.1</code>, not <code>localhost</code>: <code>localhost</code> tries IPv6 first and adds about 2 s to every request.</p>
    <table><tr><th>Setting</th><th>Purpose</th></tr>
      <tr><td><code>DWIP_DB</code></td><td>Database location (default %LOCALAPPDATA%\\DWIP)</td></tr>
      <tr><td><code>DWIP_ENROLL_TOKEN</code></td><td>Token devices use to join (default dev-token)</td></tr>
      <tr><td><code>DWIP_IT_TOKENS</code></td><td>Console sign-in, <code>token:role:name,…</code></td></tr>
      <tr><td><code>DWIP_AI</code> / <code>DWIP_LLM_MODEL</code></td><td>Turn the local AI on or off / choose the model</td></tr>
      <tr><td><code>DWIP_FLOW_ALLOWED_HOSTS</code></td><td>Hosts that Flows may call</td></tr>
      <tr><td><code>DWIP_SECRET_&lt;NAME&gt;</code></td><td>Secrets for Flows (<code>{{secret.NAME}}</code>)</td></tr>
      <tr><td><code>DWIP_TEAMS_WEBHOOK</code></td><td>Teams posts from "Notify IT"</td></tr></table>` },
  { id: "tour", title: "Console tour, filters and freshness", tags: "navigation sidebar filter demo badge live copilot", body: `
    <p>The left sidebar has 10 main sections; indented items sit under the section above them. Click any KPI tile to jump to its page.</p>
    <p><b>Filter bar</b> (top of the page): location, department, device type, data (live + demo, live only, demo only) and period. It is remembered in your browser and used by the DEX, RCA, Devices, Reports and AI Assist pages.</p>
    <p><b>Data freshness:</b> the right end of the filter bar shows the age of the newest data. 🟢 means under 2 minutes, 🟠 means older.</p>
    <p><b>DEMO badge:</b> simulator devices are tagged DEMO. Choose <i>Live only</i> to hide them.</p>
    <p><b>Copilot ✨</b> (bottom right): a quick chat about the fleet. Use <a href="#assist">AI Assist</a> for investigations with evidence.</p>` },
  { id: "dex", title: "Digital Employee Experience page", go: "dex", tags: "dex score kpi trend heatmap location top problems", body: `
    <p><b>DEX score per device (0–100)</b> = 35% performance + 30% stability + 20% responsiveness + 15% survey sentiment. 80+ good, 60–79 attention, under 60 poor.</p>
    <ul><li><b>KPIs:</b> overall DEX, impacted employees, critical issues (impact 60 or higher), alerts, predicted risks.</li>
      <li><b>Experience trend:</b> average DEX for the chosen period.</li>
      <li><b>Top 5 problems:</b> ranked by Employee Impact Score. Click one to open the incident.</li>
      <li><b>Location heatmap:</b> DEX by location × device type. Click a cell to open those devices.</li>
      <li><b>Application experience:</b> health score per app.</li></ul>` },
  { id: "impact", title: "Employee Impact Score", go: "dex", tags: "impact score weights factors explain priority", body: `
    <p>Each open problem scores 0–100 from six weighted factors. Click <b>Why this score?</b> on an incident to see the points for each factor.</p>
    <table><tr><th>Factor</th><th>Weight</th><th>Full points when</th></tr>
      <tr><td>Reach</td><td>30</td><td>Every employee in scope is affected</td></tr><tr><td>Severity</td><td>25</td><td>High (medium 0.6, low 0.3)</td></tr>
      <tr><td>Critical app</td><td>15</td><td>Teams, Outlook, SAP GUI, Citrix Workspace or VDI</td></tr><tr><td>Duration</td><td>10</td><td>Open 60 minutes or more</td></tr>
      <tr><td>Recurrence</td><td>10</td><td>Re-opened 5 times in 24 h</td></tr><tr><td>Escalation</td><td>10</td><td>New devices affected in the last 10 min</td></tr></table>
    <p>Admins change the weights and critical apps in <a href="#governance">Governance and Audit</a>.</p>` },
  { id: "devices", title: "Devices and applications", go: "devices", tags: "device drawer apps versions message survey", body: `
    <p><b>Devices:</b> filter by All, Laptops, Desktops, Mobiles or VDI. Click a card for vitals, DEX history, issues, actions, apps, guides, surveys and conversations, with <i>Message user</i>, <i>Send a guide</i>, <i>Request survey</i> and <i>Ask Copilot</i>.</p>
    <p><b>Applications:</b> health score per app from crashes, hangs, response time and CPU. Open an app for its version breakdown, which shows when one version is the problem, plus its devices and response-time trend.</p>` },
  { id: "engage", title: "Engagement, conversations and guidance", go: "engage", tags: "survey pulse campaign sentiment chat talk to it guide in-app", body: `
    <p><b>Engagement:</b> send a pulse question to everyone or to one device type. See sentiment by department, the experience score (−100 to +100), response rate, guide completion and comments.</p>
    <p><b>Conversations:</b> an employee taps <i>Talk to IT</i>; the AI checks their device and posts a triage note; IT replies from <a href="#collab">Conversations</a>.</p>
    <p><b>In-app guidance:</b> step-by-step guides. Create one with an optional automatic trigger (e.g. storage full), or push it to a device or device type. Each guide goes to a device at most once a day.</p>` },
  { id: "monitor", title: "Proactive Monitoring and coverage", go: "alerts", tags: "alerts anomaly fleet alert coverage not collected", body: `
    <ul><li><b>Device anomaly:</b> a device's DEX drops at least 12 points, well below its own normal.</li>
      <li><b>Fleet alert:</b> the same issue on 3 or more devices within 30 minutes. It clears itself when fewer than 2 remain.</li></ul>
    <p>Actions: Acknowledge, Resolve, Open device, Ask Copilot.</p>
    <p><b>Monitoring coverage</b> lists each signal as <i>Live</i>, <i>Demo only</i> or <i>Not collected</i>. A signal that is not collected names what it needs. DWIP never shows a value for it.</p>` },
  { id: "rca", title: "AI Root Cause Analysis", go: "rca", tags: "incident evidence fact correlation hypothesis root cause", body: `
    <p>Each incident groups one problem across devices and shows:</p>
    <ul><li><span class="ev-dot fact"></span><b>Observed facts</b>: real readings</li><li><span class="ev-dot correlation"></span><b>Correlations</b>: seen together, not proof of cause</li>
      <li><span class="ev-dot hypothesis"></span><b>Hypothesis</b>: always "not confirmed"</li></ul>
    <p>Status stays <i>Investigating: root cause not confirmed</i> until the evidence supports a cause. Click an incident for the score breakdown, devices and predictions; <b>Investigate</b> sends it to AI Assist.</p>` },
  { id: "predict", title: "Predictive Intelligence", go: "predict", tags: "forecast prediction disk battery patch crash trend confidence", body: `
    <table><tr><th>Prediction</th><th>Method</th></tr>
      <tr><td>Storage will be full</td><td>Linear trend; needs R² ≥ 0.6 and a steady rise; disk under 90%</td></tr>
      <tr><td>Experience degrading</td><td>Linear trend on DEX; falls below 60 within 7 days</td></tr>
      <tr><td>Battery replacement</td><td>Wear estimate when health is under 80%</td></tr>
      <tr><td>App crash rate rising</td><td>Crashes at least doubled against 5–15 minutes ago</td></tr>
      <tr><td>Patch policy breach</td><td>Patch age 16–29 days, so it reaches the 30-day limit soon</td></tr></table>
    <p>The simulator runs time-compressed, so its forecasts read in minutes.</p>` },
  { id: "remediation", title: "Intelligent Remediation and approvals", go: "remediation", tags: "fix approve reject catalogue risk verification self-healing", body: `
    <p>Only actions from the approved catalogue can run. The AI cannot run anything.</p>
    <table><tr><th>Action</th><th>Risk</th><th>Mode</th></tr>
      <tr><td>clean_temp, top_processes</td><td>Low</td><td>Runs automatically</td></tr>
      <tr><td>repair_app, restart_app, install_updates</td><td>Medium</td><td>Engineer approval</td></tr>
      <tr><td>schedule_reboot</td><td>High</td><td>Engineer approval</td></tr></table>
    <p>Approve or reject fixes in the queue. <i>Recent actions</i> shows whether each fix actually cleared the issue ("verified") or not yet. The agent is dry-run by default.</p>` },
  { id: "flows", title: "Flows: build a workflow", go: "flows", tags: "flow workflow designer low-code automation trigger condition service api node", body: `
    <ol><li>Open <a href="#flows">Flows</a> and click <b>＋ New</b>, or pick a sample.</li>
      <li>Click empty canvas to set the name, trigger (Manual, Issue opens, Alert raised), match, runs per hour and Enabled.</li>
      <li>Add steps from the toolbar: Condition, Remote action, Notify employee, Notify IT, Guide, Service/API, End.</li>
      <li>Drag from a step's bottom dot (a Condition has <i>Yes</i> and <i>No</i>) onto the next step to link them. Click a link to remove it; 🗑 deletes a step.</li>
      <li>Click a step to set it up. Text can use <code>{{device.hostname}}</code>, <code>{{issue.title}}</code>, <code>{{input.incident_number}}</code>.</li>
      <li><b>Save</b> (each save is a new version), then pick a device, keep <b>Dry run</b> ticked and click <b>▶ Run</b>. The path lights up and appears in Run history.</li></ol>
    <p><b>Safety:</b> no loops; at most 50 steps; Service/API only to <code>DWIP_FLOW_ALLOWED_HOSTS</code> with a 10 s timeout; secrets as <code>{{secret.NAME}}</code> are never logged; a cap on runs per hour; engineers and admins only.</p>` },
  { id: "assist", title: "AI Assist: ask questions", go: "assist", tags: "ai assist question investigate llm gemma confidence gaps evidence copilot", body: `
    <p>Ask in plain language, e.g. <i>"Why is Teams degraded in Bangalore?"</i>. Places, departments, apps and device names in the question narrow the scope.</p>
    <p>Order: rules → statistics → data gaps → local AI (only when there is evidence). Labels: <b>Observed fact</b>, <b>Prediction</b>, <b>Correlation</b>, <b>Hypothesis</b> (not confirmed), <b>Not available</b> (data DWIP does not collect).</p>
    <p><b>Confidence:</b> <i>High</i> needs a matching incident, 3 or more pieces of evidence, no gaps and data under 2 minutes old. Suggested fixes are read-only; approve them in Remediation.</p>` },
  { id: "integrations", title: "Enterprise integrations", go: "integrations", tags: "connector intune servicenow graph azure monitor sccm nexthink splunk status", body: `
    <table><tr><th>Status</th><th>Meaning</th></tr><tr><td>Connected</td><td>Data arriving now</td></tr><tr><td>Stale</td><td>Devices not reporting for over 90 s</td></tr>
      <tr><td>No data</td><td>Nothing enrolled from this source</td></tr><tr><td>Configured</td><td>Credentials set; use <i>Test sign-in</i></td></tr>
      <tr><td>Not configured</td><td>No credentials, so no data is shown</td></tr></table>
    <p>Each card lists the settings it needs. Microsoft sources use <code>DWIP_ENTRA_TENANT_ID</code>, <code>_CLIENT_ID</code> and <code>_CLIENT_SECRET</code>; ServiceNow uses <code>DWIP_SNOW_INSTANCE</code>, <code>_USER</code> and <code>_PASSWORD</code>.</p>` },
  { id: "reports", title: "Reports, benchmarks and AI cost", go: "reports", tags: "benchmark baseline compare location business unit os tokens cost usage", body: `
    <p>Benchmark by location, business unit, device type, OS version, model or VDI pool against your own enterprise average and the previous 7 days. The 7-day view needs 24 hours of history first. No external benchmark data is used.</p>
    <p><b>AI usage:</b> investigations, the share answered without an LLM, alerts explained, tokens, latency and cost ($0 for the local model).</p>` },
  { id: "governance", title: "Roles, sign-in and audit", go: "governance", tags: "role rbac token sign in login audit log retention security viewer analyst engineer admin", body: `
    <table><tr><th>Role</th><th>Can</th></tr><tr><td>Viewer</td><td>Read and ask AI Assist (employee names masked)</td></tr>
      <tr><td>Analyst</td><td>+ alerts, messages, guides, pulses</td></tr><tr><td>Engineer</td><td>+ approve fixes, build and run flows, read audit</td></tr><tr><td>Admin</td><td>+ impact weights, connectors</td></tr></table>
    <p>Turn on sign-in: <code>$env:DWIP_IT_TOKENS = "S3cret:admin:Yashaswi,View1:viewer:Guest"</code>, restart the server, then enter your token in the sign-in box.</p>
    <p>Audited: every change, every denied request, AI questions, automatic fixes, connector tests and flow runs. Retention: raw telemetry 1 day, rollups 90 days, audit 365 days.</p>` },
  { id: "companion", title: "Employee companion app", tags: "employee phone mobile companion inbox help guides survey", body: `
    <p>Employees open <code>http://&lt;server&gt;:8000/companion</code>. On a phone, join the same Wi-Fi and enrol with the enrolment token.</p>
    <ul><li><b>Home:</b> device score, surveys, messages</li><li><b>Guides:</b> step-by-step guides with progress</li>
      <li><b>Help:</b> AI helper for their own device, plus <i>Talk to IT</i></li><li><b>Inbox:</b> IT messages and fix confirmations</li></ul>
    <p>Employees get at most 5 notifications per device per hour; messages from IT and guides don't count towards this.</p>` },
  { id: "install", title: "Install the agent (exe / MSI)", go: "devices", tags: "install agent exe msi setup deploy add device vm service uninstall", body: `
    <p>Open <a href="#devices">Devices</a> → <b>➕ Add devices</b> to download <code>dwip-agent.exe</code>. Then, in an administrator PowerShell on the device:</p>
    <pre class="code">.\\dwip-agent.exe install --server http://&lt;dwip-host&gt;:8000 --token &lt;enrolment token&gt; --location "&lt;site&gt;"</pre>
    <p>It installs to C:\\Program Files\\DWIP, runs at start-up as SYSTEM and appears in the console within a minute. Remove it with <code>dwip-agent.exe uninstall</code>.</p>
    <p><b>MSI:</b> build it with <code>packaging\\build_agent.ps1 -Msi</code> (needs WiX), then install silently: <code>msiexec /i DWIPAgent.msi SERVER=http://host:8000 TOKEN=xyz /qn</code>.</p>
    <p>Use a server address the device can reach: <code>127.0.0.1</code> only works on the DWIP server itself.</p>` },
  { id: "azure", title: "Azure VMs", go: "devices", tags: "azure vm virtual machine cloud subscription run command onboard bastion", body: `
    <p><a href="#devices">Devices</a> → <b>☁️ Azure VMs</b> lists every VM in your subscription with its power state and whether it already reports to DWIP.</p>
    <ol><li>Sign in: <code>az login</code> on the DWIP server, or set DWIP_ENTRA_TENANT_ID, _CLIENT_ID, _CLIENT_SECRET and DWIP_AZURE_SUBSCRIPTION_ID.</li>
      <li>Tick running Windows VMs and click <b>Install agent on selected VMs</b>. Azure Run Command downloads the agent from the DWIP address you give and installs it (up to 20 VMs at a time).</li>
      <li>The VM appears as a device with its Azure region, size and resource ID.</li></ol>
    <p>Needs Reader (list) and Virtual Machine Contributor (install). The VM must be able to reach the DWIP server (VPN/ExpressRoute, or host DWIP in Azure).</p>` },
  { id: "bell", title: "Device notification box", tags: "notification bell inbox alerts offline monitored", body: `
    <p>The 🔔 at the top right shows notifications only from <b>monitored devices</b> (real agents, never demo data): new issues, alerts, fixes, devices going offline or back online, enrolments and conversations.</p>
    <p>Filter by All, Issues, Alerts, Offline or Fixes. Click an item to open the device. <i>Mark all read</i> clears the counter for you.</p>` },
  { id: "remote", title: "Remote access to a device", go: "devices", tags: "remote rdp desktop quick assist bastion connect control", body: `
    <p>Open a device and click <b>🖥️ Remote</b>. The options depend on the device:</p>
    <ul><li><b>Remote Desktop (RDP):</b> downloads a .rdp file for the device's IP. Needs RDP enabled and network reach from your PC.</li>
      <li><b>Quick Assist:</b> sends the employee a request; they press Win+Ctrl+Q and share the code with you.</li>
      <li><b>Azure Bastion:</b> for Azure VMs, opens the VM's connect page in the Azure portal.</li></ul>
    <p>Phones have no remote option. Engineers and admins only; every request is audited.</p>` },
  { id: "thresholds", title: "Alert thresholds (meters)", go: "thresholds", tags: "threshold meter saturation warning critical sustained alert level parameter app", body: `
    <p><a href="#thresholds">Proactive Monitoring → Thresholds</a> has a meter for every parameter. Green is normal, amber is past <b>Warning</b> (opens an issue), red is past <b>Critical</b> (high severity). The dark band shows where your devices are now.</p>
    <ol><li>Pick a scope: All devices, a device type (overrides global), All applications, or one app (overrides the app defaults).</li>
      <li>Drag the Warning and Critical sliders. <i>No critical</i> removes the critical level.</li>
      <li>Optional <b>Sustained</b>: minutes the value must stay past the line (CPU, memory, disk, battery), so short spikes don't alert.</li>
      <li><b>Save thresholds</b>. Each device uses them from its next report, so open issues clear or open on their own. <i>Reset this scope</i> goes back to the defaults.</li></ol>
    <p>Battery charge and battery health alert when they go <i>below</i> the line. Changes need the engineer role and are audited.</p>` },
  { id: "scripts", title: "Script library (PowerShell, Python, Batch, JavaScript)", go: "scripts", tags: "script powershell python batch javascript node query run device management app approve sha", body: `
    <ol><li>Open <a href="#scripts">Intelligent Remediation → Scripts</a>, click <b>＋ New</b>, pick the <b>Language</b> from the dropdown, choose whether it manages device settings or an application, set the risk and write the script.</li>
      <li><b>Save</b> creates a new version in <i>Draft</i>. Another engineer reads it and clicks <b>Approve this version</b>. (With sign-in on, you can't approve your own script.)</li>
      <li>Under <b>Run</b>, target one device, a device type, a location, or every device running an app. Keep <b>Dry run</b> ticked to preview, then run for real.</li>
      <li>High-risk scripts wait in <i>Runs waiting for approval</i> each time. Results, exit code and output appear in Run history; click a row to see the output.</li></ol>
    <p><b>On the device:</b> the agent runs scripts only when installed with <code>--allow-scripts</code>, checks the SHA-256 against the approved version, and stops a script after 120 s. PowerShell and Batch need Windows; Python and JavaScript need Python or Node.js installed. Phones never run scripts. Editing a script creates a new version that needs approval again. Flows can run approved scripts with the <i>Run script</i> step.</p>` },
  { id: "trouble", title: "Troubleshooting", tags: "problem error slow unicode offline fix faq", body: `
    <table><tr><th>Symptom</th><th>Fix</th></tr>
      <tr><td>Every request takes about 2 s</td><td>Use 127.0.0.1, not localhost</td></tr>
      <tr><td>Unexpected sign-in box</td><td>Hard-refresh with Ctrl+F5</td></tr>
      <tr><td>UnicodeEncodeError in the agent or simulator</td><td>Set PYTHONIOENCODING=utf-8</td></tr>
      <tr><td>"AI: rules engine (LLM offline)"</td><td>Start Ollama and pull gemma3:4b</td></tr>
      <tr><td>"Your role can't do that"</td><td>Ask an admin for a higher-role token</td></tr>
      <tr><td>Flow step "not in DWIP_FLOW_ALLOWED_HOSTS"</td><td>Add the host to that setting and restart</td></tr>
      <tr><td>Empty previous-7-days columns</td><td>Normal for the first 24 hours</td></tr></table>` },
];

const helpState = { topic: "overview" };
const plain = (html) => html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");
function helpMatches(q) {
  if (!q) return HELP.map((h) => ({ h, hits: 0 }));
  const words = q.toLowerCase().split(/\s+/).filter(Boolean);
  return HELP.map((h) => {
    const hay = `${h.title} ${h.tags} ${plain(h.body)}`.toLowerCase();
    const hits = words.every((w) => hay.includes(w)) ? words.reduce((n, w) => n + hay.split(w).length - 1 + (h.title.toLowerCase().includes(w) ? 5 : 0), 0) : 0;
    return { h, hits };
  }).filter((x) => x.hits).sort((a, b) => b.hits - a.hits);
}
function mark(html, q) {
  const words = (q || "").split(/\s+/).filter((w) => w.length > 1).map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!words.length) return html;
  const re = new RegExp(`(${words.join("|")})`, "gi");
  return html.replace(/>([^<]+)</g, (m, t) => `>${t.replace(re, "<mark>$1</mark>")}<`);
}
function renderHelp() {
  const q = $("#help-q").value.trim(), list = helpMatches(q);
  if (list.length && !list.some((x) => x.h.id === helpState.topic)) helpState.topic = list[0].h.id;
  $("#help-topics").innerHTML = list.map(({ h }) => `<button class="help-topic${h.id === helpState.topic ? " on" : ""}" data-topic="${h.id}">${esc(h.title)}</button>`).join("") ||
    `<p class="muted small">No topics match “${esc(q)}”.</p>`;
  $$(".help-topic").forEach((b) => b.onclick = () => { helpState.topic = b.dataset.topic; renderHelp(); });
  const t = HELP.find((h) => h.id === helpState.topic);
  $("#help-body").innerHTML = list.length ? `<h2>${esc(t.title)}</h2>${mark(`<div>${t.body}</div>`, q)}
    ${t.go ? `<p><a class="btn ghost" href="#${t.go}">Open this page →</a></p>` : ""}` : "";
}
$("#help-q").addEventListener("input", renderHelp);
LOADERS.help = () => { if (!$("#help-topics").children.length) renderHelp(); return Promise.resolve(); };
