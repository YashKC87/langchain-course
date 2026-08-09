# Right Model Lab — Copy-Paste Narration Script

Copy each block as needed. Plain speaking text for the 3 dropdown pages.

---

## INTRO

Welcome to Right Model Lab.

This lab shows how Small Language Models and Frontier models work together for digital workplace device monitoring.

The principle is simple. Use the right model for the right task.

Think of the SLM as an experienced Service Desk Engineer. Fast. Lower cost. Strong on routine work.

Think of the Frontier model as a Senior Solution Architect. Stronger reasoning. Better for planning, ambiguity, and synthesis.

We will walk through the three pages in the dropdown: Overview, AI Model Operations, and Model Comparison.

---

## DROPDOWN 1 — OVERVIEW

### Status strip

This is the Overview page.

At the top you can see the run mode. DEMO means simulated results with no cloud dependency. LIVE means we are using configured providers such as Ollama for the SLM and Azure OpenAI for Frontier.

You can also see which SLM and Frontier models are configured, whether LangSmith is active or local-only, and a quick fleet health summary: how many endpoints are healthy, at risk, or critical.

No secrets are displayed on this screen.

### KPI row

Below that are the key performance indicators.

You will see fleet counts, SLM and Frontier calls, token usage, latency, confidence, and illustrative cost.

The most important efficiency metric is Frontier tokens avoided.

Fewer total tokens is not automatically better if quality collapses. The goal is to preserve Frontier capacity while keeping quality where it matters.

### Five pattern tiles

These five tiles are the heart of the use case. Each tile is one architecture pattern with exactly one locked scenario.

First, Planner-Worker Hierarchy.
Scenario: complete multi-domain root cause analysis for laptop 1204.
Frontier plans the investigation and synthesizes the final RCA.
SLM workers run the routine checks across CPU, Teams, network, compliance, and history.
Primary benefit: selective reasoning.

Second, Router Pattern.
Scenario: route one hundred incoming endpoint health requests.
A non-LLM router sends routine requests to the SLM and complex or ambiguous requests to Frontier.
Primary benefit: high-volume efficiency.

Third, Confidence Cascade.
Scenario: investigate ambiguous Teams and VPN instability on laptop 9910.
The SLM tries first. If confidence is below the threshold, we escalate to Frontier.
Default threshold is 85 percent.
Primary benefit: quality-aware escalation.

Fourth, Retrieval-Augmented Generation, or RAG.
Scenario: laptop 1507 disk and OneDrive remediation using approved SOPs.
We retrieve enterprise knowledge, then let the SLM generate a grounded answer.
Frontier is not required for this scenario.
Primary benefit: grounded answers with a smaller model.

Fifth, Designing for Fallback.
Scenario: critical RCA continues when Frontier becomes unavailable.
If Frontier fails with a timeout, rate limit, offline condition, or similar issue, the SLM continues with degraded quality.
Primary benefit: resilience and availability.

### Open a pattern — architecture

I will open one pattern from Overview.

You still stay on the Overview page, but the pattern detail opens below.

First you see the architecture diagram.
Every step is labeled SLM, Frontier, or Non-LLM.
This makes the design explicit. You can see where Frontier is reserved and where the SLM carries the volume.

### Execute or Load

You can Execute a fresh run, or Load the latest saved result.

For demos, Load latest saved result is usually best. Live provider calls can take several minutes.

### Scenario section

Section one is Scenario.

This locks the story to a specific device, user, DEX score, risk score, and key telemetry anomalies.
It answers the business question behind the pattern.

### Architecture Flow section

Section two is Architecture Flow.

This shows the executed segments from the run.
Each node shows the model type, provenance, tokens, latency, confidence, and why that model was chosen.

Provenance matters.
ACTUAL means provider-reported usage.
SIMULATED means Demo Mode telemetry.
ESTIMATED means a projection, not a real spend.

### Why This Model section

Section three is Why This Model.

This compares the selected model against an estimated alternative.
It explains why SLM was enough, or why Frontier was justified even at higher cost.

### Token Utilization section

Section four is Token Utilization.

Here we compare the selected hybrid path against an estimated all-Frontier baseline.
We do not call Frontier just to invent that comparison.
The key number is Frontier tokens avoided.

### Performance section

Section five is Performance Comparison.

Depending on the pattern, this shows latency, quality, fleet economics, RAG comparisons, or fallback recovery.
Performance is not only speed. It includes quality and operating risk.

### Trace section

Section six is the Trace view.

You can see the parent and child execution path, local trace identity, and span-level tokens and latency.
If LangSmith is active, a remote link may also appear. If not, local traces still power this view.

### Tail View and AI Architect Decision

Tail View gives the precise operational ledger: segment details, examples, citations, escalation, or recovery information.

Finally, the AI Architect Decision summarizes what Frontier was used for, what the SLM was used for, how many Frontier tokens were avoided, and the recommendation for this scenario.

That is Overview.

---

## DROPDOWN 2 — AI MODEL OPERATIONS

Now open AI Model Operations from the dropdown.

This page is the MLOps control tower.
It answers one operating question: are we actually putting the right model on the right task across the whole lab?

### Refresh

You can refresh by running all five patterns again.
Live runs can take minutes, so for demos prefer using results already loaded from Overview.

### Status strip

At the top you see scenarios completed, traces recorded, total model calls, escalation rate, and fallback rate.

Escalation tells you how often Confidence Cascade needed Frontier.
Fallback tells you how often the resilience path fired.

### KPI grid

The KPI grid expands the evidence.

You will see SLM calls versus Frontier calls, SLM tokens versus Frontier tokens, average and p95 latency, average confidence, illustrative cost, and cost avoided.

Again, the primary metric is Frontier tokens avoided.
Cost numbers are illustrative. Configure them with your provider pricing. They are not invoices.

### Charts

Next are the interactive charts.

Chart one shows token consumption by pattern, SLM versus Frontier.

Chart two compares the selected hybrid architecture against the estimated all-Frontier baseline.

Chart three shows the model usage mix by calls.

Chart four shows token trend over time.

Charts five and six show latency by model type and by pattern.

Chart seven shows illustrative cost by pattern.

Chart eight plots confidence against Frontier calls.

Chart nine shows Frontier avoidance rate. This is a strong executive pause point.

Chart ten shows tokens versus latency.

Chart eleven shows cost versus quality. The cheapest point is not automatically the best point. Quality must still clear the bar.

Chart twelve shows pattern usage by model calls.

The radar chart gives a multi-axis profile across confidence, Frontier avoidance, latency efficiency, and cost efficiency.

Chart labels use short names so they stay readable: Planner-Worker, Router, Cascade, RAG, and Fallback. Hover for the full pattern name.

### Efficiency table

Below the charts is the Pattern Efficiency Table.
One row per pattern.
This is the follow-up summary you can screenshot or share after the demo.

### Benefits callout

To close this page:
Planner-Worker is selective reasoning.
Router is high-volume efficiency.
Cascade is quality-aware escalation.
RAG is grounded smaller-model answers.
Fallback is availability.

That is AI Model Operations.

---

## DROPDOWN 3 — MODEL COMPARISON

Now open Model Comparison.

If Overview is the story and AI Model Operations is the portfolio evidence, Model Comparison is the decision audit.

### Header

This page compares the selected model path against the alternative path, segment by segment, using tokens, latency, confidence, cost, and the written rationale.

### If empty

If the page is empty, generate comparisons by running all patterns, or go back to Overview and load saved results first.

### Reading a pattern table

Each pattern has its own table.

Read left to right.

Selected tells you which model type ran: SLM, Frontier, or Non-LLM.

Selected tokens, latency, confidence, and provenance describe what actually happened on that path.

Alternative columns are estimated. They show what the other choice would likely have cost in tokens, latency, and confidence.
We label them ESTIMATED so we never pretend those were live second calls.

Decision and Why explain the recommendation in plain language.

### Example narration for an SLM row

Here is a routine segment.
We selected the SLM.
Tokens and latency stay lower.
Confidence is sufficient for the task.
The Frontier alternative is estimated to cost more without a meaningful quality need.
So SLM is the right model.

### Example narration for a Frontier row

Here is a hard segment such as planning or final RCA synthesis.
We selected Frontier.
Tokens and cost are higher.
Confidence justifies that spend.
Sending this to the SLM would be a false economy.
So Frontier is the right model.

### Example narration for a Non-LLM row

Not every step is a language model call.
Routers, confidence gates, retrievers, and failure detectors are Non-LLM controls.
They make the hybrid architecture work.

### Avoidance callout

Under each pattern you will also see Frontier tokens avoided, the avoidance percentage, and the architect recommendation.

That is the one-line verdict for the pattern.

That is Model Comparison.

---

## CLOSE

To recap the three dropdown pages.

Overview tells the story, shows the five patterns, and lets you inspect each scenario in detail.

AI Model Operations proves the portfolio economics with KPIs and charts.

Model Comparison defends each segment-level decision with selected versus estimated alternative evidence.

Right Model Lab: right model, right task, measurable evidence.

Thank you.

---

## SHORT VERSION (about 3 minutes)

Welcome to Right Model Lab. Use the right model for the right task. SLM for routine high-volume work. Frontier for planning, ambiguity, and synthesis.

On Overview, check mode and fleet health, then review the five pattern tiles: Planner-Worker, Router, Confidence Cascade, RAG, and Fallback. Open one pattern, load the saved result, and walk Scenario, Architecture Flow, Why This Model, Token Utilization, and the AI Architect Decision. The key metric is Frontier tokens avoided.

On AI Model Operations, review the KPI grid and charts. Pause on selected versus all-Frontier, Frontier avoidance rate, and cost versus quality. Cheapest is not automatically best.

On Model Comparison, audit selected versus estimated alternative by segment. Explain one SLM win and one Frontier win using the Why column.

That is the use case end to end. Thank you.
