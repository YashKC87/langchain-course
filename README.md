# Right Model Lab

**SLM + Frontier Device Monitoring Patterns**

A complete, runnable lab that shows how Small Language Models (SLMs) and Frontier models work together for digital workplace device monitoring — using five enterprise architecture patterns, measurable token/cost/latency evidence, and optional LangSmith observability.

Primary principle:

> **Use the right model for the right task.**

This lab does **not** try to replace Frontier models with SLMs. It shows where each creates value: Frontier for planning, ambiguity, and synthesis; SLM for routine high-volume work.

---

## Table of contents

1. [What this use case is](#1-what-this-use-case-is)
2. [How the system is built](#2-how-the-system-is-built)
3. [The five patterns](#3-the-five-patterns)
4. [Project structure](#4-project-structure)
5. [End-to-end request flow](#5-end-to-end-request-flow)
6. [Model abstraction layer](#6-model-abstraction-layer)
7. [Data, knowledge, and persistence](#7-data-knowledge-and-persistence)
8. [Observability and metrics](#8-observability-and-metrics)
9. [UI pages](#9-ui-pages)
10. [Installation and run](#10-installation-and-run)
11. [Configuration](#11-configuration)
12. [Demo walkthrough](#12-demo-walkthrough)
13. [API reference](#13-api-reference)
14. [Tests, Docker, and export](#14-tests-docker-and-export)
15. [Security](#15-security)

---

## 1. What this use case is

Digital workplace fleets generate a mix of:

- **routine high-volume work** (health checks, known SOP remediation, simple status), and
- **harder reasoning work** (multi-domain RCA, ambiguous symptoms, synthesis).

Sending everything to a Frontier model wastes capacity and cost. Sending everything to an SLM risks quality on hard cases.

**Right Model Lab** demonstrates a hybrid approach with five locked scenarios on a synthetic endpoint fleet (for example `LAPTOP-1204`, `LAPTOP-1507`, `LAPTOP-9910`).

Executive analogy:

| Model | Analogy | Best for |
|---|---|---|
| **SLM** | Experienced Service Desk Engineer | Fast, lower-cost, known/repetitive work |
| **Frontier** | Senior Solution Architect | Planning, ambiguity, cross-domain synthesis |

---

## 2. How the system is built

The lab is a Python 3.11 application with four layers:

```
┌─────────────────────────────────────────────────────────────┐
│  UI (Streamlit) — Right Model Lab                            │
│  Overview · AI Model Operations · Model Comparison           │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│  API / Orchestration                                         │
│  FastAPI (app/main.py) + ScenarioService                     │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│  Pattern engines (one scenario each)                         │
│  Planner-Worker · Router · Cascade · RAG · Fallback          │
└───────────────┬─────────────────────────────┬───────────────┘
                │                             │
┌───────────────▼───────────────┐   ┌─────────▼───────────────┐
│  LanguageModel interface      │   │  Observability          │
│  Demo / Ollama SLM            │   │  TraceStore + LangSmith │
│  Demo / Azure Frontier        │   │  TokenMetrics + cost    │
└───────────────────────────────┘   └─────────────────────────┘
```

### Design choices baked into the build

| Choice | Why it matters |
|---|---|
| One locked scenario per pattern | Keeps demos deterministic and explainable |
| Shared `LanguageModel` interface | Patterns never import Azure/Ollama SDKs directly |
| `DEMO_MODE` by default | Works with zero cloud credentials |
| Provenance labels (`ACTUAL` / `SIMULATED` / `ESTIMATED`) | Prevents fake “savings” claims |
| Estimated All-Frontier baseline | Compares hybrid vs all-Frontier **without** calling Frontier just for the baseline |
| Primary metric = **Frontier tokens avoided** | Not “total tokens went down” |

---

## 3. The five patterns

| Pattern | Locked scenario | SLM role | Frontier role | Primary benefit |
|---|---|---|---|---|
| **Planner-Worker** | Complete RCA for `LAPTOP-1204` | Routine investigation workers | Plan + final RCA synthesis | Selective reasoning |
| **Router** | Route 100 endpoint health requests | Routine health/status | Complex/ambiguous RCA | High-volume efficiency |
| **Confidence Cascade** | Ambiguous Teams + VPN on `LAPTOP-9910` | First-pass diagnosis | Escalate when confidence is low | Quality-aware escalation |
| **RAG** | `LAPTOP-1507` disk/OneDrive SOP remediation | Grounded generation from retrieved SOPs | Not required for this scenario | Grounded smaller-model answers |
| **Fallback** | Critical RCA while Frontier is unavailable | Degraded continuity | Primary advanced path | Resilience / availability |

Architecture flows (also rendered in the UI **Architecture** page):

```
Planner-Worker
  Incident → FRONTIER Planner → SLM Workers (parallel) → FRONTIER RCA

Router
  Requests → NON-LLM Router → SLM (routine) | FRONTIER (complex)

Confidence Cascade
  Incident → SLM diagnosis → NON-LLM confidence gate → accept | FRONTIER escalate

RAG
  Ticket → NON-LLM retrieve/rank SOP → SLM grounded answer

Fallback
  Incident → FRONTIER attempt → NON-LLM failure detector → FRONTIER OK | SLM fallback
```

Fallback failure modes you can simulate: `http_503`, `timeout`, `rate_limit`, `auth_error`, `offline`, `cost_guard`.

---

## 4. Project structure

```text
.
├── app/
│   ├── config.py                 # Settings from .env (pydantic-settings)
│   ├── main.py                   # FastAPI app
│   ├── data/
│   │   ├── generator.py          # Synthetic devices + incidents
│   │   ├── devices.csv
│   │   ├── incidents.csv
│   │   └── knowledge_base/       # Markdown SOPs for RAG
│   ├── models/
│   │   ├── model_interface.py    # LanguageModel contract
│   │   ├── factory.py            # Demo / Ollama / Azure wiring
│   │   ├── slm_client.py         # Local SLM (Ollama-compatible)
│   │   ├── frontier_client.py    # Azure OpenAI-compatible Frontier
│   │   ├── demo_model.py         # Deterministic Demo clients
│   │   └── schemas.py            # PatternResult, SegmentResult, etc.
│   ├── patterns/
│   │   ├── planner_worker.py
│   │   ├── router.py
│   │   ├── confidence_cascade.py
│   │   ├── rag.py
│   │   ├── fallback.py
│   │   └── common.py             # Shared helpers / registry
│   ├── services/
│   │   ├── scenario_service.py   # Orchestrates pattern runs + MLOps KPIs
│   │   ├── baseline_estimator.py # ESTIMATED all-Frontier baselines
│   │   ├── telemetry.py
│   │   ├── vector_store.py       # TF-IDF retrieval for RAG
│   │   └── result_store.py       # Persist latest pattern results
│   ├── observability/
│   │   ├── langsmith_tracer.py   # Remote + local tracing
│   │   ├── trace_store.py        # .local_traces.json
│   │   ├── token_metrics.py
│   │   └── cost_calculator.py    # Illustrative USD pricing
│   └── ui/
│       ├── dashboard.py          # Streamlit entrypoint
│       ├── pattern_architecture.py
│       ├── architecture_components.py
│       ├── token_charts.py
│       ├── mlops_dashboard.py
│       ├── theme.py
│       └── trace_explorer.py
├── tests/                        # pytest suite (forced Demo Mode)
├── docs/                         # Deeper docs + optional static HTML report
├── scripts/export_static_report.py
├── main.py                       # Convenience launcher: api | ui | data | test
├── requirements.txt
├── pyproject.toml
├── docker-compose.yml
└── .env.example
```

---

## 5. End-to-end request flow

When you click **Execute** on a pattern (or call the API):

1. **UI / API** asks `ScenarioService.run_pattern(pattern_id)`.
2. Service resolves the pattern class from `PATTERN_REGISTRY`.
3. Pattern builds prompts/tasks for its locked scenario.
4. Pattern calls SLM and/or Frontier through the `LanguageModel` interface.
5. Each segment records tokens, latency, confidence, cost, and provenance.
6. `LangSmithTracer` writes a parent/child span tree locally (and to LangSmith when configured).
7. `BaselineEstimator` attaches an **ESTIMATED** all-Frontier comparison.
8. `ResultStore` saves the latest `PatternResult` to `.local_pattern_results.json`.
9. UI renders architecture flow, “why this model”, token charts, and the AI Architect decision.

```text
User → Streamlit/API → ScenarioService → Pattern.run()
         → SLM/Frontier clients
         → TraceStore (+ LangSmith)
         → ResultStore
         → Charts / Architecture / Comparison views
```

---

## 6. Model abstraction layer

Business logic never imports provider SDKs directly.

```text
LanguageModel (interface)
├── DemoSLMClient / DemoFrontierClient     # DEMO_MODE or missing Azure config
├── LocalSLMClient                         # Ollama-compatible HTTP API
└── AzureFrontierClient                    # Azure OpenAI-compatible Converse/chat
```

Factory selection (`app/models/factory.py`) is driven by `.env`:

- `DEMO_MODE=true` → always Demo clients (safe default)
- `DEMO_MODE=false` + Ollama settings → live SLM
- `DEMO_MODE=false` + complete Azure settings → live Frontier
- Incomplete Azure Frontier config falls back to Demo Frontier so the app still runs

---

## 7. Data, knowledge, and persistence

### Synthetic fleet

`python -m app.data.generator` (also auto-runs on UI/API startup) creates:

- `app/data/devices.csv` — endpoint fleet (seeded, deterministic)
- `app/data/incidents.csv` — incident records for demos

Special devices used by locked scenarios include `LAPTOP-1204`, `LAPTOP-1507`, and `LAPTOP-9910`.

### Knowledge base (RAG)

Markdown SOPs under `app/data/knowledge_base/` (disk, OneDrive, Teams, VPN, etc.) are indexed with a lightweight TF-IDF `VectorStore` — enough to demonstrate grounded retrieval without an external vector database.

### Local persistence (gitignored)

| File | Purpose |
|---|---|
| `.local_pattern_results.json` | Latest result per pattern (“Load latest saved result”) |
| `.local_traces.json` | Local parent/child spans for MLOps views |

---

## 8. Observability and metrics

Every segment records:

- pattern / scenario / device / segment
- model type (`SLM` | `FRONTIER` | `NON_LLM`) and role
- input / output / total tokens
- latency, confidence, illustrative cost
- escalation / fallback / retrieval metadata
- provenance:
  - **`ACTUAL`** — provider-reported usage
  - **`SIMULATED`** — Demo Mode telemetry
  - **`ESTIMATED`** — baseline or alternative projections (never shown as actual)

### Primary efficiency metric

> **Frontier tokens avoided** (hybrid vs ESTIMATED all-Frontier baseline)

Fewer total tokens is **not** automatically better if quality collapses. The Confidence Cascade page intentionally shows cases where escalation can cost more than a direct Frontier call — fleet economics still matter.

### LangSmith (optional)

When enabled, the same spans can stream to a LangSmith project. If LangSmith is off, local traces still power the AI Model Operations views.

---

## 9. UI pages

Streamlit app brand: **Right Model Lab** (`streamlit run app/ui/dashboard.py`).

| Page | What it shows |
|---|---|
| **Overview** | Fleet KPIs, pattern tiles, Run all / Open pattern detail (architecture diagram + execute or load saved) |
| **AI Model Operations** | MLOps KPIs and interactive charts (usage, avoidance, latency, cost, confidence) |
| **Model Comparison** | Selected hybrid vs alternative/estimated segments by pattern |

- Video narration by dropdown page: [`docs/video-script.md`](docs/video-script.md)
- Section-by-section write-up for each dropdown: [`docs/dropdown-section-writeup.md`](docs/dropdown-section-writeup.md)
- Full technical use-case demonstration (every element): [`docs/use-case-demonstration.md`](docs/use-case-demonstration.md)
- Catalogue PowerPoint (complete use case): [`docs/Right-Model-Lab-Catalogue.pptx`](docs/Right-Model-Lab-Catalogue.pptx) — regenerate with `python scripts/build_catalogue_pptx.py`

Theme: Dark / Light toggle in the left sidebar.

Pattern detail (from Overview → **Open**) includes:

1. Architecture diagram for that pattern  
2. Execute / Load latest saved result  
3. Scenario context  
4. Architecture flow of executed segments  
5. Why this model  
6. Token utilization vs ESTIMATED all-Frontier  
7. Performance + AI Architect decision  

---

## 10. Installation and run

### Prerequisites

- Python **3.11+**
- Optional: [Ollama](https://ollama.com) for local SLM
- Optional: Azure OpenAI deployment for Frontier
- Optional: LangSmith API key for remote tracing

### Setup

Windows:

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

### Generate data

```bash
python -m app.data.generator
# or
python main.py data
```

### Run the Streamlit UI

```bash
streamlit run app/ui/dashboard.py
# or
python main.py ui
```

Open `http://localhost:8501`.

### Run the FastAPI service

```bash
uvicorn app.main:app --reload --port 8000
# or
python main.py api
```

Open `http://localhost:8000/docs` for interactive OpenAPI docs.

### Run tests

```bash
pytest
# or
python main.py test
```

Syntax check:

```bash
python -m compileall app tests
```

---

## 11. Configuration

Copy `.env.example` → `.env` and edit. Never commit `.env`.

### Demo Mode (default)

```env
DEMO_MODE=true
```

- No Azure, Ollama, or LangSmith required
- Deterministic simulated results
- Metrics labeled `SIMULATED`

### Live local SLM (Ollama)

```env
DEMO_MODE=false
SLM_PROVIDER=ollama
SLM_MODEL=llama3.2
SLM_BASE_URL=http://localhost:11434
SLM_TIMEOUT_SECONDS=180
```

```bash
ollama pull llama3.2
ollama serve
```

Any Ollama-compatible model name can be used — nothing is hardcoded beyond the example.

### Live Frontier (Azure OpenAI-compatible)

```env
DEMO_MODE=false
FRONTIER_PROVIDER=azure_openai
FRONTIER_MODEL=gpt-4o
AZURE_OPENAI_ENDPOINT=https://YOUR_RESOURCE.openai.azure.com/
AZURE_OPENAI_API_KEY=YOUR_KEY
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_DEPLOYMENT=YOUR_DEPLOYMENT
```

Use the resource root endpoint (for example `https://YOUR_RESOURCE.openai.azure.com/`). Do not append `/openai/v1` — the client normalizes the Azure path.

### LangSmith (optional)

```env
LANGSMITH_ENABLED=true
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=YOUR_KEY
LANGSMITH_PROJECT=slm-frontier-device-monitoring
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

### Other knobs

```env
CONFIDENCE_THRESHOLD=0.85
ILLUSTRATIVE_SLM_INPUT_COST_PER_1K=0.0001
ILLUSTRATIVE_SLM_OUTPUT_COST_PER_1K=0.0002
ILLUSTRATIVE_FRONTIER_INPUT_COST_PER_1K=0.005
ILLUSTRATIVE_FRONTIER_OUTPUT_COST_PER_1K=0.015
```

Pricing values are **illustrative USD per 1K tokens**, not market facts. Configure them to match your provider pricing for demos.

---

## 12. Demo walkthrough

1. Start with `DEMO_MODE=true` and open the UI.
2. On **Overview**, click **Run all patterns** (or open each tile → **Execute** / **Load latest saved result**).
3. Open a pattern tile to see its architecture diagram and run/load results.
4. Open **AI Model Operations** for avoidance, latency, cost, and confidence charts.
5. Open **Model Comparison** for selected vs alternative segment tables.

Pattern-specific checks:

| Pattern | What to look for |
|---|---|
| Planner-Worker | Frontier plan + synthesis; SLM workers on routine domains |
| Router | Roughly high SLM share vs smaller Frontier share across 100 requests |
| Confidence Cascade | Low-confidence SLM escalates; honest cost vs direct-Frontier callout |
| RAG | Retrieved SOP chunks + grounded SLM answer; Frontier not required |
| Fallback | Choose a failure mode; SLM continues with degraded quality |

For live demos, prefer **Load latest saved result** first so the room is not waiting on multi-minute Ollama/Azure calls.

---

## 13. API reference

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness |
| `GET` | `/api/v1/config` | Public config / provider status (no secrets) |
| `GET` | `/api/v1/patterns` | Pattern catalog |
| `POST` | `/api/v1/patterns/{pattern_id}/run` | Run one pattern |
| `POST` | `/api/v1/patterns/run-all` | Run all five |
| `GET` | `/api/v1/devices` | Synthetic fleet |
| `GET` | `/api/v1/overview` | Overview cards |
| `GET` | `/api/v1/mlops` | MLOps dashboard payload |
| `GET` | `/api/v1/traces` | Local trace listing |

---

## 14. Tests, Docker, and export

### Tests

`tests/` covers planner-worker, router, confidence cascade, RAG, fallback, and token metrics. CI and local pytest force Demo Mode so runs stay offline and deterministic.

### Docker

```bash
docker compose up --build
```

- API: `http://localhost:8000`
- UI: `http://localhost:8501`

### Static HTML report

After you have saved pattern results:

```bash
PYTHONPATH=. python scripts/export_static_report.py
```

Writes `docs/right-model-lab-report.html` (no secrets).

### Deeper docs

| Doc | Topic |
|---|---|
| `docs/architecture.md` | Runtime architecture |
| `docs/patterns.md` | Pattern/scenario notes |
| `docs/model-selection.md` | Selection rationale |
| `docs/langsmith-observability.md` | Tracing details |
| `docs/ui-walkthrough.md` | UI section guide |
| `docs/use-case-demonstration.md` | Detailed technical demo of every lab element |
| `docs/video-script.md` | Video narration by dropdown page |

---

## 15. Security

Never commit:

- `.env`
- Azure / LangSmith API keys
- Local result or trace JSON if it contains sensitive demo content you do not want shared

The UI and `/api/v1/config` expose **public status only** (provider names, model names, active flags) — secrets are never rendered.

---

## License

MIT

## Future enhancements

- Azure AI Search (or similar) retriever backend
- Live Intune / DEX connectors
- Richer per-org LangSmith deep links
- Additional offline evaluation suites
- Screenshot pack for GitHub social preview
