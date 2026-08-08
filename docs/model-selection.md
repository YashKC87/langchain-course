# Model Selection Guidance

## When to use an SLM

- Repetitive tasks
- Classification and extraction
- Telemetry interpretation
- Known troubleshooting
- Simple summarization
- Deterministic/routine analysis
- High-volume or low-latency workloads
- Cost-sensitive operations

## When to use a Frontier model

- Complex planning
- Cross-domain correlation
- Ambiguity resolution
- Novel problems
- High-stakes synthesis

## When to use both

- Planner-Worker orchestration
- Confidence Cascade escalation paths
- Router fleets with mixed difficulty
- Fallback designs that keep Frontier as primary

## Important comparison rule

Fewer tokens is **not** automatically better.

Always evaluate:

- Token usage
- Cost
- Latency
- Confidence / quality
- Success
- Grounding
- Escalation behavior
- Availability

## Estimated All-Frontier baseline

The lab never calls Frontier solely to compute “what if everything used Frontier?”

`BaselineEstimator` uses configured benchmarks and historical telemetry and labels the result:

**ESTIMATED ALL-FRONTIER BASELINE**
