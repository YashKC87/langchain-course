# DWIP: gap analysis and release plan

Scope: the 13-section enhancement specification, compared with the DWIP code as it stands today (uncommitted, `feature/gemma3-setup`).

Status codes:
- **✅ Implemented**: works today and is covered by tests.
- **🟡 Partial**: some of it exists.
- **❌ Missing**: nothing exists yet.
- **🔌 Needs integration**: needs a connector to an external system.
- **📡 Needs telemetry**: the agent or simulator does not collect the data yet.
- **🏗 Needs architecture change**: needs a structural change to the platform.

## 1. Existing architecture

| Layer | Today |
|---|---|
| Presentation | One vanilla-JS console (`server/static/app.js`, no build step) with 8 views and a Copilot panel. Employee companion web app at `/companion`. **There is no React/TypeScript frontend**, so the spec's "reuse existing React components" does not apply. |
| API | FastAPI (`server/main.py`, `server/collab.py`). Devices authenticate with a per-device key; the IT side has **no authentication**. |
| Telemetry | Python endpoint agent (psutil plus a PowerShell probe) and a 14-device simulator. Stored in SQLite (WAL) with 24 h raw retention. |
| Intelligence | Rules engine (`brain.py`), z-score anomaly detection, fleet correlation (the same issue on 3 or more devices), least-squares forecasts with an R² gate (`analytics.py`), and the local LLM Gemma 3 through Ollama, falling back to rules (`ai.py`). |
| Automation | Action catalogue with risk tiers. Low-risk actions run automatically; medium and high wait for approval; advise-only actions just notify. Actions are simulated on the real agent except `clean_temp`. |
| Observability | WebSocket event stream only. No token, latency or cost metrics. |

## 2. Feature gap analysis

### §1 AI Assist
| Requirement | Status | Notes |
|---|---|---|
| Natural-language Q&A in the navigation | 🟡 | The Copilot is a floating panel, not a navigation page. Answers come from a fixed fleet summary, not a search. |
| Search across endpoint, app and network data | 🟡 | Device and app data are searchable. Network data is limited to latency. Compliance and incident data do not exist. |
| Root-cause explanations | 🟡 | The LLM explains alerts, but explanations are not tied to evidence. |
| Step-by-step remediation | 🟡 | Guides are written for employees. There are no runbooks for IT. |
| Historical incident and knowledge-base search, RAG | ❌ | No knowledge base, no embeddings. |
| Suggested PowerShell or approved actions | 🟡 | The action catalogue exists, but the assistant does not propose actions from it. |
| Incident summaries and reports | ❌ | |
| Role-based visibility | ❌ 🏗 | No IT login exists. |
| Facts, predictions and hypotheses kept separate; evidence, confidence and freshness shown | ❌ | Insights are free text. `insight_source` records rule or LLM only. |

### §2 Proactive DEX monitoring
| Domain / item | Status | Notes |
|---|---|---|
| CPU, memory, disk, boot, crashes | ✅ | |
| Login duration | 🟡 | Measured for VDI logons only. |
| OS health | ✅ | Patch age, system errors. |
| Driver health | ❌ 📡 | |
| Compliance and BitLocker | ❌ 📡 | |
| Teams and Outlook performance | 🟡 | Per-app CPU, memory, crashes and response time. No call-quality data. |
| OneDrive sync | ❌ 📡 | |
| M365 service health | ❌ 🔌 | Requires Microsoft Graph. |
| AVD/Citrix latency and logon time | ✅ | |
| AVD session failures, disconnects, host utilisation | ❌ 🔌 | Requires Azure Monitor. |
| FSLogix | ❌ 📡 | |
| Network: latency | ✅ | |
| Network: DNS, packet loss, VPN, Wi-Fi | ❌ 📡 | |
| Employee Impact Score (0–100, explainable, configurable) | ❌ | The per-device DEX score exists, but there is no per-incident impact score. |
| Dashboard: Overall DEX, critical issues, alerts, trend | ✅ | |
| Dashboard: impacted employees, top 5 problems | 🟡 | Counts are per device; there is no employee identity. |
| Location heatmap | ❌ 📡 | Devices have a `department` but no location. |
| Connector status instead of fake values | ❌ | |

### §3 Automated RCA
| Requirement | Status | Notes |
|---|---|---|
| Detect, scope and collect | ✅ | Anomaly and fleet alerts list affected devices and apps. |
| Correlate by time and dependency | 🟡 | Correlation groups by issue type only. There is no dependency model. |
| Compare against configuration changes | ❌ 📡 | Only the app version breakdown exists. There is no change log. |
| Evidence-based confidence | ❌ | |
| Verify remediation | 🟡 | An issue auto-resolves when it clears, but this is not linked to the action that was taken. |
| Learn and record findings | ❌ | |
| Sources: Intune, MECM, ServiceNow, Teams, FSLogix and others | ❌ 🔌 | |
| Dependency graph visual | ❌ | |

### §4 Predictive analytics
| Requirement | Status | Notes |
|---|---|---|
| Storage exhaustion, experience decline, app crash trend | ✅ | Statistical models, not ML. |
| Endpoint failure, non-compliance, BitLocker, AVD degradation, repeat incidents | ❌ | Needs labelled history, and compliance needs new telemetry. |
| Reuse RF, XGBoost, logistic regression, Isolation Forest | ❌ | **DWIP contains no ML models.** The sibling `../Logistic Regression` project in the same repo has some; integrating it is an option. |
| Model card: version, training time, feature importance, drift, history | ❌ | |

### §5 Remediation
| Requirement | Status | Notes |
|---|---|---|
| Detect, recommend, approve, execute | ✅ | |
| Verify and learn | ❌ | |
| Three execution modes | 🟡 | Exists implicitly through risk tiers (advise = recommend, medium/high = approval, low = auto). Not configurable per policy. |
| Allowlist; LLM cannot run arbitrary commands | ✅ | The LLM never reaches the action layer. |
| Dry-run | ✅ | The agent runs dry-run by default. |
| Audit log | 🟡 | The `events` and `actions` tables exist, with no approver identity. |
| RBAC, script signing, batch limits, timeouts, retry, rollback | ❌ | |
| Intune sync, OneDrive, BitLocker, Teams cache, AVD recovery, ServiceNow actions | ❌ 🔌 | |

### §6 Integrations
Not started (❌ 🔌). There is no connector framework, normalised schema or health view. Device identities are deduplicated by agent key only.

### §7 Benchmarking
| Requirement | Status | Notes |
|---|---|---|
| By department and device type | 🟡 | Sentiment only. |
| By OS version, app version, VDI pool | 🟡 | The data exists, but there is no comparison view. |
| By region and persona | ❌ 📡 | |
| Internal baselines, e.g. vs. previous 7 days | ❌ | Raw telemetry is kept for 24 h only, which needs daily rollups (🏗). |

### §8 Control tower UI
| Requirement | Status | Notes |
|---|---|---|
| The 10-item navigation | 🟡 | 8 views exist and map onto 6 of the 10 items. Missing: RCA, Remediation (approvals are inside Overview), Integrations, Governance and Audit. |
| Filters by region, department, device and time | ❌ | |
| Data freshness indicators; loading, empty and disconnected states | 🟡 | |
| No placeholder statistics | ✅ | All figures come from telemetry. Demo devices are not labelled as demo (❌). |

### §9–11 Architecture, cost and security
| Requirement | Status | Notes |
|---|---|---|
| Rules → stats → local SLM order | ✅ | Rules are always computed first; the LLM only refines them. |
| Enterprise LLM routing (Foundry) | ❌ | |
| Token, latency and cost tracking | ❌ | |
| Structured context, bounded iterations | ✅ | |
| No external AI by default | ✅ | Local Ollama only. |
| IAM, RBAC, TLS, secret store, prompt-injection guard, vulnerability scanning | ❌ 🏗 | The enrolment token defaults to `dev-token`. Employee chat text reaches the LLM unfiltered. |

## 3. Target architecture

The current stack stays: FastAPI, SQLite, vanilla JS and Ollama. New capability is added as modules, with no new infrastructure.

```
server/
  identity.py      roles (viewer, analyst, engineer, admin) via API token now, Entra ID OIDC later
  impact.py        Employee Impact Score with configurable weights
  incidents.py     incidents = grouped alerts + evidence + hypotheses + RCA state
  rca.py           dependency model + evidence scoring
  connectors/      base.py (status, auth, freshness, rate-limit, volume) + one module per system
  knowledge.py     runbooks (markdown) + local retrieval (BM25 first, embeddings optional)
  llm_router.py    rules → stats → local SLM → Foundry (only if configured and allowed), token/latency ledger
  policy.py        per-action execution mode, batch limits, timeouts, audit
  ml/              model registry, model cards, drift checks (separate retrain CLI)
```

## 4. Release plan

**Release 1: Experience intelligence foundation**
1. Navigation restructured into the 10 control-tower items, keeping the existing views, with no duplicates.
2. Employee Impact Score, configurable and showing how each score was calculated.
3. Incidents table that groups alerts, with evidence. The AI output is labelled as fact, prediction or hypothesis, with data freshness.
4. Location field on devices (agent and simulator), a location heatmap, and global filters.
5. Connector framework and health page. Real status only: unconfigured connectors show "Not configured".
6. AI Assist as a full page: read-only, cites evidence, and searches devices, apps, alerts and incidents.
7. Internal baselines (daily rollups; current vs. previous period, by department, location, OS and app version).
8. A demo badge on simulated devices.
9. Basic RBAC (token-based roles) on the IT APIs, plus an audit log page.

**Release 2: Predictive and diagnostic intelligence**
- RCA engine with dependency graph (Endpoint → Network → Auth → VDI host → Profile → App).
- Change log: app, OS and config versions.
- ML model registry, starting with Isolation Forest and logistic regression, with model cards and drift.
- Runbook RAG.
- Token and latency observability.
- Telemetry: DNS, packet loss, VPN, BitLocker/compliance, OneDrive, and FSLogix where available.

**Release 3: Autonomous experience operations**
- Per-policy execution modes.
- Batch limits, timeouts, retry and rollback.
- Verification linked to actions, plus effectiveness analytics.
- Signed scripts.
- Write connectors: Intune sync, ServiceNow, AVD.
- Foundry routing.

## 5. Prerequisites (owner: you)
- Access to an Entra ID app registration for SSO and Graph/Intune.
- Credentials for ServiceNow, Azure Monitor and Log Analytics, Nexthink and Splunk (only for the ones you want).
- A decision on whether an external enterprise LLM (Foundry) may receive telemetry. It defaults to **no**.
- Location data source: an agent setting, Entra ID user attributes, or IP-subnet mapping.

## 6. Test strategy
- Every release keeps the 24 existing tests green and adds unit tests per module:
  - impact score maths
  - RCA evidence scoring
  - policy enforcement
  - RBAC denial paths
  - connector status without credentials
- Integration tests run on the synthetic fleet. Demo data is flagged, and tests assert it is never mixed into live-only views.
- Acceptance: every number on a dashboard can be traced back to a stored record, and unconfigured connectors never show values.
- Rollback: each release is its own commit. Revert it with `git revert <sha>`. Schema changes are additive only (new tables and columns), so older code keeps working.
