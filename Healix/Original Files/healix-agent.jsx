import { useState, useEffect, useRef, useCallback } from "react";

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

// ── Fake data generators ─────────────────────────────────────────────────────
const randBetween = (a,b) => Math.floor(Math.random()*(b-a)+a);
const randFloat = (a,b) => (Math.random()*(b-a)+a).toFixed(1);

const ENDPOINTS = [
  {id:"EP-001",name:"PROD-SRV-01",os:"Windows Server 2022",status:"healthy",cpu:23,mem:61,disk:44,uptime:"99.97%"},
  {id:"EP-002",name:"PROD-SRV-02",os:"Ubuntu 22.04 LTS",status:"warning",cpu:87,mem:78,disk:72,uptime:"99.81%"},
  {id:"EP-003",name:"DEV-WS-015",os:"Windows 11 Pro",status:"healing",cpu:45,mem:55,disk:38,uptime:"98.20%"},
  {id:"EP-004",name:"DB-CLUSTER-01",os:"RHEL 9",status:"healthy",cpu:34,mem:82,disk:91,uptime:"99.99%"},
  {id:"EP-005",name:"EDGE-NODE-07",os:"Alpine Linux",status:"critical",cpu:99,mem:95,disk:60,uptime:"95.40%"},
  {id:"EP-006",name:"BACKUP-SRV",os:"Windows Server 2019",status:"healthy",cpu:12,mem:42,disk:55,uptime:"100%"},
];

const INITIAL_ALERTS = [
  {id:1,time:"14:32:01",type:"critical",endpoint:"EDGE-NODE-07",msg:"CPU threshold exceeded (99%). Auto-remediation triggered.",resolved:false},
  {id:2,time:"14:28:45",type:"warning",endpoint:"PROD-SRV-02",msg:"Memory utilization high (78%). Monitoring escalation path.",resolved:false},
  {id:3,time:"14:15:22",type:"info",endpoint:"DEV-WS-015",msg:"Patch KB5031455 applied. Reboot scheduled at 18:00.",resolved:true},
  {id:4,time:"13:58:11",type:"success",endpoint:"PROD-SRV-01",msg:"Self-healing: IIS service restarted successfully.",resolved:true},
  {id:5,time:"13:44:00",type:"info",endpoint:"DB-CLUSTER-01",msg:"Disk I/O spike detected. Root cause: scheduled backup.",resolved:true},
];

const HEALING_ACTIONS = [
  {id:"HA-001",ts:"14:32:05",endpoint:"EDGE-NODE-07",action:"Kill zombie processes",status:"running",impact:"high"},
  {id:"HA-002",ts:"14:30:11",endpoint:"PROD-SRV-02",action:"Compress memory cache",status:"completed",impact:"medium"},
  {id:"HA-003",ts:"14:15:00",endpoint:"DEV-WS-015",action:"Apply Windows patch",status:"completed",impact:"low"},
  {id:"HA-004",ts:"13:58:09",endpoint:"PROD-SRV-01",action:"Restart IIS service",status:"completed",impact:"low"},
  {id:"HA-005",ts:"13:21:33",endpoint:"DB-CLUSTER-01",action:"Throttle backup I/O",status:"completed",impact:"medium"},
];

const RAG_RESPONSES = {
  default: [
    {
      q: "why is edge node 7 critical",
      a: `**Root Cause Analysis — EDGE-NODE-07**\n\nRAG retrieval from knowledge base + telemetry logs:\n\n• **CPU spike to 99%** triggered at 14:31:58 UTC\n• Pattern matched: *runaway Node.js process* (seen 3x in past 90 days on this endpoint)\n• **Contributing factor:** Memory leak in app v2.3.1 causing GC pressure\n\n**Agentic Action Plan:**\n1. ✅ Killed zombie PID 4821, 4822 (auto-triggered)\n2. 🔄 Restarting application service (in progress)\n3. 📋 Flagged for app v2.3.2 patch deployment\n\n**Predicted recovery:** ~4 minutes`
    },
    {
      q: "show memory trends",
      a: `**Memory Trend Analysis — Last 24h**\n\nLLM inference on collected telemetry:\n\n• **Cluster average:** 68.2% (↑8% vs yesterday)\n• **Anomaly detected:** DB-CLUSTER-01 holding 82% — normal for end-of-month reporting\n• **Risk endpoint:** PROD-SRV-02 trajectory shows **OOM risk in ~2h** without intervention\n\n**Recommended actions:**\n1. Scale PROD-SRV-02 memory headroom (+4GB)\n2. Schedule non-critical service restart at 15:00\n3. Enable swap watchdog on all Linux nodes`
    },
    {
      q: "what patches are pending",
      a: `**Patch Intelligence Report**\n\nRAG-powered KB scan + CVE database lookup:\n\n| Endpoint | Patch | Severity | CVSS |\n|---|---|---|---|\n| DEV-WS-015 | KB5031455 | Medium | 5.6 |\n| PROD-SRV-02 | OpenSSL 3.1.4 | **Critical** | **9.1** |\n| EDGE-NODE-07 | Node.js 20.9.0 | High | 7.5 |\n\n⚠️ **OpenSSL patch on PROD-SRV-02 is URGENT** — active exploit in wild.\n\n**Auto-schedule options:**\n• Tonight 02:00 UTC (recommended)\n• Manual approval workflow`
    },
    {
      q: "predict failures next 24h",
      a: `**Predictive Failure Analysis — Next 24h**\n\nML model (LSTM + anomaly scoring) on 90-day baseline:\n\n🔴 **EDGE-NODE-07** — 94% failure probability\n   *Reason: Recurring OOM cycle, degraded hardware signal*\n\n🟡 **DB-CLUSTER-01** — 41% risk\n   *Reason: Disk at 91%, nearing threshold*\n\n🟢 **All others** — <12% risk\n\n**Recommended pre-emptive actions:**\n1. Provision failover for EDGE-NODE-07\n2. Archive old DB logs (free ~15% disk)\n3. Increase monitoring frequency to 30s intervals`
    }
  ]
};

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

// ── Sparkline ─────────────────────────────────────────────────────────────────
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

// ── AI Chat ───────────────────────────────────────────────────────────────────
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
            dangerouslySetInnerHTML={{__html: bold.replace(/\|/g,"<span style='color:var(--border)'>│</span>")}} />;
        }
        return <div key={i} dangerouslySetInnerHTML={{__html: bold}} />;
      })}
    </div>
  );
};

// ════════════════════════════════════════════════════════════════════════════
export default function HealIXAgent() {
  const [tab, setTab] = useState("dashboard");
  const [alerts, setAlerts] = useState(INITIAL_ALERTS);
  const [endpoints, setEndpoints] = useState(ENDPOINTS);
  const [healingActions, setHealingActions] = useState(HEALING_ACTIONS);
  const [chatMessages, setChatMessages] = useState([
    { role:"system", text:"**HealIX — Autonomous Infrastructure Healing Platform** online.\n\nRAG + LLM hybrid engine loaded. Monitoring **6 endpoints** across 3 environments.\nKnowledge base synced: 4,821 documents · Anomaly model: active.\n\nAsk me anything about your infrastructure — root cause, patch status, risk prediction, or remediation." }
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [sparkData] = useState(() => Array.from({length:20},()=>randBetween(20,80)));
  const [cpuHistory] = useState(() => Array.from({length:20},()=>randBetween(15,95)));
  const [memHistory] = useState(() => Array.from({length:20},()=>randBetween(40,90)));
  const [ticker] = useState(["AUTO-HEAL triggered on EDGE-NODE-07","Patch scan complete: 3 critical CVEs detected","PROD-SRV-01 uptime 99.97% — SLA met","LLM inference model v2.1 loaded","RAG knowledge base synced: 4,821 documents","Anomaly detection model running at 30s intervals"]);
  const chatEnd = useRef(null);
  const [agentThinking, setAgentThinking] = useState(false);
  const [tickerIdx, setTickerIdx] = useState(0);

  // Scroll chat
  useEffect(() => { chatEnd.current?.scrollIntoView({behavior:"smooth"}); }, [chatMessages]);

  // Simulate live metrics
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

  const sendMessage = useCallback(async (text) => {
    const msg = text || input.trim();
    if (!msg) return;
    setInput("");
    setChatMessages(prev => [...prev, {role:"user", text:msg}]);
    setIsTyping(true);
    setAgentThinking(true);

    // Find RAG response
    const lower = msg.toLowerCase();
    const all = RAG_RESPONSES.default;
    let matched = all.find(r => lower.includes(r.q.split(" ")[0]) || r.q.split(" ").some(w => lower.includes(w)));

    await new Promise(r => setTimeout(r, 1800 + Math.random()*1200));
    setIsTyping(false);
    setAgentThinking(false);

    const response = matched ? matched.a :
      `**HealIX Analysis**\n\nProcessing query: "${msg}"\n\nRAG retrieval: scanning knowledge base...\n✅ Found 12 relevant documents\n✅ LLM reasoning applied\n\n*This query requires deeper investigation. I've flagged it for the operations team and will escalate if auto-remediation patterns match.*\n\n**Suggested actions:** Run diagnostics on affected endpoints, review recent change logs.`;

    setChatMessages(prev => [...prev, {role:"assistant", text:response}]);
  }, [input]);

  // ── Stats summary ────────────────────────────────────────────────────────
  const healthyCnt = endpoints.filter(e=>e.status==="healthy").length;
  const critCnt = endpoints.filter(e=>e.status==="critical").length;
  const warnCnt = endpoints.filter(e=>e.status==="warning").length;
  const avgCpu = Math.round(endpoints.reduce((a,e)=>a+e.cpu,0)/endpoints.length);
  const avgMem = Math.round(endpoints.reduce((a,e)=>a+e.mem,0)/endpoints.length);

  // ── Styles ────────────────────────────────────────────────────────────────
  const navBtn = (t) => ({
    padding:"8px 20px", borderRadius:4, cursor:"pointer", fontFamily:"'Space Mono',monospace",
    fontSize:11, letterSpacing:2, textTransform:"uppercase", border:"none",
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
            }}>⬡</div>
            <div>
              <div style={{ fontSize:16, fontWeight:800, letterSpacing:2, color:"var(--accent)" }}>HEALIX</div>
              <div style={{ fontFamily:"'Space Mono',monospace", fontSize:9, color:"var(--muted)", letterSpacing:2 }}>
                AUTONOMOUS INFRASTRUCTURE HEALING PLATFORM · RAG+LLM
              </div>
            </div>
          </div>

          <nav style={{ display:"flex", gap:4 }}>
            {["dashboard","endpoints","healing","rag-agent"].map(t => (
              <button key={t} style={navBtn(t)} onClick={() => setTab(t)}>
                {t==="rag-agent"?"AI Agent":t}
              </button>
            ))}
          </nav>

          <div style={{ display:"flex", alignItems:"center", gap:16 }}>
            <div style={{ textAlign:"right" }}>
              <div style={{ fontFamily:"'Space Mono',monospace", fontSize:10, color:"var(--accent3)" }}>
                ● LIVE
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
              ▶ {ticker[tickerIdx]}
            </div>
          </div>
        </div>

        {/* ── Main ── */}
        <main style={{ flex:1, padding:"20px 24px", overflowY:"auto" }}>

          {/* ─── DASHBOARD ─────────────────────────────────────────────── */}
          {tab === "dashboard" && (
            <div style={{ display:"flex", flexDirection:"column", gap:16 }}>

              {/* KPI row */}
              <div style={{ display:"grid", gridTemplateColumns:"repeat(5,1fr)", gap:12 }}>
                {[
                  {label:"Total Endpoints", value:"6", sub:"monitored", color:"var(--accent)"},
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
                          <td style={{ padding:"8px", fontFamily:"'Space Mono',monospace", fontSize:10, color:"var(--muted)" }}>{ep.os.split(" ").slice(0,2).join(" ")}</td>
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
                      const clr = {critical:"var(--danger)",warning:"var(--warn)",info:"var(--accent)",success:"var(--accent3)"}[alert.type];
                      return (
                        <div key={alert.id} style={{
                          padding:"10px", borderRadius:4, border:`1px solid ${clr}22`,
                          background:`${clr}08`, animation:"slideIn 0.3s ease"
                        }}>
                          <div style={{ display:"flex", justifyContent:"space-between", marginBottom:4 }}>
                            <Tag color={clr}>{alert.type}</Tag>
                            <span style={{ fontFamily:"'Space Mono',monospace", fontSize:9, color:"var(--muted)" }}>{alert.time}</span>
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
                const statusColor = {healthy:"var(--accent3)",warning:"var(--warn)",critical:"var(--danger)",healing:"var(--accent)"}[ep.status];
                return (
                  <Card key={ep.id} style={{ border:`1px solid ${statusColor}33` }} glow>
                    <div style={{ display:"flex", justifyContent:"space-between", marginBottom:12 }}>
                      <div>
                        <div style={{ fontWeight:700, fontSize:15, letterSpacing:1 }}>{ep.name}</div>
                        <div style={{ fontFamily:"'Space Mono',monospace", fontSize:10, color:"var(--muted)", marginTop:2 }}>{ep.id} · {ep.os}</div>
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
                        → Trigger Remediation
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
                      completed:{color:"var(--accent3)",label:"DONE",anim:"none"},
                      failed:{color:"var(--danger)",label:"FAILED",anim:"none"},
                    }[ha.status];
                    const impactClr = {high:"var(--danger)",medium:"var(--warn)",low:"var(--accent3)"}[ha.impact];
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
                    {step:"1",label:"Detect",sub:"Telemetry + Anomaly ML",icon:"◎",color:"var(--accent)"},
                    {step:"2",label:"Analyze",sub:"RAG + LLM Reasoning",icon:"⬡",color:"var(--accent2)"},
                    {step:"3",label:"Plan",sub:"Action Prioritization",icon:"◈",color:"var(--warn)"},
                    {step:"4",label:"Execute",sub:"Auto-Remediation",icon:"▶",color:"var(--accent3)"},
                    {step:"5",label:"Verify",sub:"Post-Fix Validation",icon:"✓",color:"var(--accent3)"},
                    {step:"6",label:"Learn",sub:"Update KB + Model",icon:"⟲",color:"var(--accent)"},
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
                        <div style={{ color:"var(--border)", fontSize:16, padding:"0 4px" }}>→</div>
                      )}
                    </div>
                  ))}
                </div>
              </Card>
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
                      ● RAG+LLM HYBRID · KNOWLEDGE BASE: 4,821 DOCS
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
                          ⬡ HEALIX
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
                    {layer:"Vector Store", items:["4,821 KB documents","Embedding model","Semantic retrieval"], color:"var(--accent2)"},
                    {layer:"LLM Reasoning", items:["Contextual analysis","Action planning","Root cause inference"], color:"var(--warn)"},
                    {layer:"Agent Actions", items:["Tool calling","Auto-remediation","Escalation"], color:"var(--accent3)"},
                  ].map(({layer,items,color}) => (
                    <div key={layer} style={{ marginBottom:10, paddingBottom:10, borderBottom:"1px solid var(--border)" }}>
                      <div style={{ fontWeight:700, fontSize:12, color, marginBottom:4 }}>{layer}</div>
                      {items.map(it => (
                        <div key={it} style={{ fontFamily:"'Space Mono',monospace", fontSize:10, color:"var(--muted)", padding:"1px 0" }}>
                          · {it}
                        </div>
                      ))}
                    </div>
                  ))}
                </Card>

                <Card>
                  <Label style={{ display:"block", marginBottom:10 }}>Model Stats</Label>
                  {[
                    {k:"KB Documents",v:"4,821"},
                    {k:"Query Latency",v:"1.4s avg"},
                    {k:"Recall@10",v:"94.3%"},
                    {k:"Auto-resolve rate",v:"78.6%"},
                    {k:"Hallucination rate",v:"<0.8%"},
                    {k:"Retraining cycle",v:"7 days"},
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
