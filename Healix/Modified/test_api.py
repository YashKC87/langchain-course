#!/usr/bin/env python3
# ============================================================
#  HEALIX v2.0 — API Test Script
#  Run this to verify your backend is working correctly.
#  Usage: python test_api.py
# ============================================================

import requests
import json
import sys

BASE_URL = "http://localhost:8000"

# ── Helper to print results nicely ────────────────────────────
def print_test(name, passed, response_data=None, error=None):
    status = "\u2705 PASS" if passed else "\u274C FAIL"
    print(f"\n{status} \u2014 {name}")
    if response_data and passed:
        text = json.dumps(response_data, indent=2)
        lines = text.split("\n")
        preview = "\n".join(lines[:8])
        if len(lines) > 8:
            preview += f"\n  ... ({len(lines)-8} more lines)"
        print(f"  Response preview:\n  {preview.replace(chr(10), chr(10)+'  ')}")
    if error:
        print(f"  Error: {error}")

def run_test(name, method, path, expected_keys=None, expected_status=200,
             json_body=None, timeout=10, extra_headers=None):
    """Generic test runner. Returns (passed, data)."""
    global tests_passed, tests_failed
    try:
        headers = extra_headers or {}
        if method == "GET":
            r = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=timeout)
        elif method == "POST":
            r = requests.post(f"{BASE_URL}{path}", json=json_body, headers=headers, timeout=timeout)
        elif method == "DELETE":
            r = requests.delete(f"{BASE_URL}{path}", headers=headers, timeout=timeout)
        else:
            raise ValueError(f"Unknown method: {method}")

        data = r.json()
        passed = r.status_code == expected_status
        if expected_keys:
            for key in expected_keys:
                if key not in data:
                    passed = False
        print_test(name, passed, data if passed else None,
                   error=None if passed else f"Status {r.status_code}, keys missing: {expected_keys}")
        if passed:
            tests_passed += 1
        else:
            tests_failed += 1
        return passed, data
    except Exception as e:
        print_test(name, False, error=str(e))
        tests_failed += 1
        return False, None


print("=" * 60)
print("  HEALIX v2.0 \u2014 API Test Suite")
print("  Make sure your server is running first!")
print("  Run: python main.py")
print("=" * 60)

tests_passed = 0
tests_failed = 0

# ═══════════════════════════════════════════════════════════════
#  SECTION 1: Core v1 Endpoints
# ═══════════════════════════════════════════════════════════════
print("\n\u2500\u2500 CORE ENDPOINTS \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")

# Test 1: Server is running
try:
    r = requests.get(f"{BASE_URL}/", timeout=5)
    if r.status_code == 200 and "HEALIX" in r.json().get("product", ""):
        print_test("Server is running (v2.0)", True, r.json())
        tests_passed += 1
    else:
        print_test("Server is running", False, error=f"Unexpected response: {r.text}")
        tests_failed += 1
except Exception as e:
    print_test("Server is running", False, error=f"Cannot connect.\n  Error: {e}")
    tests_failed += 1
    print("\n\u26D4 Cannot reach server. Please start it first with:\n   python main.py")
    sys.exit(1)

# Test 2: Health check (now includes service status)
run_test("Health check with service status", "GET", "/health",
         expected_keys=["status", "services"])

# Test 3: Get endpoints
run_test("Get endpoints", "GET", "/api/endpoints",
         expected_keys=["endpoints", "count"])

# Test 4: Get alerts
run_test("Get alerts", "GET", "/api/alerts",
         expected_keys=["alerts"])

# Test 5: Get healing actions
run_test("Get healing actions", "GET", "/api/healing-actions",
         expected_keys=["actions"])

# Test 6: AI Agent chat
run_test("AI Agent chat (RAG + LLM)", "POST", "/api/agent/chat",
         json_body={"question": "Why is EDGE-NODE-07 critical?"},
         expected_keys=["answer", "sources"], timeout=30)

# Test 7: Trigger remediation
run_test("Trigger auto-remediation", "POST", "/api/healing/trigger",
         json_body={"endpoint_id": "EP-005", "issue_type": "high_cpu"},
         expected_keys=["status", "action"], timeout=15)

# Test 8: Predictions
run_test("Failure predictions", "GET", "/api/predictions",
         expected_keys=["predictions"])

# Test 9: Patch intelligence
run_test("Patch intelligence", "GET", "/api/patches",
         expected_keys=["patches"])


# ═══════════════════════════════════════════════════════════════
#  SECTION 2: Microsoft Integration Endpoints
# ═══════════════════════════════════════════════════════════════
print("\n\u2500\u2500 MICROSOFT INTEGRATIONS \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")

run_test("Microsoft services status", "GET", "/api/microsoft/status")

run_test("Defender incidents", "GET", "/api/microsoft/defender/incidents")

run_test("Defender security alerts", "GET", "/api/microsoft/defender/alerts")

run_test("Intune managed devices", "GET", "/api/microsoft/intune/devices")

run_test("Entra risky users", "GET", "/api/microsoft/entra/risky-users")


# ═══════════════════════════════════════════════════════════════
#  SECTION 3: Log Management
# ═══════════════════════════════════════════════════════════════
print("\n\u2500\u2500 LOG MANAGEMENT \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")

run_test("Query logs", "GET", "/api/logs?limit=10")

run_test("Log statistics", "GET", "/api/logs/stats")

run_test("Log sources", "GET", "/api/logs/sources")

# Test log ingestion
run_test("Ingest custom logs", "POST", "/api/logs/ingest",
         json_body={
             "source": "test_script",
             "entries": [
                 {"severity": "info", "message": "Test log entry from test_api.py",
                  "endpoint_name": "TEST-SRV-01", "category": "test"}
             ]
         })


# ═══════════════════════════════════════════════════════════════
#  SECTION 4: Alert Management
# ═══════════════════════════════════════════════════════════════
print("\n\u2500\u2500 ALERT MANAGEMENT \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")

run_test("List alerts from DB", "GET", "/api/alerts/list")

run_test("Alert statistics", "GET", "/api/alerts/stats")

run_test("List alert rules", "GET", "/api/alerts/rules")


# ═══════════════════════════════════════════════════════════════
#  SECTION 5: Compliance
# ═══════════════════════════════════════════════════════════════
print("\n\u2500\u2500 COMPLIANCE \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")

run_test("Security posture", "GET", "/api/compliance/posture")

run_test("Compliance gaps", "GET", "/api/compliance/gaps")

run_test("Posture history", "GET", "/api/compliance/posture/history")


# ═══════════════════════════════════════════════════════════════
#  SECTION 6: Monitoring
# ═══════════════════════════════════════════════════════════════
print("\n\u2500\u2500 MONITORING \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")

run_test("System overview", "GET", "/api/monitoring/overview")

run_test("List monitored endpoints", "GET", "/api/monitoring/endpoints",
         expected_keys=["endpoints"])

run_test("Anomaly detection", "GET", "/api/monitoring/anomalies",
         expected_keys=["anomalies"])

run_test("Heartbeat status", "GET", "/api/monitoring/heartbeat")


# ═══════════════════════════════════════════════════════════════
#  SECTION 7: Dashboards
# ═══════════════════════════════════════════════════════════════
print("\n\u2500\u2500 DASHBOARDS \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")

run_test("Executive dashboard", "GET", "/api/dashboards/executive")

run_test("Security dashboard", "GET", "/api/dashboards/security")

run_test("Operations dashboard", "GET", "/api/dashboards/operations")

run_test("Compliance dashboard", "GET", "/api/dashboards/compliance")


# ═══════════════════════════════════════════════════════════════
#  SECTION 8: Usage Analytics
# ═══════════════════════════════════════════════════════════════
print("\n\u2500\u2500 USAGE ANALYTICS \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")

run_test("Usage summary", "GET", "/api/usage/summary")

run_test("Adoption metrics", "GET", "/api/usage/adoption")

run_test("Workload distribution", "GET", "/api/usage/workload")

run_test("Efficiency metrics", "GET", "/api/usage/efficiency")


# ═══════════════════════════════════════════════════════════════
#  SECTION 9: Workflows
# ═══════════════════════════════════════════════════════════════
print("\n\u2500\u2500 WORKFLOWS \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")

run_test("Workflow history", "GET", "/api/workflows/history")


# ═══════════════════════════════════════════════════════════════
#  SECTION 10: Error Handling
# ═══════════════════════════════════════════════════════════════
print("\n\u2500\u2500 ERROR HANDLING \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")

# Empty question should return 400
run_test("Reject empty chat question", "POST", "/api/agent/chat",
         json_body={"question": ""}, expected_status=400)

# Non-existent endpoint detail should return 404
run_test("404 on unknown endpoint detail", "GET",
         "/api/monitoring/endpoints/DOES-NOT-EXIST", expected_status=404)


# ═══════════════════════════════════════════════════════════════
#  SECTION 11: Azure Monitor (VM polling via ARM API)
# ═══════════════════════════════════════════════════════════════
print("\n\u2500\u2500 AZURE MONITOR \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")

run_test("Azure Monitor status", "GET", "/api/azure/status",
         expected_keys=["available", "demo_mode"])

run_test("Azure VM list", "GET", "/api/azure/vms",
         expected_keys=["vms", "count"])


# ═══════════════════════════════════════════════════════════════
#  SECTION 12: AWS Monitoring (EC2 / CloudWatch)
# ═══════════════════════════════════════════════════════════════
print("\n\u2500\u2500 AWS MONITORING \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")

run_test("AWS client status", "GET", "/api/aws/status",
         expected_keys=["available", "demo_mode", "boto3_installed"])

run_test("AWS EC2 instance list", "GET", "/api/aws/instances",
         expected_keys=["instances", "count"])

run_test("AWS instance metrics (demo)", "GET",
         "/api/aws/instance/i-0abc123456789001/metrics?hours=1",
         expected_keys=["instance_id", "metrics"])


# ═══════════════════════════════════════════════════════════════
#  SECTION 13: Azure AI Foundry
# ═══════════════════════════════════════════════════════════════
print("\n\u2500\u2500 AZURE AI FOUNDRY \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")

run_test("Foundry status", "GET", "/api/foundry/status",
         expected_keys=["foundry_available", "agent_provider"])

run_test("Foundry model info", "GET", "/api/foundry/model-info",
         expected_keys=["provider", "available"])

run_test("Foundry direct chat (demo)", "POST", "/api/foundry/chat",
         json_body={"message": "What is HEALIX?"},
         expected_keys=["answer", "provider"], timeout=15)


# ═══════════════════════════════════════════════════════════════
#  SECTION 14: Integration API v1
# ═══════════════════════════════════════════════════════════════
print("\n\u2500\u2500 INTEGRATION API v1 \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")

# API key for testing (works in dev mode even with random key)
_auth = {"Authorization": "Bearer test-key-for-ci"}

run_test("v1 platform status", "GET", "/api/v1/status",
         expected_keys=["success", "data"], extra_headers=_auth)

run_test("v1 endpoints list", "GET", "/api/v1/endpoints",
         expected_keys=["success", "data"], extra_headers=_auth)

run_test("v1 active alerts", "GET", "/api/v1/alerts",
         expected_keys=["success", "data"], extra_headers=_auth)

run_test("v1 compliance posture", "GET", "/api/v1/compliance",
         expected_keys=["success", "data"], extra_headers=_auth)

run_test("v1 AI query", "POST", "/api/v1/query",
         json_body={"question": "What is the current CPU status?"},
         expected_keys=["success", "data"], extra_headers=_auth, timeout=30)

run_test("v1 push event", "POST", "/api/v1/events",
         json_body={"source": "test_script", "severity": "info",
                    "message": "Integration API test event", "endpoint_name": "TEST-01"},
         expected_keys=["success", "data"], extra_headers=_auth)

_, wh_data = run_test("v1 webhook register", "POST", "/api/v1/webhook/register",
         json_body={"url": "https://httpbin.org/post", "events": ["alert"],
                    "description": "CI test webhook"},
         expected_keys=["success", "data"], extra_headers=_auth)

run_test("v1 webhook list", "GET", "/api/v1/webhook/list",
         expected_keys=["success", "data"], extra_headers=_auth)


# ═══════════════════════════════════════════════════════════════
#  SUMMARY
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
total = tests_passed + tests_failed
print(f"  Results: {tests_passed}/{total} tests passed")
if tests_failed == 0:
    print("  \U0001F389 All tests passed! HEALIX v2.0 backend is fully operational.")
    print("\n  Next steps:")
    print("    \u2022 Open http://localhost:8000/docs for interactive Swagger docs")
    print("    \u2022 Load healix-agent.jsx in your React app to see the full UI")
    print("    \u2022 Add Azure credentials to .env for real Microsoft integrations")
else:
    print(f"  \u26A0\uFE0F  {tests_failed} test(s) failed. Check the errors above.")
    print("  Note: Some failures in demo mode (no Azure credentials) are expected.")
print("=" * 60)
