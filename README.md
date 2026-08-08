# SLM + Frontier Device Monitoring Patterns

**Digital Workplace Device Monitoring Architecture Lab**

This repository is a complete working demonstration of how Small Language Models (SLMs) and Frontier Models collaborate using five enterprise architecture patterns.

Primary principle:

> **Use the right model for the right task.**

This lab does **not** try to replace Frontier models with SLMs. It shows where each creates value.

---

## What is an SLM?

An SLM is a smaller language model — think of it as an experienced Service Desk Engineer.

- Fast
- Lower cost
- Strong on known/repetitive work
- Ideal for classification, extraction, telemetry interpretation, and routine summaries

## What is a Frontier Model?

A Frontier model is a highly capable large model — think of it as a Senior Solution Architect.

- Stronger reasoning and planning
- Better at ambiguity and cross-domain synthesis
- More expensive and often slower
- Best reserved for high-value reasoning segments

## Why use both?

Most digital workplace workflows contain both:

1. routine high-volume steps, and
2. a smaller number of difficult reasoning steps.

Hybrid architecture protects Frontier capacity while preserving quality where it matters.

---

## The five patterns (one scenario each)

| Pattern | Scenario | SLM role | Frontier role | Primary benefit |
|---|---|---|---|---|
| Planner-Worker | Complete RCA for `LAPTOP-1204` | Routine workers | Plan + final RCA | Selective reasoning |
| Router | Route 100 endpoint health requests | Routine requests | Complex requests | High-volume efficiency |
| Confidence Cascade | Ambiguous Teams/VPN on `LAPTOP-9910` | First diagnosis | Escalate if unsure | Quality-aware escalation |
| RAG | `LAPTOP-1507` disk + OneDrive SOP | Grounded answer | Not required | Knowledge + smaller model |
| Fallback | Frontier unavailable during critical RCA | Degraded continuity | Primary path | Resilience/availability |

---

## How token consumption is measured

Every segment records:

- input / output / total tokens
- latency
- confidence
- estimated cost
- provenance label:
  - `ACTUAL` for provider telemetry
  - `SIMULATED` for Demo Mode
  - `ESTIMATED` for baselines/alternatives

Important metric:

> **Frontier tokens avoided**

not merely “total tokens saved.”

## Estimated All-Frontier baseline

The app compares hybrid execution against an **ESTIMATED ALL-FRONTIER BASELINE**.

It does **not** call Frontier just to invent that comparison. Baselines come from `BaselineEstimator` benchmarks and historical telemetry.

## Why fewer tokens is not automatically better

Example:

- SLM: fewer tokens, faster, cheaper, but 61% confidence on complex RCA
- Frontier: more tokens, slower, costlier, but 94% confidence

Decision: Frontier — quality requirement justifies the extra inference.

## What LangSmith does

LangSmith (and the local LLMOps views) show:

- which pattern/segment/model ran
- parent/child execution
- tokens, latency, cost, confidence
- escalation and fallback events
- retrieval metadata

## What MLOps / LLMOps means here

The **AI Model Operations** page visualizes model-selection decisions over time and by pattern: usage, avoidance, latency, cost, confidence, escalation, and fallback.

---

## Installation (Windows)

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Generate synthetic data

```bash
python -m app.data.generator
```

## Run the API

```bash
uvicorn app.main:app --reload --port 8000
```

## Run the Streamlit app

```bash
streamlit run app/ui/dashboard.py
```

## Run tests

```bash
pytest
```

Syntax validation:

```bash
python -m compileall app tests
```

---

## Demo Mode

Default:

```env
DEMO_MODE=true
```

Demo Mode:

- needs no Azure, Ollama, or LangSmith
- returns deterministic simulated results
- labels metrics as `SIMULATED`

---

## Ollama configuration (optional local SLM)

1. Install Ollama
2. Pull a model, for example: `ollama pull llama3.2`
3. Configure `.env`:

```env
DEMO_MODE=false
SLM_PROVIDER=ollama
SLM_MODEL=llama3.2
SLM_BASE_URL=http://localhost:11434
```

No specific model is hardcoded. Any Ollama-compatible model name can be used.

---

## Azure Frontier configuration (optional)

```env
DEMO_MODE=false
FRONTIER_PROVIDER=azure_openai
FRONTIER_MODEL=gpt-4o
AZURE_OPENAI_ENDPOINT=https://YOUR_RESOURCE.openai.azure.com/
AZURE_OPENAI_API_KEY=YOUR_KEY
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_DEPLOYMENT=YOUR_DEPLOYMENT
```

Business logic never imports Azure SDK types directly. Patterns call the shared `LanguageModel` interface.

---

## LangSmith configuration (optional)

```env
LANGSMITH_ENABLED=true
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=YOUR_KEY
LANGSMITH_PROJECT=slm-frontier-device-monitoring
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

If LangSmith is disabled, local traces still power the LLMOps pages.

---

## Demo walkthrough

### 1) Planner-Worker
Open **1 — Planner-Worker** → Execute → inspect Frontier plan/synthesis vs SLM workers and the “Why not Frontier for CPU?” callout.

### 2) Router
Open **2 — Router Pattern** → Execute → confirm ~85 SLM / ~15 Frontier and review routine vs complex examples.

### 3) Confidence Cascade
Open **3 — Confidence Cascade** → Execute → see SLM confidence 54% escalate, honest cascade-vs-direct token callout, then fleet economics.

### 4) RAG
Open **4 — RAG** → Execute → review retrieved SOP chunks, citations, grounding, and RAG+SLM vs estimated RAG+Frontier.

### 5) Fallback
Open **5 — Fallback** → choose failure mode → Execute → confirm degraded SLM continuity and resiliency callout.

Then open **AI Model Operations**, **LangSmith / LLMOps**, and **Trace Explorer**.

---

## Screenshots

> Placeholder: add UI screenshots for Overview, each pattern page, MLOps, and Trace Explorer before publishing a polished GitHub release.

---

## Project structure

See repository tree under `app/`, `tests/`, `docs/`, and `.github/workflows/`.

## Security

Never commit:

- `.env`
- API keys
- LangSmith keys
- Azure secrets

`.gitignore` is configured accordingly.

## Docker

```bash
docker compose up --build
```

- API: `http://localhost:8000`
- UI: `http://localhost:8501`

## License

MIT

## Future enhancements

- Azure AI Search retriever backend
- Live Intune/DEX connectors
- Richer LangSmith deep links per organization
- Additional offline evaluation suites
- Screenshot pack for GitHub social preview

---

## Publish to GitHub

```bash
git init
git add .
git commit -m "Initial SLM + Frontier device monitoring pattern lab"
git branch -M main
git remote add origin https://github.com/<your-org>/slm-frontier-device-monitoring-patterns.git
git push -u origin main
```

If you are already inside this cloned workspace branch, use your normal branch push workflow instead.
