# Architecture

## Principle

**Use the right model for the right task.**

This lab does not attempt to replace Frontier models with SLMs. It shows how to reserve Frontier capacity for planning, ambiguity resolution, and synthesis while using SLMs for routine high-volume work.

## Runtime

```
Streamlit UI
    |
    +--> ScenarioService / Pattern engines
              |
              +--> LanguageModel interface
              |      + DemoSLM / DemoFrontier
              |      + LocalSLM (Ollama-compatible)
              |      + AzureFrontier (Azure OpenAI-compatible)
              |
              +--> Telemetry + VectorStore (TF-IDF)
              |
              +--> LangSmithTracer + local TraceStore
              |
              +--> BaselineEstimator (Estimated All-Frontier)
```

## Five first-class patterns

1. Planner-Worker Hierarchy — LAPTOP-1204 multi-domain RCA
2. Router Pattern — 100 endpoint health requests
3. Confidence Cascade — LAPTOP-9910 ambiguous Teams/VPN
4. RAG — LAPTOP-1507 disk/OneDrive SOP remediation
5. Designing for Fallback — Frontier outage with SLM continuity

Each pattern has exactly one dedicated scenario.

## Observability

Every segment records model type, role, tokens, latency, cost, confidence, and provenance:

- **ACTUAL** — provider-reported usage
- **SIMULATED** — Demo Mode telemetry
- **ESTIMATED** — baseline/alternative projections (never presented as actual)
