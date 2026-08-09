# Patterns and Scenarios

## 1. Planner-Worker Hierarchy

**Scenario:** Complete multi-domain RCA for LAPTOP-1204.

Frontier plans and synthesizes. SLM workers analyze CPU/memory, Teams, network/VPN, compliance, and history.

## 2. Router Pattern

**Scenario:** Route 100 incoming endpoint health requests.

Routine checks go to SLM. Complex/ambiguous RCA goes to Frontier.

## 3. Confidence Cascade

**Scenario:** Investigate ambiguous Teams + VPN instability on LAPTOP-9910.

SLM attempts first. If confidence < 85%, escalate to Frontier. An escalated case can cost more than direct Frontier; fleet economics still matter.

## 4. RAG

**Scenario:** LAPTOP-1507 low disk + OneDrive errors — approved SOP remediation.

TF-IDF retrieval supplies enterprise knowledge. SLM generates the grounded answer.

## 5. Designing for Fallback

**Scenario:** Critical RCA while Frontier is unavailable.

Failure modes: HTTP 503, timeout, rate limit, auth/service error, offline, cost guard. SLM preserves availability with degraded quality.
