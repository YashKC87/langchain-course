#!/usr/bin/env python3
# ============================================================
#  HEALIX — API Test Script
#  Run this to verify your backend is working correctly.
#  Usage: python test_api.py
# ============================================================

import requests
import json
import sys

BASE_URL = "http://localhost:8000"

# ── Helper to print results nicely ────────────────────────────
def print_test(name, passed, response_data=None, error=None):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{status} — {name}")
    if response_data and passed:
        # Print a short preview of the response
        text = json.dumps(response_data, indent=2)
        lines = text.split("\n")
        preview = "\n".join(lines[:8])
        if len(lines) > 8:
            preview += f"\n  ... ({len(lines)-8} more lines)"
        print(f"  Response preview:\n  {preview.replace(chr(10), chr(10)+'  ')}")
    if error:
        print(f"  Error: {error}")

print("=" * 60)
print("  HEALIX API Test Suite")
print("  Make sure your server is running first!")
print("  Run: python main.py")
print("=" * 60)

tests_passed = 0
tests_failed = 0

# ── Test 1: Server is running ─────────────────────────────────
try:
    r = requests.get(f"{BASE_URL}/", timeout=5)
    if r.status_code == 200 and "HEALIX" in r.json().get("product", ""):
        print_test("Server is running", True, r.json())
        tests_passed += 1
    else:
        print_test("Server is running", False, error=f"Unexpected response: {r.text}")
        tests_failed += 1
except Exception as e:
    print_test("Server is running", False, error=f"Cannot connect. Is the server running?\n  Error: {e}")
    tests_failed += 1
    print("\n⛔ Cannot reach server. Please start it first with:\n   python main.py")
    sys.exit(1)

# ── Test 2: Health check ──────────────────────────────────────
try:
    r = requests.get(f"{BASE_URL}/health", timeout=5)
    passed = r.status_code == 200 and r.json().get("status") == "healthy"
    print_test("Health check endpoint", passed, r.json() if passed else None)
    tests_passed += 1 if passed else 0
    tests_failed += 0 if passed else 1
except Exception as e:
    print_test("Health check endpoint", False, error=str(e))
    tests_failed += 1

# ── Test 3: Get endpoints ─────────────────────────────────────
try:
    r = requests.get(f"{BASE_URL}/api/endpoints", timeout=5)
    data = r.json()
    passed = r.status_code == 200 and "endpoints" in data and len(data["endpoints"]) > 0
    print_test("Get endpoints (6 servers)", passed, data if passed else None)
    tests_passed += 1 if passed else 0
    tests_failed += 0 if passed else 1
except Exception as e:
    print_test("Get endpoints", False, error=str(e))
    tests_failed += 1

# ── Test 4: Get alerts ────────────────────────────────────────
try:
    r = requests.get(f"{BASE_URL}/api/alerts", timeout=5)
    data = r.json()
    passed = r.status_code == 200 and "alerts" in data
    print_test("Get alerts", passed, data if passed else None)
    tests_passed += 1 if passed else 0
    tests_failed += 0 if passed else 1
except Exception as e:
    print_test("Get alerts", False, error=str(e))
    tests_failed += 1

# ── Test 5: Get healing actions ───────────────────────────────
try:
    r = requests.get(f"{BASE_URL}/api/healing-actions", timeout=5)
    data = r.json()
    passed = r.status_code == 200 and "actions" in data
    print_test("Get healing actions", passed, data if passed else None)
    tests_passed += 1 if passed else 0
    tests_failed += 0 if passed else 1
except Exception as e:
    print_test("Get healing actions", False, error=str(e))
    tests_failed += 1

# ── Test 6: AI Agent — ask a question ────────────────────────
try:
    payload = {"question": "Why is EDGE-NODE-07 critical?"}
    r = requests.post(f"{BASE_URL}/api/agent/chat", json=payload, timeout=30)
    data = r.json()
    passed = r.status_code == 200 and "answer" in data and len(data["answer"]) > 20
    print_test("AI Agent chat (RAG + LLM)", passed, data if passed else None)
    tests_passed += 1 if passed else 0
    tests_failed += 0 if passed else 1
except Exception as e:
    print_test("AI Agent chat", False, error=str(e))
    tests_failed += 1

# ── Test 7: Trigger remediation ───────────────────────────────
try:
    payload = {"endpoint_id": "EP-005", "issue_type": "high_cpu"}
    r = requests.post(f"{BASE_URL}/api/healing/trigger", json=payload, timeout=15)
    data = r.json()
    passed = r.status_code == 200 and data.get("status") == "triggered"
    print_test("Trigger auto-remediation", passed, data if passed else None)
    tests_passed += 1 if passed else 0
    tests_failed += 0 if passed else 1
except Exception as e:
    print_test("Trigger remediation", False, error=str(e))
    tests_failed += 1

# ── Test 8: Predictions ───────────────────────────────────────
try:
    r = requests.get(f"{BASE_URL}/api/predictions", timeout=10)
    data = r.json()
    passed = r.status_code == 200 and "predictions" in data
    print_test("Failure predictions (ML)", passed, data if passed else None)
    tests_passed += 1 if passed else 0
    tests_failed += 0 if passed else 1
except Exception as e:
    print_test("Predictions", False, error=str(e))
    tests_failed += 1

# ── Test 9: Patch intelligence ────────────────────────────────
try:
    r = requests.get(f"{BASE_URL}/api/patches", timeout=10)
    data = r.json()
    passed = r.status_code == 200 and "patches" in data
    print_test("Patch intelligence", passed, data if passed else None)
    tests_passed += 1 if passed else 0
    tests_failed += 0 if passed else 1
except Exception as e:
    print_test("Patch intelligence", False, error=str(e))
    tests_failed += 1

# ── Summary ───────────────────────────────────────────────────
print("\n" + "=" * 60)
total = tests_passed + tests_failed
print(f"  Results: {tests_passed}/{total} tests passed")
if tests_failed == 0:
    print("  🎉 All tests passed! HEALIX backend is working perfectly.")
    print("\n  Next step: Open http://localhost:8000/docs")
    print("  to explore all API endpoints interactively.")
else:
    print(f"  ⚠️  {tests_failed} test(s) failed. Check the errors above.")
print("=" * 60)
