# LangSmith Observability

LangSmith is a first-class component of this lab.

## Configuration

```env
LANGSMITH_ENABLED=true
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=slm-frontier-device-monitoring
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

The application runs when `LANGSMITH_ENABLED=false`. Local parent/child spans still power the **LangSmith / LLMOps** and **Trace Explorer** pages.

## Captured fields

Each span stores the `TokenMetrics` contract:

- pattern, scenario, device, segment
- model name / type / role / provider
- input/output/total/context tokens
- latency, estimated cost, confidence
- escalation / fallback / retrieval metadata
- provenance: ACTUAL / SIMULATED / ESTIMATED

## Trace shapes

### Planner-Worker

```
Planner-Worker RCA
├── FRONTIER — Planner
├── SLM — CPU Worker
├── SLM — Teams Worker
├── SLM — Network Worker
├── SLM — Compliance Worker
├── SLM — Incident Worker
└── FRONTIER — RCA Synthesis
```

### Router

```
Router Fleet Analysis
├── Router
├── Request 001 → SLM
├── Request 003 → Frontier
└── ...
```

### Confidence Cascade

```
Ambiguous Incident
├── SLM Initial Diagnosis
├── Confidence Evaluator
├── Escalation Decision
└── FRONTIER RCA
```

### RAG

```
RAG SOP Resolution
├── Query Analysis
├── Retrieval
├── Document Ranking
├── Context Construction
└── SLM Grounded Generation
```

### Fallback

```
Fallback RCA
├── FRONTIER Attempt
├── Failure Detector
├── Fallback Decision
└── SLM Fallback
```

Never commit API keys. The UI never displays secrets.
