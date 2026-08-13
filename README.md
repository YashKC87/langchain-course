# Agent Metering & Observability Control Center

One live control center to discover, meter, observe, trace, and optimize AI agents across Azure, AWS, Google Cloud, local environments, agent frameworks, MCP servers, RAG systems, enterprise tools, and multi-agent architectures.

**Connect → Enable → Discover → Observe → Trace → Optimize**

## What this is

A production-oriented, multi-cloud, framework-agnostic operational control plane for AI agents. It is:

- OpenTelemetry-based
- Live-data driven (no synthetic operational telemetry in the UI)
- Provider-neutral after normalization
- Built around graphical execution workflows

### Explicitly out of scope

FinOps, cost, billing, pricing, budgets, chargeback, showback, ROI, and financial forecasting are **not** part of this product.

## Architecture

```text
Agent Platform
      ↓
Platform Connector
      ↓
OpenTelemetry / Provider Telemetry
      ↓
Telemetry Collector
      ↓
Normalization Layer
      ↓
Agent Discovery → Agent Registry → Metering Engine
      ↓
Observability Store → Analytics API → Unified Dashboard
      ↓
Tracing / Health / Optimization
```

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | React, TypeScript, Vite, React Flow |
| Backend | Python FastAPI |
| Telemetry | OpenTelemetry (OTLP JSON / simplified spans) |
| Storage (MVP) | In-memory observability store (swap-ready) |

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 20+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### 1. Environment

```bash
cp .env.example .env
# Edit as needed — never commit real credentials
```

### 2. Backend

```bash
cd backend
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

UI: http://localhost:5173

### 4. Optional — OpenTelemetry Collector

```bash
docker compose up otel-collector
```

Point agent exporters at `http://localhost:4318` (OTLP HTTP).

### Docker Compose (full stack)

```bash
docker compose up --build
```

## First-time experience

With no integrations enabled, the Overview page shows **Connect Your First Platform**:

- Microsoft Azure
- AWS
- Google Cloud
- OpenTelemetry

Configure → Test → Enable. The ON/OFF switch runs:

```text
Check Config → Authenticate → Permissions → Endpoint →
Telemetry Access → Discover Agents → Register → Monitoring
```

If discovery finds nothing:

> Connection successful. No agents discovered.

The UI never invents agents or KPI values.

## Ingesting live telemetry

Enable the OpenTelemetry integration, then POST spans:

```bash
curl -X POST 'http://localhost:8000/api/v1/telemetry/spans?integration_id=otel' \
  -H 'Content-Type: application/json' \
  -d '{
    "spans": [{
      "name": "agent.run",
      "span_id": "s1",
      "trace_id": "t1",
      "status": "ok",
      "start_time": "2026-04-11T12:00:00+00:00",
      "end_time": "2026-04-11T12:00:01+00:00",
      "attributes": {
        "agent.id": "demo-agent",
        "agent.name": "Demo Agent",
        "cloud.provider": "azure",
        "framework.name": "langgraph",
        "gen_ai.request.model": "gpt-4o",
        "prompt_tokens": 100,
        "completion_tokens": 40
      }
    }]
  }'
```

OTLP JSON (`resourceSpans`) is also accepted at `/api/v1/telemetry/otlp`.

## Navigation

1. Overview  
2. Agents  
3. Live Executions  
4. Workflow  
5. Models  
6. Tools & MCP  
7. RAG  
8. Multi-Agent / A2A  
9. Integrations  
10. Observability  
11. Optimization  
12. Settings  

## MVP integrations

Prioritized connectors (catalog + config + toggle; live ingest via OTel first):

1. Generic OpenTelemetry  
2. Microsoft Foundry / Application Insights  
3. AWS Bedrock / AgentCore / CloudWatch  
4. Google Vertex AI / Cloud Observability  
5. LangSmith  

Additional catalog entries (MCP, ServiceNow, Datadog, etc.) are present for configuration and extension without redesigning the platform.

## Non-negotiable rules

1. No synthetic operational data in the production UI  
2. Missing telemetry stays visibly missing (`—` / No live data)  
3. No FinOps fields  
4. Graphical workflows are built only from real traces  
5. Prompts/responses are not stored by default (`Content Capture = OFF`)  
6. Secrets are never returned to the frontend in plaintext  

## Tests

```bash
cd backend && source .venv/bin/activate && pytest -q
```

Tests assert empty-state behaviour, token normalization (Azure/AWS/GCP → canonical), integration toggle workflows, workflow generation, runaway detection, and that empty ingest never creates fake agents.

## Project layout

```text
backend/          FastAPI app, services, connectors, tests
frontend/         React control center UI
collector/        Example OTel Collector config
docker-compose.yml
.env.example
```

## Security notes

- RBAC roles: Platform Administrator, Observability Administrator, Agent Owner, Business Unit Owner, Operations Engineer, Auditor, Viewer  
- Dev mode uses optional `X-Role` header when `AUTH_ENABLED=true`  
- Wire enterprise IdP (Entra ID / IAM / Workload Identity) before production  

## License

Proprietary — internal enterprise use unless otherwise specified.
