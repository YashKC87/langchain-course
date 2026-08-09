# Right Model Lab — Video Write-up by Dropdown Page

Use this as a narration and on-screen guide. Record in order. Keep the left sidebar visible so viewers see the **Go to** dropdown.

**Dropdown pages in this build**

1. Overview  
2. AI Model Operations  
3. Model Comparison  

Suggested total length: **8–12 minutes**.

---

## Cold open (20–30 seconds)

**On screen:** Overview page, sidebar open, app title **Right Model Lab**.

**Say:**

> Welcome to Right Model Lab — a working demo of how Small Language Models and Frontier models collaborate for digital workplace device monitoring.
>
> The principle is simple: use the right model for the right task. Frontier handles planning, ambiguity, and synthesis. SLMs handle routine, high-volume work.
>
> In this walkthrough we’ll use the three pages in the dropdown: Overview, AI Model Operations, and Model Comparison.

---

## 1) Overview

**Go to:** `Overview`

### Purpose of this page

This is the home base. It shows whether you’re in Demo or Live mode, which models are configured, fleet health at a glance, and the five architecture patterns you can open and run.

### What to show (in order)

1. Status strip — Mode, SLM, Frontier, LangSmith, Fleet  
2. **Run all patterns** (optional if results are already saved)  
3. KPI row — endpoints, healthy / at risk / critical, Frontier avoidance, latency, cost  
4. Five pattern tiles  
5. Open one pattern and walk the detail view  

### Narration

> This is Overview.
>
> At the top you can see the run mode. In Demo Mode, everything is simulated and safe — no Azure or Ollama required. In Live Mode, the SLM can come from Ollama and the Frontier model from Azure OpenAI. LangSmith is optional; if it’s off, local traces still power the analytics.
>
> Below that are the fleet KPIs from our synthetic digital workplace environment — how many endpoints are healthy, at risk, or critical — plus efficiency signals like Frontier tokens avoided.
>
> These five tiles are the heart of the use case. Each tile is one architecture pattern with exactly one locked scenario:

**Tile 1 — Planner-Worker**

> Planner-Worker is multi-domain root-cause analysis for laptop 1204. The Frontier model plans the investigation and synthesizes the final RCA. SLM workers run the routine checks — OS, network, applications.

**Tile 2 — Router**

> Router takes one hundred incoming endpoint health requests. A non-LLM router sends routine work to the SLM and complex or ambiguous cases to Frontier. This is where high-volume efficiency shows up.

**Tile 3 — Confidence Cascade**

> Confidence Cascade investigates ambiguous Teams and VPN issues on laptop 9910. The SLM tries first. If confidence is below the threshold, we escalate to Frontier. Quality-aware escalation — not blind cheapest-model routing.

**Tile 4 — RAG**

> RAG is approved SOP remediation for laptop 1507 disk and OneDrive issues. We retrieve enterprise knowledge, then let the SLM generate a grounded answer. Frontier is not required for this scenario.

**Tile 5 — Fallback**

> Fallback proves resilience. When Frontier is unavailable — timeout, rate limit, offline, and similar failures — the SLM continues with degraded quality so the operation doesn’t stop.

### Pattern detail (still under Overview)

**Action:** Click **Open** on Planner-Worker (or any tile). Leave the dropdown on Overview.

**Say:**

> Opening a tile keeps us on Overview, but expands the pattern detail.
>
> First you see the architecture diagram for that pattern — clearly labeled SLM, Frontier, and non-LLM steps. No overlapping labels; each stage has a job.
>
> Then you can Execute a live or demo run, or Load the latest saved result for a fast demo.
>
> After a run, scroll the explainable sections: architecture flow of segments, why this model was chosen, token utilization versus an estimated all-Frontier baseline, and the AI Architect decision.
>
> The key metric is Frontier tokens avoided — not simply “total tokens went down.” Fewer tokens with collapsed quality is not a win.
>
> You can Close detail and open another tile the same way.

**Optional 60–90 second inserts (one each if time allows):**

| Pattern | One-line closer |
|---|---|
| Planner-Worker | Point at Frontier plan/synthesis vs SLM workers |
| Router | Show roughly high SLM share vs smaller Frontier share |
| Cascade | Show low confidence → escalate; mention fleet economics |
| RAG | Show retrieved SOP + grounded SLM answer |
| Fallback | Pick a failure mode, show SLM continuity |

---

## 2) AI Model Operations

**Go to:** `AI Model Operations`

### Purpose of this page

This is the MLOps control tower. After patterns have been run (or loaded), this page aggregates evidence across scenarios: model usage, Frontier avoidance, latency, cost, and confidence.

### What to show (in order)

1. Refresh / run-all button (mention; skip if already populated)  
2. Top KPI strip — scenarios, traces, model calls, escalation, fallback  
3. KPI grid — SLM vs Frontier calls/tokens, avoidance, latency, cost  
4. Interactive charts (scroll slowly; pause on 2–3 highlight charts)  
5. Pattern efficiency table  

### Narration

> Now open AI Model Operations from the dropdown.
>
> This page answers the operating question: are we actually putting the right model on the right task?
>
> The KPIs summarize how many scenarios and model calls we’ve made, how often we escalated or fell back, and how many Frontier calls and tokens we avoided.
>
> Scroll the charts. You’ll see token consumption by pattern, selected hybrid versus the estimated all-Frontier baseline, model usage mix, latency, cost, and confidence trade-offs.
>
> Chart labels use short names — Planner-Worker, Router, Cascade, RAG, Fallback — so the picture stays readable. Hover any point for the full pattern name.
>
> Two ideas to leave the audience with:
>
> First — Frontier avoidance is the primary efficiency signal.
>
> Second — the best architecture is not always the cheapest point on the chart. It is the one that meets quality at an acceptable Frontier spend.
>
> The efficiency table at the bottom is useful for executive follow-ups: one row per pattern, with tokens, latency, confidence, and cost side by side.

**Suggested pause charts for the camera:**

1. Selected vs All-Frontier  
2. Frontier Avoidance Rate  
3. Cost vs Quality (Confidence)  

---

## 3) Model Comparison

**Go to:** `Model Comparison`

### Purpose of this page

This page is the decision audit. For each pattern, it compares the **selected** model path against the **alternative / estimated** path segment by segment — tokens, latency, confidence, cost, and the written rationale.

### What to show (in order)

1. Page header  
2. If empty — click generate/run all (or go back to Overview and load results first)  
3. Expand or scroll each pattern’s comparison table  
4. Read one “why” row out loud  
5. Point at the Frontier tokens avoided callout when present  

### Narration

> Finally, Model Comparison.
>
> Where AI Model Operations shows the portfolio view, this page shows the per-segment decision view.
>
> For each pattern you get a table: what we selected, what the alternative would have been, estimated alternative tokens and latency, and why the system made that choice.
>
> Let’s read one row. Here the selected model is SLM for a routine segment — lower cost, enough confidence. The alternative Frontier path is estimated only; we did not burn Frontier just to invent a comparison.
>
> On harder segments you’ll see the opposite: Frontier selected because quality required it, even if tokens and cost are higher.
>
> That is the whole point of the lab. Hybrid architecture is not “always use the small model.” It is disciplined model selection with evidence.

---

## Closing (20–30 seconds)

**On screen:** Return to Overview; sidebar showing the three dropdown pages.

**Say:**

> To recap the dropdown:
>
> Overview — fleet status, five patterns, and deep dives into each scenario.
> AI Model Operations — proof that the hybrid design saves Frontier capacity without hiding quality trade-offs.
> Model Comparison — the segment-level audit of selected versus alternative.
>
> Right Model Lab: right model, right task, measurable evidence.
>
> Thank you.

---

## Recording checklist

- [ ] Sidebar expanded; Theme control visible if you want to mention Dark/Light once  
- [ ] Prefer **Load latest saved result** for a smooth take; use Execute only if you want a live call  
- [ ] Do not show `.env`, API keys, or secret panels  
- [ ] If Live Mode: mention providers briefly, then focus on decisions not credentials  
- [ ] Architecture is **not** a dropdown page; diagrams appear inside Overview pattern detail  

## Suggested chapter markers

| Time (approx.) | Chapter |
|---|---|
| 0:00 | Intro — Right Model Lab |
| 0:30 | Overview — status, KPIs, five tiles |
| 2:30 | Overview — open pattern detail + architecture diagram |
| 5:30 | AI Model Operations |
| 8:00 | Model Comparison |
| 10:00 | Close |

Adjust timings if you only deep-dive one or two patterns.
