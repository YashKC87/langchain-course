# UI Walkthrough — Explainable Pattern Dashboard

Open via Cursor **Ports → forward 8501 → http://localhost:8501**  
(Do not open the private VM IP from your laptop.)

## Overview
1. Confirm Mode LIVE/DEMO, SLM, Frontier, LangSmith, fleet strip.
2. Read KPI row: especially **Frontier Tokens Avoided**.
3. Use pattern tiles → **Open pattern**.

## Pattern pages (same 6-section structure)
1. Scenario + telemetry anomalies  
2. Architecture Flow (SLM / FRONTIER / NON-LLM labels)  
3. Why This Model? (selected vs alternative deltas)  
4. Token Utilization (Hybrid vs ESTIMATED All-Frontier)  
5. Performance Comparison (honest tradeoffs)  
6. LangSmith Trace + waterfall  

Then Tail View details + **AI Architect Decision**.

### Tips
- Click **Load latest saved result** for fast demos.
- Live Execute can take minutes (Ollama/Azure).
- Provenance badges: ACTUAL / SIMULATED / ESTIMATED.

## AI Model Operations
Review all KPIs and 12 charts. Focus on Frontier avoidance and cost vs quality.

## LangSmith / LLMOps
Inspect recent spans and pattern-specific trace meaning.

## Trace Explorer
Filter, select a trace, inspect waterfall + span drawer.

## Architecture / Model Comparison
Use for executive narrative and segment-level selected-vs-alternative review.
