# Right Model Lab — Detailed Section Write-up for Each Dropdown

This is a **section-by-section** script for the three pages in the **Go to** dropdown:

1. [Overview](#1-overview)
2. [AI Model Operations](#2-ai-model-operations)
3. [Model Comparison](#3-model-comparison)

Use it for video narration, live demos, or training. For each section: **what it is**, **what to say**, and **what it proves**.

---

## Sidebar (visible on all three pages)

Before the dropdown pages, briefly cover the left panel.

| Section | What it shows | What to say |
|---|---|---|
| **App title** | Right Model Lab | “This is Right Model Lab — right model, right task, measurable evidence.” |
| **Theme** | Dark / Light | “You can switch theme here; content stays the same.” |
| **Go to** | Overview · AI Model Operations · Model Comparison | “These three pages are the full demo path.” |
| **Mode / SLM / Frontier / LangSmith** | Provider status (no secrets) | “DEMO or LIVE, which SLM and Frontier are configured, and whether LangSmith is active or local-only.” |
| **Pricing caption** | Illustrative cost disclaimer | “Cost numbers are illustrative — configure with your provider pricing.” |

---

# 1. Overview

**Dropdown:** `Overview`  
**Purpose:** Home base for the use case — status, fleet KPIs, five patterns, and deep pattern detail.

---

### 1.1 Page header

**On screen:**  
`Right Model Lab`  
Subtitle: *Right model · right task · measurable evidence*

**Write-up:**  
This is the product identity. The lab is not a generic chatbot demo. It is an architecture lab that shows when to use an SLM and when to use a Frontier model for digital workplace device monitoring.

**Say:**  
> Welcome to Right Model Lab. The thesis is simple: use the right model for the right task.

---

### 1.2 Thesis line

**On screen:**  
*Frontier for planning/ambiguity/synthesis · SLM for routine high-volume work*

**Write-up:**  
This one sentence is the operating rule of the entire lab. Frontier is the senior architect. SLM is the experienced service desk. Hybrid architecture protects Frontier capacity without pretending the small model can do everything.

**Say:**  
> Frontier handles planning, ambiguity, and synthesis. The SLM handles routine, high-volume work.

---

### 1.3 Status strip

**On screen (five chips):**

| Chip | Meaning |
|---|---|
| **Mode** | `DEMO` = simulated, no cloud required · `LIVE` = Ollama/Azure in use |
| **SLM** | Provider / model name (for example `ollama / llama3.2`) |
| **Frontier** | Provider / model name (for example `azure_openai / gpt-4o`) |
| **LangSmith** | `active` or `local-only` |
| **Fleet** | Endpoint count · healthy · at risk · critical |

**Write-up:**  
This strip tells the audience which runtime they are watching. In DEMO, metrics are labeled SIMULATED. In LIVE, provider usage can be ACTUAL. LangSmith is optional; local traces still power analytics.

**Say:**  
> At a glance you can see mode, models, observability, and fleet health. No secrets are shown here.

---

### 1.4 Run all patterns + demo tip

**On screen:**  
Button **Run all patterns** · tip to use “Load latest saved result”

**Write-up:**  
Run all executes Planner-Worker, Router, Cascade, RAG, and Fallback through `ScenarioService`. Live runs can take minutes. For demos, prefer loading saved results from earlier executions.

**Say:**  
> You can run all five patterns here, or open one pattern and load the latest saved result for a fast walkthrough.

---

### 1.5 KPI row

**On screen (examples of cards):**  
Endpoints · Healthy · At Risk · Critical · Cost Avoided\* · SLM Calls · Frontier Calls · SLM Tokens · Frontier Tokens · Frontier Calls Avoided · Frontier Tokens Avoided · Avg Latency · P95 Latency · Avg Confidence · Estimated Cost\*

**Write-up:**  
These KPIs summarize the synthetic fleet and aggregate model economics across saved runs. The most important efficiency cards are **Frontier Calls Avoided** and **Frontier Tokens Avoided**. Cost is illustrative USD, not an invoice.

**Say:**  
> The headline efficiency metric is Frontier tokens avoided — not simply that total tokens went down. Quality still has to hold.

---

### 1.6 Patterns section (five tiles)

**On screen:** Five tiles, each with name, locked scenario, SLM role, Frontier role, primary benefit, last-run timestamp, and **Open**.

#### Tile A — Planner-Worker Hierarchy

| Field | Content |
|---|---|
| Scenario | Complete multi-domain RCA for `LAPTOP-1204` |
| SLM role | Execute routine investigation workers |
| Frontier role | Plan investigation and synthesize final RCA |
| Benefit | Selective reasoning + orchestration efficiency |

**Say:**  
> Planner-Worker: Frontier plans and synthesizes. SLM workers run routine CPU, Teams, network, compliance, and history checks.

#### Tile B — Router Pattern

| Field | Content |
|---|---|
| Scenario | Route 100 endpoint health requests |
| SLM role | Routine health/status requests |
| Frontier role | Complex/ambiguous RCA requests |
| Benefit | High-volume inference efficiency |

**Say:**  
> Router: a non-LLM dispatcher sends most routine volume to the SLM and reserves Frontier for hard cases.

#### Tile C — Confidence Cascade

| Field | Content |
|---|---|
| Scenario | Ambiguous Teams + VPN on `LAPTOP-9910` |
| SLM role | First-pass diagnosis |
| Frontier role | Escalation when confidence is low |
| Benefit | Quality-aware escalation |

**Say:**  
> Cascade: try SLM first; escalate only when confidence falls below the threshold — default 85%.

#### Tile D — Retrieval-Augmented Generation (RAG)

| Field | Content |
|---|---|
| Scenario | `LAPTOP-1507` disk/OneDrive approved SOP remediation |
| SLM role | Grounded generation from retrieved SOPs |
| Frontier role | Not required for this SOP scenario |
| Benefit | Grounded enterprise knowledge with smaller model |

**Say:**  
> RAG: retrieve approved SOPs, then answer with a grounded SLM. Frontier is not required here.

#### Tile E — Designing for Fallback

| Field | Content |
|---|---|
| Scenario | Critical RCA when Frontier is unavailable |
| SLM role | Availability fallback with degraded quality |
| Frontier role | Primary advanced reasoning path |
| Benefit | Resilience and availability |

**Say:**  
> Fallback: if Frontier fails — timeout, rate limit, offline, and similar — the SLM continues so operations do not stop.

---

### 1.7 Pattern detail (opened from a tile — still under Overview)

Clicking **Open** expands detail below the tiles. Dropdown stays on Overview.

#### 1.7.1 Detail header + Close

**Write-up:** Shows which pattern is open. **Close detail** returns to the tile grid.

#### 1.7.2 Architecture diagram

**On screen:** Step lanes with nodes labeled **SLM / FRONTIER / NON-LLM**, thesis line, edge summary, roles, primary benefit.

**Write-up:** This is the intended architecture before you look at an executed run. Every box is role-labeled so the audience never guesses which model class owns a step.

**Say:**  
> Here is the architecture for this pattern — clearly labeled so you can see where Frontier is reserved and where the SLM carries the volume.

#### 1.7.3 Locked scenario caption + Execute / Load

**On screen:**  
- Pattern-specific caption (device / scenario lock)  
- Fallback only: failure-mode dropdown (`http_503`, `timeout`, `rate_limit`, `auth_error`, `offline`, `cost_guard`)  
- **Execute \<pattern\>** · **Load latest saved result**

**Write-up:**  
Execute runs live/demo providers now. Load reads `.local_pattern_results.json` for an instant replay.

**Say:**  
> For a smooth demo, load the latest saved result. Execute when you want to show a fresh live or demo run.

#### 1.7.4 Section 1) Scenario

**On screen:** Business question, device id, user, DEX, risk, key telemetry anomalies, anomaly thresholds.

**Write-up:** Anchors the pattern in a real operational story — not an abstract prompt.

**Say:**  
> This is the locked incident. The telemetry and risk scores explain why this device needs this pattern.

#### 1.7.5 Section 2) Architecture Flow

**On screen:** Executed segment cards with model badge, provenance badge (`ACTUAL` / `SIMULATED` / `ESTIMATED`), tokens, latency, confidence, why-text, optional “What if alternative?” expander.

**Write-up:** This is the **actual run path**, not just the diagram. Provenance prevents overclaiming.

**Say:**  
> Every node tells you which model ran, how expensive it was, how confident it was, and why that choice was made.

#### 1.7.6 Section 3) Why This Model?

**On screen:** Table of selected model vs ESTIMATED alternative with token/latency/confidence deltas and recommendation.

**Write-up:** The decision audit for each segment — especially useful when Frontier costs more but quality requires it, or when SLM is enough.

**Say:**  
> This answers the challenge question: why not send everything to Frontier — or everything to the SLM?

#### 1.7.7 Section 4) Token Utilization

**On screen:** Stacked hybrid SLM + Frontier bars vs **All-Frontier (ESTIMATED)** bar; KPIs for Frontier tokens avoided, avoidance %, latency improvement, quality difference, cost avoided\*.

**Write-up:** Primary visual for the lab’s efficiency claim. Baseline is ESTIMATED — no Frontier call was made solely to invent the comparison.

**Say:**  
> Hybrid versus estimated all-Frontier. The win is Frontier capacity preserved, with quality kept in view.

#### 1.7.8 Section 5) Performance Comparison

**On screen (pattern-specific):**  
- Common: hybrid vs baseline summary  
- Router: mix / avoidance stats  
- Cascade: strategy options + fleet economics  
- RAG: RAG+SLM vs RAG+Frontier  
- Fallback: normal Frontier (ESTIMATED) vs failure + SLM recovery  

**Write-up:** Performance is not only speed — it is quality, avoidance, and resilience depending on the pattern.

**Say:**  
> Performance here includes quality and operating risk, not latency alone.

#### 1.7.9 Section 6) LangSmith Trace

**On screen:** Local trace id, optional LangSmith link, waterfall chart, span table.

**Write-up:** Parent/child execution visibility. Works with local traces even when LangSmith is off.

**Say:**  
> This is the execution trace — which segment ran, in what order, with what tokens and latency.

#### 1.7.10 Tail View — Precise Operational Detail

**On screen:** Segment ledger + pattern-specific drill-downs (worker comparisons, router examples, escalation event, retrieval citations, failure/recovery).

**Write-up:** For technical audiences who want the ledger behind the story.

**Say:**  
> Tail view is the operator ledger — request examples, citations, escalation and recovery detail.

#### 1.7.11 AI Architect Decision

**On screen:** What Frontier was used for, what SLM was used for, Frontier tokens/calls avoided, recommendation text.

**Write-up:** Closing verdict for that pattern run.

**Say:**  
> The AI Architect Decision summarizes the model mix and the Frontier tokens avoided for this scenario.

---

# 2. AI Model Operations

**Dropdown:** `AI Model Operations`  
**Purpose:** MLOps control tower — portfolio evidence across all pattern runs.

---

### 2.1 Page header

**On screen:**  
`AI Model Operations`  
Subtitle: *MLOps control tower · right-model evidence*

**Write-up:** After individual patterns, this page answers: are we actually putting the right model on the right task across the lab?

**Say:**  
> AI Model Operations is the portfolio view — usage, avoidance, latency, cost, and confidence across patterns.

---

### 2.2 Refresh control

**On screen:**  
**Refresh by running all five patterns** · caption that live runs can take minutes

**Write-up:** Re-executes all patterns to refresh KPIs/charts. For demos, populate Overview first with Load/Execute, then open this page.

**Say:**  
> Refresh only if you need a fresh run. Otherwise use saved results already produced on Overview.

---

### 2.3 Operations status strip

**On screen:**

| Chip | Meaning |
|---|---|
| **Scenarios** | Completed pattern runs counted |
| **Traces** | Parent execution traces |
| **Model Calls** | Total spans / model invocations |
| **Escalation Rate** | Share of cascade escalations |
| **Fallback Rate** | Share of fallback events |

**Write-up:** Quick operating pulse — volume and how often quality/resilience paths fired.

**Say:**  
> Watch escalation and fallback rates. They tell you when the hybrid paths are being stress-tested.

---

### 2.4 KPI grid

**On screen (seventeen cards):**

| KPI | Why it matters in the demo |
|---|---|
| Total Scenarios | How many pattern runs feed the view |
| Total Traces | Parent executions |
| Total Model Calls | All spans |
| SLM Calls | Routine capacity used |
| Frontier Calls | Reasoning capacity used |
| SLM Tokens | High-volume path consumption |
| Frontier Tokens | Premium path consumption |
| Total Tokens | Combined model tokens |
| **Frontier Calls Avoided** | Primary efficiency (calls) |
| **Frontier Tokens Avoided** | **Primary metric** |
| Average Latency | Mean span latency |
| P95 Latency | Tail latency |
| Average Confidence | Quality signal |
| Escalation Rate | Cascade pressure |
| Fallback Rate | Resiliency events |
| Estimated Cost\* | Illustrative USD |
| Estimated Cost Avoided\* | Illustrative USD saved vs baseline |

**Write-up:** Read **Frontier Tokens Avoided** first, then confidence and p95, then illustrative cost. Always voice the pricing disclaimer.

**Say:**  
> Frontier tokens avoided is the primary metric. Cost is illustrative. Confidence and p95 keep us honest about quality and tail latency.

---

### 2.5 Pricing disclaimer caption

**Write-up:** Reminds viewers that USD figures come from configurable illustrative rates in `.env`, not a billing system.

**Say:**  
> Treat cost as directional for architecture decisions, not as an invoice.

---

### 2.6 Interactive Charts

**On screen:** Caption about short labels (Planner-Worker · Router · Cascade · RAG · Fallback), then charts 1–12 (+ radar).

| # | Chart | What to say |
|---|---|---|
| **1** | Token Consumption by Pattern | “Where SLM volume sits versus Frontier per pattern.” |
| **2** | Selected vs All-Frontier (ESTIMATED) | “Hybrid selected path versus the estimated all-Frontier baseline.” |
| **3** | Model Usage Mix (Calls) | “Share of calls on SLM versus Frontier.” |
| **4** | Token Trend Over Time | “Token activity over the recorded span timeline.” |
| **5** | Latency by Model Type | “SLM versus Frontier versus non-LLM latency distributions.” |
| **6** | Latency by Pattern | “Which patterns are latency-heavy.” |
| **7** | Cost by Pattern (Illustrative) | “Directional cost by pattern — not billing.” |
| **8** | Confidence vs Frontier Calls | “Quality signal versus how much Frontier was used.” |
| **9** | Frontier Avoidance Rate (%) | “The efficiency scorecard — pause here for executives.” |
| **10** | Tokens vs Latency | “Spend/shape of work versus speed.” |
| **11** | Cost vs Quality (Confidence) | “Cheapest is not automatically best — quality must clear the bar.” |
| **12** | Pattern Usage (Model Calls) | “Relative call volume by pattern.” |
| **Radar** | Quality / Efficiency Radar | “Multi-axis profile: confidence, avoidance, latency efficiency, cost efficiency.” |

**Write-up:** Charts use short names so labels do not overlap. Hover for full pattern names. Baseline comparisons are ESTIMATED.

**Say (close the charts block):**  
> Two takeaways: Frontier avoidance is the efficiency win, and the best architecture meets quality at an acceptable Frontier spend.

---

### 2.7 Pattern Efficiency Table

**On screen:** Dataframe — one row per pattern with tokens, latency, confidence, cost, avoidance fields (from `efficiency_table`).

**Write-up:** The slide-friendly summary after the charts. Good for freeze-frame or screenshot.

**Say:**  
> One row per pattern — this is what you send in a follow-up email after the demo.

---

### 2.8 Primary benefits callout

**On screen:**  
Planner-Worker = selective reasoning · Router = high-volume efficiency · Cascade = quality-aware escalation · RAG = grounded smaller-model answers · Fallback = availability

**Write-up:** Restates why five patterns exist — each proves a different operating benefit.

**Say:**  
> Five patterns, five benefits. Together they are the hybrid operating model.

---

# 3. Model Comparison

**Dropdown:** `Model Comparison`  
**Purpose:** Segment-level decision audit — selected path versus alternative / ESTIMATED path.

---

### 3.1 Page header

**On screen:**  
`Model Comparison`  
Subtitle: *Selected vs alternative by segment · tokens · latency · confidence · cost*

**Write-up:** Where Operations is portfolio analytics, Comparison is the courtroom evidence for each modeling decision.

**Say:**  
> Model Comparison is the audit trail: what we selected, what the alternative would have been, and why.

---

### 3.2 Empty state / generate control

**On screen (only if no results yet):**  
Button **Generate comparisons by running all patterns**

**Write-up:** Appears when `_last_results` is empty. Prefer loading/running patterns on Overview first so this page is immediately populated.

**Say:**  
> If this page is empty, run or load patterns on Overview first — or generate comparisons here.

---

### 3.3 Per-pattern block (repeats for each saved pattern)

For each pattern result:

#### 3.3.1 Pattern subheader

**On screen:** Full pattern name (for example *Planner-Worker Hierarchy*).

**Say:**  
> Starting with [pattern name].

#### 3.3.2 Comparison table columns

| Column | Meaning |
|---|---|
| `segment` | Named step in the pattern (Planning, Router, SLM Diagnosis, Retrieval, etc.) |
| `selected` | Chosen model type: SLM / FRONTIER / NON_LLM |
| `selected_tokens` | Tokens used on the selected path |
| `selected_latency_ms` | Latency of selected path |
| `selected_confidence` | Confidence of selected path |
| `selected_provenance` | ACTUAL / SIMULATED / ESTIMATED for the selected path |
| `alternative` | Counterfactual model type |
| `alt_tokens_ESTIMATED` | Estimated tokens if alternative had been used |
| `alt_latency_ESTIMATED` | Estimated alternative latency |
| `alt_confidence_ESTIMATED` | Estimated alternative confidence |
| `decision` | Short decision label |
| `why` | Human-readable rationale |

**Write-up:**  
Router request children (`REQ-001`…) are hidden so the table stays readable; router aggregates remain on Overview pattern detail and Operations charts. Alternative columns are explicitly ESTIMATED — not secret second live calls.

**Say:**  
> Read left to right: selected path, then the estimated alternative, then the why. ESTIMATED means projected — we did not burn Frontier just to build the comparison.

#### 3.3.3 How to narrate one row (template)

Pick one **SLM-selected** row:

> This segment is routine. We selected SLM. Tokens and latency stay low, confidence is enough. The Frontier alternative is estimated higher cost for little quality gain — so SLM wins.

Pick one **Frontier-selected** row:

> This segment needs planning or synthesis. We selected Frontier. Tokens and cost are higher, but confidence justifies it. Sending this to SLM would be the false economy.

Pick one **NON_LLM** row (router / evaluator / retriever):

> Not every step is a model call. Routers, confidence gates, and retrievers are non-LLM controls that make the hybrid design work.

#### 3.3.4 Avoidance callout under each pattern

**On screen (when `architect_decision` exists):**  
Frontier tokens avoided (count and %), plus recommendation text.

**Write-up:** Pattern-level punchline after the segment table.

**Say:**  
> For this pattern, Frontier tokens avoided were [N] — [P]%. That is the architect recommendation in one line.

---

### 3.4 Closing the Comparison page

**Write-up:** Reconnect Comparison to the other two dropdown pages.

**Say:**  
> Overview tells the story and runs the scenarios. AI Model Operations proves the portfolio economics. Model Comparison defends each segment decision. Together they demonstrate the use case end to end.

---

## Recommended demo order (all three dropdowns)

1. **Overview** — status, KPIs, name five tiles  
2. **Overview → Open one pattern** — architecture, load result, sections 1–6 + Architect Decision  
3. **AI Model Operations** — KPI grid, charts 2 / 9 / 11, efficiency table  
4. **Model Comparison** — one pattern table, one SLM row, one Frontier row, avoidance callout  
5. Return to **Overview** — restate principle: right model, right task, measurable evidence  

---

## One-page cheat sheet

| Dropdown | Job | Signature element | Signature metric / line |
|---|---|---|---|
| **Overview** | Story + run patterns | Five tiles + pattern detail sections | Locked scenarios on real devices |
| **AI Model Operations** | Portfolio MLOps evidence | Charts + KPI grid | Frontier tokens avoided |
| **Model Comparison** | Segment decision audit | Selected vs ESTIMATED alternative table | Why this model won |

---

*End of dropdown section write-up.*
