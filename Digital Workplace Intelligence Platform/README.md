# DWIP: Digital Workplace Intelligence Platform

DWIP is a single platform for digital employee experience across **laptops, desktops, mobile phones and virtual desktops (Citrix and AVD)**. It covers application, OS and device monitoring, AI alerting and insights, conversational AI, IT ↔ employee collaboration, in-app guidance, predictive analytics and employee engagement.

Everything runs on the **N-DUDE-N** loop: Notice → Discover → Understand → Decide → Execute → Notify.

## Capabilities
| Capability | Where it lives |
|---|---|
| **Monitoring: devices, OS, apps, VDI** | Agent and simulator report device vitals and OS health (patch age, system errors). Each app reports CPU, memory, crashes, hangs and response time. VDI sessions report round-trip time, logon time, host and protocol. Rules live in `server/brain.py`. |
| **App visibility & performance** | **Applications** view: a health score per app, version breakdown, affected devices and a response-time trend (`server/analytics.py`). |
| **AI alerting & insights** | A *device anomaly* is a DEX drop against that device's own baseline. A *fleet alert* is the same issue open on ≥3 devices (crash waves, VDI slowdowns). Each alert gets an instant rule-based insight, which the local LLM then refines. |
| **Predictive analytics** | Disk-full forecast and declining DEX score (both require a real trend, R² ≥ 0.6), battery replacement, rising app crash rates. |
| **Conversational access** | IT **Copilot** (✨ button) answers questions about the fleet. Employees get a self-help assistant in the companion app. |
| **IT ↔ employee collaboration** | Employees open conversations from their device. The AI checks the device and posts a triage note, then IT replies from **Conversations**. |
| **In-app guidance** | Step-by-step guides, sent automatically when an issue opens (e.g. storage full → "Free up storage") or pushed by IT. Delivery and completion are tracked. |
| **Employee engagement** | Pulse surveys targeted by device type, sentiment by department and device type, response rate, an experience score (−100 to 100), comments and guide completion. |
| **Remediation** | Low-risk fixes run automatically. Medium- and high-risk fixes wait for IT approval. Users get at most 5 notifications per device per hour. |

## Release 1: experience intelligence (control tower)
The console navigation has 10 sections: Executive Overview · Digital Employee Experience (with Devices, Applications, Engagement, Conversations and Guidance) · Proactive Monitoring · AI Root Cause Analysis · Predictive Intelligence · Intelligent Remediation · AI Assist · Enterprise Integrations · Reports and Analytics · Governance and Audit. Global filters (location, department, device type, live/demo data, period) and data-freshness indicators apply across views.

| Feature | Where it lives |
|---|---|
| **Employee Impact Score (0–100)** | `server/impact.py`. Six weighted factors: reach, severity, critical app, duration, recurrence, escalation. Admins set the weights; every score shows its breakdown. |
| **Incidents and basic correlation** | `server/intel.py`: open issues grouped across devices, each labelled as fact, correlation or hypothesis. A cause is never marked as confirmed. |
| **Monitoring coverage** | Each signal shows Live, Demo only or Not collected (with what it needs). Values are never invented. |
| **Internal baselines** | Hourly DEX rollups (kept 90 days) and comparisons by location, business unit, OS version, model and VDI pool. |
| **AI Assist (read-only)** | Rules → statistics → local LLM, and the LLM only runs when there is evidence. Answers show data gaps, confidence and data freshness. |
| **Connectors** | `server/connectors.py`: health for the agent and simulator; Intune, M365, Teams, OneDrive, Azure Monitor, ServiceNow, SCCM, Nexthink and Splunk show "Not configured" until their environment settings are present. |
| **RBAC and audit** | `server/identity.py`. Roles: viewer, analyst, engineer, admin. Viewers see employee names masked. Every change, denied request, AI query and automatic fix goes to the audit log. |
| **AI usage** | Calls, tokens and latency per purpose, plus the share of answers given without an LLM. |

Set `DWIP_IT_TOKENS="tokenA:admin:Alice,tokenB:viewer"` to require console sign-in. With no tokens the console runs in local-dev mode (admin, with a warning). Simulated devices carry a **DEMO** badge.

## Parts
| Path | What it is |
|---|---|
| `server/main.py` | FastAPI app: enrolment, telemetry pipeline, alerts, approvals, apps, predictions |
| `server/collab.py` | Conversations, guidance, campaigns, AI assistant endpoints |
| `server/brain.py` · `analytics.py` · `ai.py` | Rules and DEX score · anomaly, correlation and forecasting · LLM with rules fallback |
| `server/static/` | Animated IT console (`/`) and employee companion app (`/companion`) |
| `agent/agent.py` | Real agent for Windows, macOS and Linux. Collects vitals, known apps, OS health and per-app crashes from event logs, and detects Citrix/AVD sessions. |
| `simulator/simulate.py` | 14-device fleet: laptops, desktops, Android and iOS phones, Citrix and AVD. Includes crash waves, VDI slowdowns and chatting employees. |

## Run locally
```powershell
pip install -r requirements.txt
ollama pull gemma3:4b                                          # optional: enables LLM answers and insights
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000   # terminal 1
python simulator/simulate.py                                   # terminal 2 (demo fleet)
python agent/agent.py                                          # terminal 3 (this PC, dry-run)
```
Open http://localhost:8000 for the console. The employee companion is at http://localhost:8000/companion; the agent prints a ready-made link for this PC.

**Phone:** join the same Wi-Fi and open `http://<your-PC-IP>:8000/companion`. The enrolment token is `dev-token`. Windows Firewall may ask you to allow Python.

### Settings (environment variables)
| Variable | Default | |
|---|---|---|
| `DWIP_DB` | `%LOCALAPPDATA%\DWIP\dwip.db` | Keep the database out of OneDrive or other synced folders. |
| `DWIP_ENROLL_TOKEN` | `dev-token` | Shared enrolment token |
| `DWIP_AI` | `on` | Set to `off` for rules-only mode |
| `DWIP_OLLAMA_URL` / `DWIP_LLM_MODEL` | `http://127.0.0.1:11434` / `gemma3:4b` | Local LLM |

> On Windows, use `127.0.0.1` instead of `localhost` for agents and scripts. `localhost` tries IPv6 first and adds about 2 s to every request.

## Safety
- The agent is **dry-run by default**. `clean_temp` only deletes temp files older than 7 days, and only with `--allow-actions`.
- Repair, restart, update and reboot actions are simulated on real devices.
- Interactive AI requests take priority over background ones. Background insights are dropped (keeping the rule-based text) when Ollama is busy.

## Tests
```powershell
python -m pytest -q          # 33 tests
```

## Rollback
Release 1 only adds tables and columns, so the older code still runs against the new database. To undo it, revert its commit.

## Not built yet (Release 2/3)
- Entra ID sign-in (tokens for now), RCA dependency graph, ML model registry, runbook RAG, write connectors
- mTLS between agent and server
- Native mobile apps or an MDM connector (Intune, JAMF)
- Real remediation scripts (signed)
- ClickHouse for large fleets
- Teams and email notification channel
