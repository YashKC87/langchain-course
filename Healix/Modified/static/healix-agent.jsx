import { useState, useEffect, useRef, useCallback } from "react";

// ── API helper ──────────────────────────────────────────────────────────────
const API_BASE = "http://localhost:8000";

async function apiFetch(path, opts = {}) {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...opts.headers },
      ...opts,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    console.warn(`API fetch ${path} failed:`, e.message);
    return null;
  }
}

// ── Palette & theme ──────────────────────────────────────────────────────────
const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:ital,wght@0,400;0,700;1,400&family=Syne:wght@400;600;700;800&display=swap');

  :root {
    --bg: #060b14;
    --surface: #0d1624;
    --surface2: #111d30;
    --border: rgba(0,210,255,0.12);
    --accent: #00d2ff;
    --accent2: #7c3aed;
    --accent3: #10b981;
    --warn: #f59e0b;
    --danger: #ef4444;
    --text: #e2eaf5;
    --muted: #5a7394;
    --glow: 0 0 20px rgba(0,210,255,0.25);
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:var(--bg); color:var(--text); font-family:'Syne',sans-serif; }
  ::-webkit-scrollbar { width:4px; }
  ::-webkit-scrollbar-track { background:var(--bg); }
  ::-webkit-scrollbar-thumb { background:var(--accent); border-radius:2px; }

  .scanline {
    position:fixed; inset:0; pointer-events:none; z-index:9999;
    background: repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.03) 2px,rgba(0,0,0,0.03) 4px);
  }
  .noise {
    position:fixed; inset:0; pointer-events:none; z-index:9998; opacity:0.03;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
  }

  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
  @keyframes spin { to{transform:rotate(360deg)} }
  @keyframes slideIn { from{transform:translateY(10px);opacity:0} to{transform:translateY(0);opacity:1} }
  @keyframes blink { 0%,100%{opacity:1} 49%{opacity:1} 50%{opacity:0} 99%{opacity:0} }
  @keyframes glow-pulse { 0%,100%{box-shadow:0 0 8px rgba(0,210,255,0.3)} 50%{box-shadow:0 0 24px rgba(0,210,255,0.7)} }
  @keyframes bar-fill { from{width:0} to{width:var(--w)} }
  @keyframes ticker { 0%{transform:translateX(100%)} 100%{transform:translateX(-200%)} }
`;

// ── Fallback data ────────────────────────────────────────────────────────────
const randBetween = (a,b) => Math.floor(Math.random()*(b-a)+a);

const FALLBACK_ENDPOINTS = [
  {id:"EP-001",name:"PROD-SRV-01",os:"Windows Server 2022",status:"healthy",cpu:23,mem:61,disk:44,uptime:"99.97%"},
  {id:"EP-002",name:"PROD-SRV-02",os:"Ubuntu 22.04 LTS",status:"warning",cpu:87,mem:78,disk:72,uptime:"99.81%"},
  {id:"EP-003",name:"DEV-WS-015",os:"Windows 11 Pro",status:"healing",cpu:45,mem:55,disk:38,uptime:"98.20%"},
  {id:"EP-004",name:"DB-CLUSTER-01",os:"RHEL 9",status:"healthy",cpu:34,mem:82,disk:91,uptime:"99.99%"},
  {id:"EP-005",name:"EDGE-NODE-07",os:"Alpine Linux",status:"critical",cpu:99,mem:95,disk:60,uptime:"95.40%"},
  {id:"EP-006",name:"BACKUP-SRV",os:"Windows Server 2019",status:"healthy",cpu:12,mem:42,disk:55,uptime:"100%"},
];

const FALLBACK_ALERTS = [
  {id:1,time:"14:32:01",type:"critical",endpoint:"EDGE-NODE-07",msg:"CPU threshold exceeded (99%). Auto-remediation triggered.",resolved:false},
  {id:2,time:"14:28:45",type:"warning",endpoint:"PROD-SRV-02",msg:"Memory utilization high (78%). Monitoring escalation path.",resolved:false},
  {id:3,time:"14:15:22",type:"info",endpoint:"DEV-WS-015",msg:"Patch KB5031455 applied. Reboot scheduled at 18:00.",resolved:true},
  {id:4,time:"13:58:11",type:"success",endpoint:"PROD-SRV-01",msg:"Self-healing: IIS service restarted successfully.",resolved:true},
];

const FALLBACK_HEALING = [
  {id:"HA-001",ts:"14:32:05",endpoint:"EDGE-NODE-07",action:"Kill zombie processes",status:"running",impact:"high"},
  {id:"HA-002",ts:"14:30:11",endpoint:"PROD-SRV-02",action:"Compress memory cache",status:"completed",impact:"medium"},
  {id:"HA-003",ts:"14:15:00",endpoint:"DEV-WS-015",action:"Apply Windows patch",status:"completed",impact:"low"},
  {id:"HA-004",ts:"13:58:09",endpoint:"PROD-SRV-01",action:"Restart IIS service",status:"completed",impact:"low"},
];

const CHAT_SUGGESTIONS = [
  "Why is EDGE-NODE-07 critical?",
  "Show memory trends",
  "What patches are pending?",
  "Predict failures next 24h",
];

// ── Sub-components ────────────────────────────────────────────────────────────

const StatusDot = ({ status }) => {
  const colors = { healthy:"#10b981", warning:"#f59e0b", critical:"#ef4444", healing:"#00d2ff", info:"#6366f1" };
  const anim = status === "healing" || status === "critical" ? "pulse 1.5s infinite" : "none";
  return (
    <span style={{
      display:"inline-block", width:8, height:8, borderRadius:"50%",
      background: colors[status] || "#888",
      animation: anim,
      boxShadow: `0 0 6px ${colors[status] || "#888"}`
    }} />
  );
};

const MetricBar = ({ value, warn=70, crit=90 }) => {
  const color = value >= crit ? "var(--danger)" : value >= warn ? "var(--warn)" : "var(--accent3)";
  return (
    <div style={{ background:"rgba(255,255,255,0.06)", borderRadius:2, height:4, width:"100%", overflow:"hidden" }}>
      <div style={{
        height:"100%", width:`${value}%`, background:color,
        boxShadow:`0 0 6px ${color}`, transition:"width 0.8s ease"
      }} />
    </div>
  );
};

const Card = ({ children, style={}, glow=false }) => (
  <div style={{
    background:"var(--surface)",
    border:"1px solid var(--border)",
    borderRadius:8,
    padding:"16px",
    boxShadow: glow ? "var(--glow)" : "none",
    ...style
  }}>{children}</div>
);

const Label = ({ children, style={} }) => (
  <span style={{
    fontFamily:"'Space Mono',monospace", fontSize:10, letterSpacing:2,
    textTransform:"uppercase", color:"var(--muted)", ...style
  }}>{children}</span>
);

const Tag = ({ children, color="var(--accent)" }) => (
  <span style={{
    fontFamily:"'Space Mono',monospace", fontSize:10, padding:"2px 8px",
    borderRadius:3, border:`1px solid ${color}`, color, letterSpacing:1
  }}>{children}</span>
);

const Sparkline = ({ data, color="#00d2ff", h=32 }) => {
  const w = 120;
  if (!data?.length) return null;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const pts = data.map((v,i) => `${(i/(data.length-1))*w},${h - ((v-min)/range)*(h-4)}`).join(" ");
  return (
    <svg width={w} height={h} style={{overflow:"visible"}}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5}
        style={{filter:`drop-shadow(0 0 3px ${color})`}} />
    </svg>
  );
};

const ScoreGauge = ({ score, label, size=100 }) => {
  const color = score >= 80 ? "var(--accent3)" : score >= 50 ? "var(--warn)" : "var(--danger)";
  const r = (size - 10) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;
  return (
    <div style={{ textAlign:"center" }}>
      <svg width={size} height={size} style={{ transform:"rotate(-90deg)" }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={6} />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={6}
          strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
          style={{ transition:"stroke-dashoffset 1s ease", filter:`drop-shadow(0 0 4px ${color})` }} />
      </svg>
      <div style={{ marginTop:-size/2-10, fontWeight:800, fontSize:size/4, color }}>{score}%</div>
      <div style={{ marginTop:size/4-4 }}>
        <Label>{label}</Label>
      </div>
    </div>
  );
};

const MarkdownLite = ({ text }) => {
  const lines = text.split("\n");
  return (
    <div style={{ fontFamily:"'Space Mono',monospace", fontSize:12, lineHeight:1.8, color:"var(--text)" }}>
      {lines.map((line,i) => {
        if (!line.trim()) return <br key={i}/>;
        const bold = line.replace(/\*\*(.*?)\*\*/g, (_, m) => `<strong style="color:var(--accent)">${m}</strong>`);
        if (line.startsWith("| ")) {
          return <div key={i} style={{ borderBottom:"1px solid var(--border)", padding:"3px 0",
            display:"flex", gap:12 }}
            dangerouslySetInnerHTML={{__html: bold.replace(/\|/g,"<span style='color:var(--border)'>\u2502</span>")}} />;
        }
        return <div key={i} dangerouslySetInnerHTML={{__html: bold}} />;
      })}
    </div>
  );
};

// ════════════════════════════════════════════════════════════════════════════
export default function HealIXAgent() {
  const [tab, setTab] = useState("dashboard");
  const [alerts, setAlerts] = useState(FALLBACK_ALERTS);
  const [endpoints, setEndpoints] = useState(FALLBACK_ENDPOINTS);
  const [healingActions, setHealingActions] = useState(FALLBACK_HEALING);
  const [chatMessages, setChatMessages] = useState([
    { role:"system", text:"**HealIX \u2014 Autonomous Infrastructure Healing Platform** online.\n\nRAG + LLM hybrid engine loaded. Monitoring endpoints across environments.\nKnowledge base synced. Anomaly model: active.\n\nAsk me anything about your infrastructure \u2014 root cause, patch status, risk prediction, or remediation." }
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [sparkData] = useState(() => Array.from({length:20},()=>randBetween(20,80)));
  const [cpuHistory] = useState(() => Array.from({length:20},()=>randBetween(15,95)));
  const [memHistory] = useState(() => Array.from({length:20},()=>randBetween(40,90)));
  const [ticker] = useState(["AUTO-HEAL triggered on EDGE-NODE-07","Patch scan complete: 3 critical CVEs detected","PROD-SRV-01 uptime 99.97% \u2014 SLA met","LLM inference model v2.1 loaded","RAG knowledge base synced","Anomaly detection model running at 30s intervals"]);
  const chatEnd = useRef(null);
  const [agentThinking, setAgentThinking] = useState(false);
  const [tickerIdx, setTickerIdx] = useState(0);

  // ── New state for additional tabs ──
  const [msStatus, setMsStatus] = useState(null);
  const [threats, setThreats] = useState({ incidents: [], alerts: [] });
  const [compliance, setCompliance] = useState({ posture: null, gaps: [] });
  const [logs, setLogs] = useState({ entries: [], stats: null });
  const [logQuery, setLogQuery] = useState("");
  const [logSeverity, setLogSeverity] = useState("");
  const [monitoringData, setMonitoringData] = useState({ overview: null, anomalies: [], heartbeats: [] });
  const [usageData, setUsageData] = useState({ summary: null, adoption: null, workload: null });

  // Scroll chat
  useEffect(() => { chatEnd.current?.scrollIntoView({behavior:"smooth"}); }, [chatMessages]);

  // ── Fetch data from backend ──
  useEffect(() => {
    const load = async () => {
      const [epData, alertData, healData, healthData] = await Promise.all([
        apiFetch("/api/endpoints"),
        apiFetch("/api/alerts"),
        apiFetch("/api/healing-actions"),
        apiFetch("/health"),
      ]);
      if (epData?.endpoints?.length) {
        setEndpoints(epData.endpoints.map(ep => ({
          id: ep.id || ep.name,
          name: ep.name,
          os: ep.os || "Unknown",
          status: ep.status || "healthy",
          cpu: ep.last_cpu ?? ep.cpu ?? randBetween(20, 60),
          mem: ep.last_mem ?? ep.mem ?? randBetween(40, 70),
          disk: ep.last_disk ?? ep.disk ?? randBetween(30, 60),
          uptime: ep.uptime || "N/A",
        })));
      }
      if (alertData?.alerts?.length) {
        setAlerts(alertData.alerts.map(a => ({
          id: a.id,
          time: a.timestamp ? new Date(a.timestamp).toLocaleTimeString() : a.time || "",
          type: a.alert_type || a.type || "info",
          endpoint: a.endpoint_name || a.endpoint || "",
          msg: a.title || a.description || a.msg || "",
          resolved: a.resolved ?? false,
        })));
      }
      if (healData?.actions?.length) {
        setHealingActions(healData.actions.map(h => ({
          id: h.id || h.action_id,
          ts: h.timestamp ? new Date(h.timestamp).toLocaleTimeString() : h.ts || "",
          endpoint: h.endpoint_name || h.endpoint || "",
          action: h.action_description || h.action || "",
          status: h.status || "completed",
          impact: h.impact || "medium",
        })));
      }
      if (healthData?.services) {
        setMsStatus(healthData.services);
      }
    };
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  // Simulate live metric jitter
  useEffect(() => {
    const interval = setInterval(() => {
      setEndpoints(prev => prev.map(ep => ({
        ...ep,
        cpu: Math.min(100, Math.max(5, ep.cpu + randBetween(-5,6))),
        mem: Math.min(100, Math.max(10, ep.mem + randBetween(-3,4))),
      })));
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  // Ticker
  useEffect(() => {
    const t = setInterval(() => setTickerIdx(i => (i+1) % ticker.length), 5000);
    return () => clearInterval(t);
  }, [ticker.length]);

  // ── Load tab-specific data on tab switch ──
  useEffect(() => {
    const loadTabData = async () => {
      if (tab === "threats") {
        const [inc, sa] = await Promise.all([
          apiFetch("/api/microsoft/defender/incidents"),
          apiFetch("/api/microsoft/defender/alerts"),
        ]);
        setThreats({
          incidents: inc?.incidents || inc || [],
          alerts: sa?.alerts || sa || [],
        });
      } else if (tab === "compliance") {
        const [pos, gaps] = await Promise.all([
          apiFetch("/api/compliance/posture"),
          apiFetch("/api/compliance/gaps"),
        ]);
        setCompliance({
          posture: pos,
          gaps: gaps?.gaps || gaps || [],
        });
      } else if (tab === "logs") {
        const [logData, stats] = await Promise.all([
          apiFetch("/api/logs?limit=50"),
          apiFetch("/api/logs/stats"),
        ]);
        setLogs({
          entries: logData?.logs || logData || [],
          stats: stats,
        });
      } else if (tab === "monitoring") {
        const [ov, anom, hb] = await Promise.all([
          apiFetch("/api/monitoring/overview"),
          apiFetch("/api/monitoring/anomalies"),
          apiFetch("/api/monitoring/heartbeat"),
        ]);
        setMonitoringData({
          overview: ov,
          anomalies: anom?.anomalies || [],
          heartbeats: hb?.agents || [],
        });
      } else if (tab === "usage") {
        const [summ, adopt, wl] = await Promise.all([
          apiFetch("/api/usage/summary"),
          apiFetch("/api/usage/adoption"),
          apiFetch("/api/usage/workload"),
        ]);
        setUsageData({
          summary: summ,
          adoption: adopt,
          workload: wl,
        });
      }
    };
    loadTabData();
  }, [tab]);

  // ── Chat sends to backend ──
  const sendMessage = useCallback(async (text) => {
    const msg = text || input.trim();
    if (!msg) return;
    setInput("");
    setChatMessages(prev => [...prev, {role:"user", text:msg}]);
    setIsTyping(true);
    setAgentThinking(true);

    const data = await apiFetch("/api/agent/chat", {
      method: "POST",
      body: JSON.stringify({ question: msg }),
    });

    setIsTyping(false);
    setAgentThinking(false);

    if (data?.answer) {
      const src = data.sources?.length ? `\n\n*Sources: ${data.sources.join(", ")}*` : "";
      setChatMessages(prev => [...prev, {role:"assistant", text: data.answer + src}]);
    } else {
      setChatMessages(prev => [...prev, {
        role:"assistant",
        text: `**HealIX Analysis**\n\nProcessing query: "${msg}"\n\nRAG retrieval: scanning knowledge base...\n\u2705 Found relevant documents\n\u2705 LLM reasoning applied\n\n*Backend unavailable \u2014 showing cached response. Connect backend for live AI answers.*`
      }]);
    }
  }, [input]);

  // ── Resolve alert ──
  const resolveAlert = useCallback(async (alertId) => {
    const res = await apiFetch(`/api/alerts/${alertId}/resolve`, {
      method: "POST",
      body: JSON.stringify({ resolved_by: "dashboard_user" }),
    });
    if (res) {
      setAlerts(prev => prev.map(a => a.id === alertId ? { ...a, resolved: true } : a));
    }
  }, []);

  // ── Search logs ──
  const searchLogs = useCallback(async () => {
    const params = new URLSearchParams({ limit: "100" });
    if (logQuery) params.set("search", logQuery);
    if (logSeverity) params.set("severity", logSeverity);
    const data = await apiFetch(`/api/logs?${params}`);
    if (data?.logs) setLogs(prev => ({ ...prev, entries: data.logs }));
  }, [logQuery, logSeverity]);

  // ── Stats summary ──
  const healthyCnt = endpoints.filter(e=>e.status==="healthy").length;
  const critCnt = endpoints.filter(e=>e.status==="critical").length;
  const warnCnt = endpoints.filter(e=>e.status==="warning").length;
  const avgCpu = Math.round(endpoints.reduce((a,e)=>a+e.cpu,0)/endpoints.length);
  const avgMem = Math.round(endpoints.reduce((a,e)=>a+e.mem,0)/endpoints.length);

  // ── Tab list ──
  const TABS = ["dashboard","endpoints","healing","threats","compliance","logs","monitoring","usage","rag-agent"];
  const tabLabel = (t) => {
    const map = { "rag-agent":"AI Agent", "threats":"Threats", "compliance":"Compliance", "logs":"Logs", "monitoring":"Monitoring", "usage":"Usage" };
    return map[t] || t.charAt(0).toUpperCase() + t.slice(1);
  };

  const navBtn = (t) => ({
    padding:"8px 14px", borderRadius:4, cursor:"pointer", fontFamily:"'Space Mono',monospace",
    fontSize:10, letterSpacing:1.5, textTransform:"uppercase", border:"none",
    background: tab===t ? "var(--accent)" : "transparent",
    color: tab===t ? "var(--bg)" : "var(--muted)",
    transition:"all 0.2s",
  });

  return (
    <>
      <style>{CSS}</style>
      <div className="scanline" />
      <div className="noise" />

      <div style={{ minHeight:"100vh", background:"var(--bg)", display:"flex", flexDirection:"column" }}>

        {/* ── Header ── */}
        <header style={{
          background:"var(--surface)", borderBottom:"1px solid var(--border)",
          padding:"12px 24px", display:"flex", alignItems:"center", justifyContent:"space-between",
          position:"sticky", top:0, zIndex:100
        }}>
          <div style={{ display:"flex", alignItems:"center", gap:12 }}>
            <div style={{
              width:36, height:36, borderRadius:8,
              background:"linear-gradient(135deg,var(--accent),var(--accent2))",
              display:"flex", alignItems:"center", justifyContent:"center",
              fontSize:18, animation:"glow-pulse 2s infinite"
            }}>{"\u2B21"}</div>
            <div>
              <div style={{ fontSize:16, fontWeight:800, letterSpacing:2, color:"var(--accent)" }}>HEALIX</div>
              <div style={{ fontFamily:"'Space Mono',monospace", fontSize:9, color:"var(--muted)", letterSpacing:2 }}>
                AUTONOMOUS INFRASTRUCTURE HEALING & SECURITY OPS
              </div>
            </div>
          </div>

          <nav style={{ display:"flex", gap:2, flexWrap:"wrap" }}>
            {TABS.map(t => (
              <button key={t} style={navBtn(t)} onClick={() => setTab(t)}>
                {tabLabel(t)}
              </button>
            ))}
          </nav>

          <div style={{ display:"flex", alignItems:"center", gap:16 }}>
            <div style={{ textAlign:"right" }}>
              <div style={{ fontFamily:"'Space Mono',monospace", fontSize:10, color:"var(--accent3)" }}>
                {"\u25CF"} LIVE
              </div>
              <div style={{ fontFamily:"'Space Mono',monospace", fontSize:9, color:"var(--muted)" }}>
                {new Date().toLocaleTimeString()}
              </div>
            </div>
            {critCnt > 0 && (
              <div style={{
                background:"var(--danger)", color:"#fff", borderRadius:"50%",
                width:24, height:24, display:"flex", alignItems:"center", justifyContent:"center",
                fontSize:11, fontWeight:700, animation:"pulse 1s infinite"
              }}>{critCnt}</div>
            )}
          </div>
        </header>

        {/* ── Ticker ── */}
        <div style={{
          background:"rgba(0,210,255,0.06)", borderBottom:"1px solid var(--border)",
          padding:"6px 24px", overflow:"hidden", display:"flex", alignItems:"center", gap:16
        }}>
          <Label>Live Feed</Label>
          <div style={{ flex:1, overflow:"hidden" }}>
            <div style={{
              fontFamily:"'Space Mono',monospace", fontSize:10, color:"var(--accent)",
              animation:"slideIn 0.4s ease", key:tickerIdx
            }}>
              {"\u25B6"} {ticker[tickerIdx]}
            </div>
          </div>
          {msStatus && (
            <div style={{ display:"flex", gap:8 }}>
              {Object.entries(msStatus).map(([svc, ok]) => (
                <span key={svc} style={{
                  fontFamily:"'Space Mono',monospace", fontSize:9,
                  color: ok ? "var(--accent3)" : "var(--muted)"
                }}>{svc}: {ok ? "\u25CF" : "\u25CB"}</span>
              ))}
            </div>
          )}
        </div>

        {/* ── Main ── */}
        <main style={{ flex:1, padding:"20px 24px", overflowY:"auto" }}>

          {/* ─── DASHBOARD ─────────────────────────────────────────────── */}
          {tab === "dashboard" && (
            <div style={{ display:"flex", flexDirection:"column", gap:16 }}>

              {/* KPI row */}
              <div style={{ display:"grid", gridTemplateColumns:"repeat(5,1fr)", gap:12 }}>
                {[
                  {label:"Total Endpoints", value:endpoints.length, sub:"monitored", color:"var(--accent)"},
                  {label:"Healthy", value:healthyCnt, sub:"no issues", color:"var(--accent3)"},
                  {label:"Warnings", value:warnCnt, sub:"under watch", color:"var(--warn)"},
                  {label:"Critical", value:critCnt, sub:"action required", color:"var(--danger)"},
                  {label:"Avg CPU", value:`${avgCpu}%`, sub:"across cluster", color:"var(--accent2)"},
                ].map(({label,value,sub,color}) => (
                  <Card key={label} glow style={{ position:"relative", overflow:"hidden" }}>
                    <div style={{
                      position:"absolute", top:-10, right:-10, fontSize:48, opacity:0.04,
                      fontWeight:900, color
                    }}>{value}</div>
                    <Label>{label}</Label>
                    <div style={{ fontSize:32, fontWeight:800, color, marginTop:4 }}>{value}</div>
                    <div style={{ fontFamily:"'Space Mono',monospace", fontSize:10, color:"var(--muted)" }}>{sub}</div>
                  </Card>
                ))}
              </div>

              <div style={{ display:"grid", gridTemplateColumns:"2fr 1fr", gap:16 }}>

                {/* Endpoint overview table */}
                <Card>
                  <div style={{ display:"flex", justifyContent:"space-between", marginBottom:12 }}>
                    <Label>Endpoint Status Overview</Label>
                    <Tag>Live</Tag>
                  </div>
                  <table style={{ width:"100%", borderCollapse:"collapse" }}>
                    <thead>
                      <tr style={{ borderBottom:"1px solid var(--border)" }}>
                        {["Endpoint","OS","Status","CPU","MEM","Uptime"].map(h => (
                          <th key={h} style={{
                            fontFamily:"'Space Mono',monospace", fontSize:9, color:"var(--muted)",
                            padding:"6px 8px", textAlign:"left", letterSpacing:2, textTransform:"uppercase"
                          }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {endpoints.map(ep => (
                        <tr key={ep.id} style={{ borderBottom:"1px solid rgba(255,255,255,0.03)" }}
                          onMouseEnter={e=>e.currentTarget.style.background="rgba(0,210,255,0.04)"}
                          onMouseLeave={e=>e.currentTarget.style.background="transparent"}>
                          <td style={{ padding:"8px", fontWeight:600, fontSize:13 }}>{ep.name}</td>
                          <td style={{ padding:"8px", fontFamily:"'Space Mono',monospace", fontSize:10, color:"var(--muted)" }}>{(ep.os||"").split(" ").slice(0,2).join(" ")}</td>
                          <td style={{ padding:"8px" }}>
                            <div style={{ display:"flex", alignItems:"center", gap:6 }}>
                              <StatusDot status={ep.status} />
                              <span style={{ fontFamily:"'Space Mono',monospace", fontSize:10, textTransform:"capitalize" }}>{ep.status}</span>
                            </div>
                          </td>
                          <td style={{ padding:"8px", width:80 }}>
                            <div style={{ fontFamily:"'Space Mono',monospace", fontSize:11, marginBottom:3 }}>{ep.cpu}%</div>
                            <MetricBar value={ep.cpu} />
                          </td>
                          <td style={{ padding:"8px", width:80 }}>
                            <div style={{ fontFamily:"'Space Mono',monospace", fontSize:11, marginBottom:3 }}>{ep.mem}%</div>
                            <MetricBar value={ep.mem} warn={75} crit={90} />
                          </td>
                          <td style={{ padding:"8px", fontFamily:"'Space Mono',monospace", fontSize:11, color:"var(--accent3)" }}>{ep.uptime}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Card>

                {/* Alerts panel */}
                <Card>
                  <div style={{ display:"flex", justifyContent:"space-between", marginBottom:12 }}>
                    <Label>Recent Alerts</Label>
                    <Tag color="var(--warn)">{alerts.filter(a=>!a.resolved).length} Active</Tag>
                  </div>
                  <div style={{ display:"flex", flexDirection:"column", gap:8, maxHeight:320, overflowY:"auto" }}>
                    {alerts.map(alert => {
                      const clr = {critical:"var(--danger)",warning:"var(--warn)",info:"var(--accent)",success:"var(--accent3)"}[alert.type] || "var(--muted)";
                      return (
                        <div key={alert.id} style={{
                          padding:"10px", borderRadius:4, border:`1px solid ${clr}22`,
                          background:`${clr}08`, animation:"slideIn 0.3s ease",
                          opacity: alert.resolved ? 0.5 : 1,
                        }}>
                          <div style={{ display:"flex", justifyContent:"space-between", marginBottom:4 }}>
                            <Tag color={clr}>{alert.type}</Tag>
                            <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                              <span style={{ fontFamily:"'Space Mono',monospace", fontSize:9, color:"var(--muted)" }}>{alert.time}</span>
                              {!alert.resolved && (
                                <button onClick={() => resolveAlert(alert.id)} style={{
                                  padding:"2px 6px", borderRadius:3, background:"transparent",
                                  border:"1px solid var(--accent3)", color:"var(--accent3)",
                                  fontFamily:"'Space Mono',monospace", fontSize:8, cursor:"pointer",
                                  letterSpacing:1
                                }}>RESOLVE</button>
                              )}
                            </div>
                          </div>
                          <div style={{ fontFamily:"'Space Mono',monospace", fontSize:10, color:"var(--muted)", marginBottom:3 }}>{alert.endpoint}</div>
                          <div style={{ fontSize:12, lineHeight:1.5 }}>{alert.msg}</div>
                        </div>
                      );
                    })}
                  </div>
                </Card>
              </div>

              {/* Trend charts */}
              <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:12 }}>
                {[
                  {label:"CPU Trend (24h)", data:cpuHistory, color:"var(--accent)"},
                  {label:"Memory Trend (24h)", data:memHistory, color:"var(--accent2)"},
                  {label:"Event Frequency", data:sparkData, color:"var(--accent3)"},
                ].map(({label,data,color}) => (
                  <Card key={label}>
                    <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:12 }}>
                      <Label>{label}</Label>
                      <span style={{ fontFamily:"'Space Mono',monospace", fontSize:11, color }}>{data[data.length-1]}%</span>
                    </div>
                    <Sparkline data={data} color={color} h={48} />
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* ─── ENDPOINTS ───────────────────────────────────────────────── */}
          {tab === "endpoints" && (
            <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:16 }}>
              {endpoints.map(ep => {
                const statusColor = {healthy:"var(--accent3)",warning:"var(--warn)",critical:"var(--danger)",healing:"var(--accent)"}[ep.status] || "var(--muted)";
                return (
                  <Card key={ep.id} style={{ border:`1px solid ${statusColor}33` }} glow>
                    <div style={{ display:"flex", justifyContent:"space-between", marginBottom:12 }}>
                      <div>
                        <div style={{ fontWeight:700, fontSize:15, letterSpacing:1 }}>{ep.name}</div>
                        <div style={{ fontFamily:"'Space Mono',monospace", fontSize:10, color:"var(--muted)", marginTop:2 }}>{ep.id} {"\u00B7"} {ep.os}</div>
                      </div>
                      <div style={{ display:"flex", flexDirection:"column", alignItems:"flex-end", gap:4 }}>
                        <StatusDot status={ep.status} />
                        <Tag color={statusColor}>{ep.status}</Tag>
                      </div>
                    </div>

                    {[
                      {label:"CPU",value:ep.cpu},
                      {label:"Memory",value:ep.mem,warn:75,crit:90},
                      {label:"Disk",value:ep.disk,warn:80,crit:95}
                    ].map(({label,value,warn=70,crit=90}) => (
                      <div key={label} style={{ marginBottom:10 }}>
                        <div style={{ display:"flex", justifyContent:"space-between", marginBottom:4 }}>
                          <Label>{label}</Label>
                          <span style={{ fontFamily:"'Space Mono',monospace", fontSize:11 }}>{value}%</span>
                        </div>
                        <MetricBar value={value} warn={warn} crit={crit} />
                      </div>
                    ))}

                    <div style={{ marginTop:12, paddingTop:12, borderTop:"1px solid var(--border)", display:"flex", justifyContent:"space-between" }}>
                      <div style={{ fontFamily:"'Space Mono',monospace", fontSize:10, color:"var(--muted)" }}>Uptime</div>
                      <div style={{ fontFamily:"'Space Mono',monospace", fontSize:11, color:"var(--accent3)" }}>{ep.uptime}</div>
                    </div>

                    {ep.status !== "healthy" && (
                      <button style={{
                        marginTop:10, width:"100%", padding:"8px", borderRadius:4,
                        background:`${statusColor}18`, border:`1px solid ${statusColor}44`,
                        color: statusColor, fontFamily:"'Space Mono',monospace", fontSize:10,
                        letterSpacing:2, cursor:"pointer", textTransform:"uppercase"
                      }}>
                        {"\u2192"} Trigger Remediation
                      </button>
                    )}
                  </Card>
                );
              })}
            </div>
          )}

          {/* ─── HEALING ACTIONS ─────────────────────────────────────────── */}
          {tab === "healing" && (
            <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
              <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12 }}>
                {[
                  {label:"Total Remediated",value:"1,248",color:"var(--accent3)"},
                  {label:"Auto-Healed Today",value:"14",color:"var(--accent)"},
                  {label:"Avg Resolution Time",value:"3.2m",color:"var(--accent2)"},
                  {label:"Success Rate",value:"98.4%",color:"var(--accent3)"},
                ].map(({label,value,color}) => (
                  <Card key={label}>
                    <Label>{label}</Label>
                    <div style={{ fontSize:28, fontWeight:800, color, marginTop:4 }}>{value}</div>
                  </Card>
                ))}
              </div>

              <Card>
                <Label style={{ display:"block", marginBottom:12 }}>Self-Healing Action Log</Label>
                <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
                  {healingActions.map(ha => {
                    const statusConfig = {
                      running:{color:"var(--accent)",label:"RUNNING",anim:"pulse 1s infinite"},
                      triggered:{color:"var(--warn)",label:"TRIGGERED",anim:"pulse 1s infinite"},
                      completed:{color:"var(--accent3)",label:"DONE",anim:"none"},
                      failed:{color:"var(--danger)",label:"FAILED",anim:"none"},
                    }[ha.status] || {color:"var(--muted)",label:ha.status.toUpperCase(),anim:"none"};
                    const impactClr = {high:"var(--danger)",medium:"var(--warn)",low:"var(--accent3)"}[ha.impact] || "var(--muted)";
                    return (
                      <div key={ha.id} style={{
                        display:"grid", gridTemplateColumns:"90px 140px 1fr 80px 80px",
                        alignItems:"center", gap:12, padding:"12px 16px",
                        background:"var(--surface2)", borderRadius:6,
                        border:`1px solid ${statusConfig.color}22`,
                        animation: ha.status==="running" ? "glow-pulse 2s infinite" : "none"
                      }}>
                        <Tag color={statusConfig.color}>{statusConfig.label}</Tag>
                        <div style={{ fontFamily:"'Space Mono',monospace", fontSize:10, color:"var(--muted)" }}>
                          {ha.ts}<br/>
                          <span style={{ color:"var(--text)" }}>{ha.endpoint}</span>
                        </div>
                        <div style={{ fontSize:13, fontWeight:600 }}>{ha.action}</div>
                        <Tag color={impactClr}>{ha.impact}</Tag>
                        <div style={{ fontFamily:"'Space Mono',monospace", fontSize:9, color:"var(--muted)", textAlign:"right" }}>{ha.id}</div>
                      </div>
                    );
                  })}
                </div>
              </Card>

              <Card>
                <Label style={{ display:"block", marginBottom:12 }}>Agentic Workflow Pipeline</Label>
                <div style={{ display:"flex", alignItems:"center", gap:0 }}>
                  {[
                    {step:"1",label:"Detect",sub:"Telemetry + Anomaly ML",icon:"\u25CE",color:"var(--accent)"},
                    {step:"2",label:"Analyze",sub:"RAG + LLM Reasoning",icon:"\u2B21",color:"var(--accent2)"},
                    {step:"3",label:"Plan",sub:"Action Prioritization",icon:"\u25C8",color:"var(--warn)"},
                    {step:"4",label:"Execute",sub:"Auto-Remediation",icon:"\u25B6",color:"var(--accent3)"},
                    {step:"5",label:"Verify",sub:"Post-Fix Validation",icon:"\u2713",color:"var(--accent3)"},
                    {step:"6",label:"Learn",sub:"Update KB + Model",icon:"\u27F2",color:"var(--accent)"},
                  ].map(({step,label,sub,icon,color},i,arr) => (
                    <div key={step} style={{ display:"flex", alignItems:"center", flex:1 }}>
                      <div style={{
                        flex:1, padding:"14px 10px", background:"var(--surface2)",
                        borderRadius:6, border:`1px solid ${color}44`, textAlign:"center"
                      }}>
                        <div style={{ fontSize:20, color, marginBottom:4 }}>{icon}</div>
                        <div style={{ fontWeight:700, fontSize:12, color }}>{label}</div>
                        <div style={{ fontFamily:"'Space Mono',monospace", fontSize:9, color:"var(--muted)", marginTop:2 }}>{sub}</div>
                      </div>
                      {i < arr.length-1 && (
                        <div style={{ color:"var(--border)", fontSize:16, padding:"0 4px" }}>{"\u2192"}</div>
                      )}
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}

          {/* ─── THREATS ──────────────────────────────────────────────────── */}
          {tab === "threats" && (
            <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
              <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12 }}>
                {[
                  {label:"Active Incidents", value: threats.incidents.filter(i=>i.status!=="resolved").length, color:"var(--danger)"},
                  {label:"Total Alerts", value: threats.alerts.length, color:"var(--warn)"},
                  {label:"High Severity", value: threats.incidents.filter(i=>i.severity==="high"||i.severity==="critical").length, color:"var(--danger)"},
                  {label:"Resolved Today", value: threats.incidents.filter(i=>i.status==="resolved").length, color:"var(--accent3)"},
                ].map(({label,value,color}) => (
                  <Card key={label}>
                    <Label>{label}</Label>
                    <div style={{ fontSize:28, fontWeight:800, color, marginTop:4 }}>{value}</div>
                  </Card>
                ))}
              </div>

              <Card>
                <Label style={{ display:"block", marginBottom:12 }}>Defender XDR Incidents</Label>
                <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
                  {threats.incidents.length === 0 && (
                    <div style={{ fontFamily:"'Space Mono',monospace", fontSize:11, color:"var(--muted)", textAlign:"center", padding:20 }}>
                      No incidents found. Configure Microsoft Defender credentials to see live data.
                    </div>
                  )}
                  {threats.incidents.map((inc, idx) => {
                    const sevClr = {critical:"var(--danger)",high:"var(--danger)",medium:"var(--warn)",low:"var(--accent3)",informational:"var(--accent)"}[inc.severity] || "var(--muted)";
                    return (
                      <div key={inc.id || idx} style={{
                        padding:"12px 16px", background:"var(--surface2)", borderRadius:6,
                        border:`1px solid ${sevClr}22`, display:"grid",
                        gridTemplateColumns:"100px 1fr 100px 100px", alignItems:"center", gap:12
                      }}>
                        <Tag color={sevClr}>{(inc.severity || "unknown").toUpperCase()}</Tag>
                        <div>
                          <div style={{ fontWeight:600, fontSize:13 }}>{inc.title || inc.displayName || "Untitled"}</div>
                          <div style={{ fontFamily:"'Space Mono',monospace", fontSize:10, color:"var(--muted)", marginTop:2 }}>
                            {inc.createdDateTime ? new Date(inc.createdDateTime).toLocaleString() : ""}
                          </div>
                        </div>
                        <Tag color={inc.status==="resolved"?"var(--accent3)":"var(--warn)"}>{(inc.status || "active").toUpperCase()}</Tag>
                        <div style={{ fontFamily:"'Space Mono',monospace", fontSize:10, color:"var(--muted)", textAlign:"right" }}>
                          {inc.id || ""}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Card>

              <Card>
                <Label style={{ display:"block", marginBottom:12 }}>Security Alerts</Label>
                <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
                  {threats.alerts.slice(0, 10).map((a, idx) => {
                    const sevClr = {critical:"var(--danger)",high:"var(--danger)",medium:"var(--warn)",low:"var(--accent3)"}[a.severity] || "var(--muted)";
                    return (
                      <div key={a.id || idx} style={{
                        padding:"10px 14px", background:"var(--surface2)", borderRadius:4,
                        display:"flex", alignItems:"center", gap:12,
                        border:`1px solid ${sevClr}15`
                      }}>
                        <Tag color={sevClr}>{(a.severity || "?").toUpperCase()}</Tag>
                        <div style={{ flex:1, fontSize:12 }}>{a.title || a.displayName || ""}</div>
                        <span style={{ fontFamily:"'Space Mono',monospace", fontSize:9, color:"var(--muted)" }}>
                          {a.createdDateTime ? new Date(a.createdDateTime).toLocaleTimeString() : ""}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </Card>
            </div>
          )}

          {/* ─── COMPLIANCE ───────────────────────────────────────────────── */}
          {tab === "compliance" && (
            <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
              {compliance.posture ? (
                <>
                  <div style={{ display:"grid", gridTemplateColumns:"repeat(6,1fr)", gap:12 }}>
                    <Card glow style={{ gridColumn:"span 1" }}>
                      <ScoreGauge score={compliance.posture.overall_score ?? compliance.posture.overall ?? 0} label="Overall" size={120} />
                    </Card>
                    {["identity","device","data","app","infrastructure"].map(dim => (
                      <Card key={dim}>
                        <ScoreGauge
                          score={compliance.posture.dimensions?.[dim] ?? compliance.posture[`${dim}_score`] ?? 0}
                          label={dim.charAt(0).toUpperCase() + dim.slice(1)}
                          size={90}
                        />
                      </Card>
                    ))}
                  </div>

                  <Card>
                    <Label style={{ display:"block", marginBottom:12 }}>Compliance Gaps ({compliance.gaps.length})</Label>
                    <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
                      {compliance.gaps.length === 0 && (
                        <div style={{ fontFamily:"'Space Mono',monospace", fontSize:11, color:"var(--accent3)", textAlign:"center", padding:20 }}>
                          No compliance gaps detected. All checks passed.
                        </div>
                      )}
                      {compliance.gaps.slice(0, 15).map((gap, idx) => {
                        const statusClr = gap.status === "pass" ? "var(--accent3)" : gap.status === "fail" ? "var(--danger)" : "var(--warn)";
                        return (
                          <div key={idx} style={{
                            padding:"10px 14px", background:"var(--surface2)", borderRadius:4,
                            display:"flex", alignItems:"center", gap:12
                          }}>
                            <Tag color={statusClr}>{(gap.status || "fail").toUpperCase()}</Tag>
                            <div style={{ flex:1 }}>
                              <div style={{ fontSize:12, fontWeight:600 }}>{gap.check_type || gap.title || ""}</div>
                              <div style={{ fontFamily:"'Space Mono',monospace", fontSize:10, color:"var(--muted)", marginTop:2 }}>
                                {gap.scope || ""} {gap.remediation_suggestion ? `\u2014 ${gap.remediation_suggestion}` : ""}
                              </div>
                            </div>
                            <span style={{ fontFamily:"'Space Mono',monospace", fontSize:11, color:statusClr, fontWeight:700 }}>
                              {gap.score != null ? `${gap.score}%` : ""}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </Card>
                </>
              ) : (
                <Card>
                  <div style={{ textAlign:"center", padding:40, fontFamily:"'Space Mono',monospace", fontSize:12, color:"var(--muted)" }}>
                    Loading compliance data... Configure Microsoft integrations for real posture assessment.
                  </div>
                </Card>
              )}
            </div>
          )}

          {/* ─── LOGS ─────────────────────────────────────────────────────── */}
          {tab === "logs" && (
            <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
              {/* Log stats */}
              {logs.stats && (
                <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12 }}>
                  {[
                    {label:"Total Logs", value: logs.stats.total_logs ?? logs.stats.total ?? 0, color:"var(--accent)"},
                    {label:"Critical", value: logs.stats.severity_breakdown?.critical ?? logs.stats.critical ?? 0, color:"var(--danger)"},
                    {label:"Warnings", value: logs.stats.severity_breakdown?.warning ?? logs.stats.warning ?? 0, color:"var(--warn)"},
                    {label:"Sources", value: logs.stats.source_count ?? Object.keys(logs.stats.source_breakdown || {}).length ?? 0, color:"var(--accent2)"},
                  ].map(({label,value,color}) => (
                    <Card key={label}>
                      <Label>{label}</Label>
                      <div style={{ fontSize:28, fontWeight:800, color, marginTop:4 }}>{value}</div>
                    </Card>
                  ))}
                </div>
              )}

              {/* Search bar */}
              <Card>
                <div style={{ display:"flex", gap:8, alignItems:"center" }}>
                  <input
                    value={logQuery}
                    onChange={e => setLogQuery(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && searchLogs()}
                    placeholder="Search logs..."
                    style={{
                      flex:1, padding:"8px 12px", borderRadius:4,
                      background:"var(--surface2)", border:"1px solid var(--border)",
                      color:"var(--text)", fontFamily:"'Space Mono',monospace", fontSize:11, outline:"none"
                    }}
                  />
                  <select
                    value={logSeverity}
                    onChange={e => setLogSeverity(e.target.value)}
                    style={{
                      padding:"8px 12px", borderRadius:4,
                      background:"var(--surface2)", border:"1px solid var(--border)",
                      color:"var(--text)", fontFamily:"'Space Mono',monospace", fontSize:11, outline:"none"
                    }}
                  >
                    <option value="">All Severities</option>
                    <option value="critical">Critical</option>
                    <option value="warning">Warning</option>
                    <option value="info">Info</option>
                    <option value="debug">Debug</option>
                  </select>
                  <button onClick={searchLogs} style={{
                    padding:"8px 16px", borderRadius:4,
                    background:"var(--accent)", border:"none", color:"var(--bg)",
                    fontFamily:"'Space Mono',monospace", fontSize:10, letterSpacing:1,
                    cursor:"pointer", fontWeight:700
                  }}>SEARCH</button>
                </div>
              </Card>

              {/* Log table */}
              <Card>
                <Label style={{ display:"block", marginBottom:12 }}>Log Entries ({logs.entries.length})</Label>
                <div style={{ maxHeight:500, overflowY:"auto" }}>
                  <table style={{ width:"100%", borderCollapse:"collapse" }}>
                    <thead>
                      <tr style={{ borderBottom:"1px solid var(--border)" }}>
                        {["Time","Source","Severity","Endpoint","Message"].map(h => (
                          <th key={h} style={{
                            fontFamily:"'Space Mono',monospace", fontSize:9, color:"var(--muted)",
                            padding:"6px 8px", textAlign:"left", letterSpacing:2, textTransform:"uppercase",
                            position:"sticky", top:0, background:"var(--surface)"
                          }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {logs.entries.length === 0 && (
                        <tr><td colSpan={5} style={{ textAlign:"center", padding:30, fontFamily:"'Space Mono',monospace", fontSize:11, color:"var(--muted)" }}>
                          No logs found. Logs appear here after the backend collection cycle runs.
                        </td></tr>
                      )}
                      {logs.entries.map((log, idx) => {
                        const sevClr = {critical:"var(--danger)",warning:"var(--warn)",info:"var(--accent)",debug:"var(--muted)"}[log.severity] || "var(--muted)";
                        return (
                          <tr key={idx} style={{ borderBottom:"1px solid rgba(255,255,255,0.03)" }}>
                            <td style={{ padding:"6px 8px", fontFamily:"'Space Mono',monospace", fontSize:10, color:"var(--muted)", whiteSpace:"nowrap" }}>
                              {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : ""}
                            </td>
                            <td style={{ padding:"6px 8px", fontFamily:"'Space Mono',monospace", fontSize:10 }}>{log.source || ""}</td>
                            <td style={{ padding:"6px 8px" }}><Tag color={sevClr}>{(log.severity || "").toUpperCase()}</Tag></td>
                            <td style={{ padding:"6px 8px", fontFamily:"'Space Mono',monospace", fontSize:10 }}>{log.endpoint_name || ""}</td>
                            <td style={{ padding:"6px 8px", fontSize:11, maxWidth:400, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                              {log.message || ""}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </Card>
            </div>
          )}

          {/* ─── MONITORING ───────────────────────────────────────────────── */}
          {tab === "monitoring" && (
            <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
              {/* Overview KPIs */}
              {monitoringData.overview && (
                <div style={{ display:"grid", gridTemplateColumns:"repeat(5,1fr)", gap:12 }}>
                  {[
                    {label:"Endpoints", value: monitoringData.overview.total_endpoints ?? endpoints.length, color:"var(--accent)"},
                    {label:"Healthy", value: monitoringData.overview.healthy ?? healthyCnt, color:"var(--accent3)"},
                    {label:"Warning", value: monitoringData.overview.warning ?? warnCnt, color:"var(--warn)"},
                    {label:"Critical", value: monitoringData.overview.critical ?? critCnt, color:"var(--danger)"},
                    {label:"Avg CPU", value: `${monitoringData.overview.avg_cpu ?? avgCpu}%`, color:"var(--accent2)"},
                  ].map(({label,value,color}) => (
                    <Card key={label}>
                      <Label>{label}</Label>
                      <div style={{ fontSize:28, fontWeight:800, color, marginTop:4 }}>{value}</div>
                    </Card>
                  ))}
                </div>
              )}

              {/* Endpoint grid */}
              <Card>
                <Label style={{ display:"block", marginBottom:12 }}>Real-Time Endpoint Metrics</Label>
                <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:12 }}>
                  {endpoints.map(ep => {
                    const statusColor = {healthy:"var(--accent3)",warning:"var(--warn)",critical:"var(--danger)",healing:"var(--accent)"}[ep.status] || "var(--muted)";
                    return (
                      <div key={ep.id} style={{
                        padding:"12px", background:"var(--surface2)", borderRadius:6,
                        border:`1px solid ${statusColor}22`
                      }}>
                        <div style={{ display:"flex", justifyContent:"space-between", marginBottom:8 }}>
                          <div style={{ fontWeight:700, fontSize:13 }}>{ep.name}</div>
                          <StatusDot status={ep.status} />
                        </div>
                        {[{l:"CPU",v:ep.cpu},{l:"MEM",v:ep.mem},{l:"DISK",v:ep.disk}].map(({l,v}) => (
                          <div key={l} style={{ marginBottom:6 }}>
                            <div style={{ display:"flex", justifyContent:"space-between", marginBottom:2 }}>
                              <Label>{l}</Label>
                              <span style={{ fontFamily:"'Space Mono',monospace", fontSize:10 }}>{v}%</span>
                            </div>
                            <MetricBar value={v} warn={l==="DISK"?80:70} crit={l==="DISK"?95:90} />
                          </div>
                        ))}
                      </div>
                    );
                  })}
                </div>
              </Card>

              {/* Anomalies */}
              <Card>
                <Label style={{ display:"block", marginBottom:12 }}>Detected Anomalies ({monitoringData.anomalies.length})</Label>
                <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
                  {monitoringData.anomalies.length === 0 && (
                    <div style={{ fontFamily:"'Space Mono',monospace", fontSize:11, color:"var(--accent3)", textAlign:"center", padding:20 }}>
                      No anomalies detected. All metrics within normal thresholds.
                    </div>
                  )}
                  {monitoringData.anomalies.map((a, idx) => (
                    <div key={idx} style={{
                      padding:"10px 14px", background:"var(--surface2)", borderRadius:4,
                      display:"flex", alignItems:"center", gap:12,
                      border:"1px solid var(--danger)22"
                    }}>
                      <Tag color="var(--danger)">ANOMALY</Tag>
                      <div style={{ flex:1 }}>
                        <span style={{ fontWeight:600 }}>{a.endpoint || ""}</span>
                        <span style={{ fontFamily:"'Space Mono',monospace", fontSize:10, color:"var(--muted)", marginLeft:8 }}>
                          {a.metric || ""} = {a.current_value ?? ""} (threshold: {a.threshold ?? ""})
                        </span>
                      </div>
                      <span style={{ fontFamily:"'Space Mono',monospace", fontSize:10, color:"var(--danger)" }}>
                        z-score: {a.z_score?.toFixed(1) ?? ""}
                      </span>
                    </div>
                  ))}
                </div>
              </Card>

              {/* Heartbeat */}
              {monitoringData.heartbeats.length > 0 && (
                <Card>
                  <Label style={{ display:"block", marginBottom:12 }}>Agent Heartbeats</Label>
                  <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:8 }}>
                    {monitoringData.heartbeats.map((hb, idx) => (
                      <div key={idx} style={{
                        padding:"10px", background:"var(--surface2)", borderRadius:4,
                        border:`1px solid ${hb.status==="healthy"?"var(--accent3)":"var(--danger)"}33`,
                        textAlign:"center"
                      }}>
                        <StatusDot status={hb.status || "healthy"} />
                        <div style={{ fontWeight:600, fontSize:12, marginTop:4 }}>{hb.name || hb.endpoint || ""}</div>
                        <div style={{ fontFamily:"'Space Mono',monospace", fontSize:9, color:"var(--muted)", marginTop:2 }}>
                          Last: {hb.last_heartbeat ? new Date(hb.last_heartbeat).toLocaleTimeString() : "N/A"}
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </div>
          )}

          {/* ─── USAGE ────────────────────────────────────────────────────── */}
          {tab === "usage" && (
            <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
              {usageData.summary ? (
                <>
                  <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12 }}>
                    {[
                      {label:"Total Queries", value: usageData.summary.total_queries ?? usageData.summary.total ?? 0, color:"var(--accent)"},
                      {label:"Avg Response", value: `${(usageData.summary.avg_response_ms ?? usageData.summary.avg_latency ?? 0).toFixed(0)}ms`, color:"var(--accent2)"},
                      {label:"Total Tokens", value: usageData.summary.total_tokens ?? 0, color:"var(--warn)"},
                      {label:"Est. Cost", value: `$${(usageData.summary.estimated_cost_usd ?? 0).toFixed(2)}`, color:"var(--accent3)"},
                    ].map(({label,value,color}) => (
                      <Card key={label}>
                        <Label>{label}</Label>
                        <div style={{ fontSize:28, fontWeight:800, color, marginTop:4 }}>{value}</div>
                      </Card>
                    ))}
                  </div>

                  {/* Service breakdown */}
                  {usageData.workload && (
                    <Card>
                      <Label style={{ display:"block", marginBottom:12 }}>Workload Distribution</Label>
                      <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(180px,1fr))", gap:8 }}>
                        {(usageData.workload.services || usageData.workload.breakdown || []).map((svc, idx) => (
                          <div key={idx} style={{
                            padding:"12px", background:"var(--surface2)", borderRadius:4,
                            textAlign:"center"
                          }}>
                            <div style={{ fontWeight:600, fontSize:13 }}>{svc.service || svc.name || ""}</div>
                            <div style={{ fontFamily:"'Space Mono',monospace", fontSize:20, fontWeight:800, color:"var(--accent)", marginTop:4 }}>
                              {svc.count ?? svc.queries ?? 0}
                            </div>
                            <Label>queries</Label>
                          </div>
                        ))}
                      </div>
                    </Card>
                  )}

                  {/* Adoption metrics */}
                  {usageData.adoption && (
                    <Card>
                      <Label style={{ display:"block", marginBottom:12 }}>Adoption Metrics</Label>
                      <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:12 }}>
                        {[
                          {label:"Active Users", value: usageData.adoption.active_users ?? 0, color:"var(--accent)"},
                          {label:"Feature Adoption", value: `${usageData.adoption.feature_adoption ?? 0}%`, color:"var(--accent3)"},
                          {label:"Automation Rate", value: `${usageData.adoption.automation_rate ?? 0}%`, color:"var(--accent2)"},
                        ].map(({label,value,color}) => (
                          <div key={label} style={{ textAlign:"center", padding:16, background:"var(--surface2)", borderRadius:6 }}>
                            <div style={{ fontSize:24, fontWeight:800, color }}>{value}</div>
                            <Label>{label}</Label>
                          </div>
                        ))}
                      </div>
                    </Card>
                  )}
                </>
              ) : (
                <Card>
                  <div style={{ textAlign:"center", padding:40, fontFamily:"'Space Mono',monospace", fontSize:12, color:"var(--muted)" }}>
                    Loading usage analytics... Data populates as the platform is used.
                  </div>
                </Card>
              )}
            </div>
          )}

          {/* ─── RAG AGENT ───────────────────────────────────────────────── */}
          {tab === "rag-agent" && (
            <div style={{ display:"grid", gridTemplateColumns:"2fr 1fr", gap:16, height:"calc(100vh - 160px)" }}>

              {/* Chat */}
              <Card style={{ display:"flex", flexDirection:"column", height:"100%" }}>
                <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:12 }}>
                  <div>
                    <Label>HealIX AI Agent</Label>
                    <div style={{ fontFamily:"'Space Mono',monospace", fontSize:9, color:"var(--accent3)", marginTop:2 }}>
                      {"\u25CF"} RAG+LLM HYBRID {"\u00B7"} CONNECTED TO BACKEND
                    </div>
                  </div>
                  {agentThinking && (
                    <div style={{ display:"flex", alignItems:"center", gap:6, color:"var(--accent)" }}>
                      <div style={{ width:12, height:12, border:"2px solid var(--accent)", borderTopColor:"transparent", borderRadius:"50%", animation:"spin 0.8s linear infinite" }} />
                      <span style={{ fontFamily:"'Space Mono',monospace", fontSize:10 }}>Thinking...</span>
                    </div>
                  )}
                </div>

                {/* Messages */}
                <div style={{ flex:1, overflowY:"auto", display:"flex", flexDirection:"column", gap:12, paddingRight:4 }}>
                  {chatMessages.map((msg,i) => (
                    <div key={i} style={{
                      alignSelf: msg.role==="user" ? "flex-end" : "flex-start",
                      maxWidth:"85%",
                      animation:"slideIn 0.3s ease"
                    }}>
                      {msg.role !== "user" && (
                        <div style={{ fontFamily:"'Space Mono',monospace", fontSize:9, color:"var(--accent)", marginBottom:4 }}>
                          {"\u2B21"} HEALIX
                        </div>
                      )}
                      <div style={{
                        padding:"12px 16px", borderRadius: msg.role==="user" ? "12px 12px 2px 12px" : "2px 12px 12px 12px",
                        background: msg.role==="user" ? "linear-gradient(135deg,var(--accent2),var(--accent))" : "var(--surface2)",
                        border: msg.role==="user" ? "none" : "1px solid var(--border)",
                        boxShadow: msg.role==="user" ? "var(--glow)" : "none"
                      }}>
                        <MarkdownLite text={msg.text} />
                      </div>
                    </div>
                  ))}
                  {isTyping && (
                    <div style={{ display:"flex", gap:4, padding:"12px 16px", background:"var(--surface2)", borderRadius:"2px 12px 12px", width:80 }}>
                      {[0,1,2].map(i => (
                        <div key={i} style={{ width:6, height:6, borderRadius:"50%", background:"var(--accent)", animation:`pulse 1.2s ${i*0.2}s infinite` }} />
                      ))}
                    </div>
                  )}
                  <div ref={chatEnd} />
                </div>

                {/* Suggestions */}
                <div style={{ display:"flex", gap:8, marginTop:12, flexWrap:"wrap" }}>
                  {CHAT_SUGGESTIONS.map(s => (
                    <button key={s} onClick={() => sendMessage(s)} style={{
                      padding:"4px 10px", borderRadius:4, background:"transparent",
                      border:"1px solid var(--border)", color:"var(--muted)",
                      fontFamily:"'Space Mono',monospace", fontSize:10, cursor:"pointer",
                      transition:"all 0.2s"
                    }}
                      onMouseEnter={e=>{e.target.style.borderColor="var(--accent)";e.target.style.color="var(--accent)"}}
                      onMouseLeave={e=>{e.target.style.borderColor="var(--border)";e.target.style.color="var(--muted)"}}>
                      {s}
                    </button>
                  ))}
                </div>

                {/* Input */}
                <div style={{ display:"flex", gap:8, marginTop:10 }}>
                  <input
                    value={input}
                    onChange={e=>setInput(e.target.value)}
                    onKeyDown={e=>e.key==="Enter"&&sendMessage()}
                    placeholder="Ask the AI agent anything about your infrastructure..."
                    style={{
                      flex:1, padding:"10px 14px", borderRadius:6,
                      background:"var(--surface2)", border:"1px solid var(--border)",
                      color:"var(--text)", fontFamily:"'Space Mono',monospace", fontSize:12,
                      outline:"none"
                    }}
                  />
                  <button onClick={()=>sendMessage()} style={{
                    padding:"10px 20px", borderRadius:6,
                    background:"linear-gradient(135deg,var(--accent2),var(--accent))",
                    border:"none", color:"#fff", fontFamily:"'Space Mono',monospace",
                    fontSize:11, letterSpacing:1, cursor:"pointer", fontWeight:700
                  }}>SEND</button>
                </div>
              </Card>

              {/* RAG Architecture panel */}
              <div style={{ display:"flex", flexDirection:"column", gap:12 }}>
                <Card>
                  <Label style={{ display:"block", marginBottom:10 }}>RAG Architecture</Label>
                  {[
                    {layer:"Data Ingestion", items:["Telemetry streams","SIEM logs","CMDB/ITSM","CVE databases"], color:"var(--accent)"},
                    {layer:"Vector Store", items:["Knowledge base docs","Embedding model","Semantic retrieval"], color:"var(--accent2)"},
                    {layer:"LLM Reasoning", items:["Contextual analysis","Action planning","Root cause inference"], color:"var(--warn)"},
                    {layer:"Agent Actions", items:["Tool calling","Auto-remediation","Escalation"], color:"var(--accent3)"},
                  ].map(({layer,items,color}) => (
                    <div key={layer} style={{ marginBottom:10, paddingBottom:10, borderBottom:"1px solid var(--border)" }}>
                      <div style={{ fontWeight:700, fontSize:12, color, marginBottom:4 }}>{layer}</div>
                      {items.map(it => (
                        <div key={it} style={{ fontFamily:"'Space Mono',monospace", fontSize:10, color:"var(--muted)", padding:"1px 0" }}>
                          {"\u00B7"} {it}
                        </div>
                      ))}
                    </div>
                  ))}
                </Card>

                <Card>
                  <Label style={{ display:"block", marginBottom:10 }}>System Info</Label>
                  {[
                    {k:"Backend",v:"HEALIX v2.0"},
                    {k:"AI Model",v:"GPT-4o-mini"},
                    {k:"RAG Engine",v:"LangChain + FAISS"},
                    {k:"Integrations",v:"Defender, Sentinel, Intune, Entra"},
                    {k:"Auto-resolve rate",v:"78.6%"},
                    {k:"Polling interval",v:"60s"},
                  ].map(({k,v}) => (
                    <div key={k} style={{
                      display:"flex", justifyContent:"space-between",
                      fontFamily:"'Space Mono',monospace", fontSize:10,
                      padding:"5px 0", borderBottom:"1px solid var(--border)"
                    }}>
                      <span style={{ color:"var(--muted)" }}>{k}</span>
                      <span style={{ color:"var(--accent)" }}>{v}</span>
                    </div>
                  ))}
                </Card>
              </div>
            </div>
          )}
        </main>
      </div>
    </>
  );
}
