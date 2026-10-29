"""Configurable alert thresholds and the controlled script library."""
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from agent.agent import Agent
from server import brain
from server.main import create_app

HEALTHY = {"cpu_pct": 20, "mem_pct": 50, "disk_pct": 60, "uptime_hours": 10, "network_latency_ms": 40}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(str(tmp_path / "t.db"), enroll_token="tok", ai_enabled=False, it_tokens=""))


def enroll(c, name="lt-1", kind="laptop", platform="windows"):
    r = c.post("/api/enroll", json={"token": "tok", "hostname": name, "kind": kind, "platform": platform}).json()
    return {"X-Device-Key": r["key"]}, r["device_id"]


def types(c, did):
    return {i["type"]: i for i in c.get(f"/api/devices/{did}").json()["issues"] if i["status"] == "open"}


# ---------- thresholds ----------
def test_level_handles_above_below_and_critical():
    th = brain.DEVICE_THRESHOLDS
    assert brain.level(th, "disk_pct", 92) == "warn" and brain.level(th, "disk_pct", 96) == "crit"
    assert brain.level(th, "battery_pct", 10) == "warn" and brain.level(th, "battery_pct", 50) is None
    assert brain.level(th, "cpu_pct", None) is None


def test_global_and_kind_thresholds_change_alerting(client):
    h, did = enroll(client)
    client.post("/api/telemetry", json={"metrics": {**HEALTHY, "cpu_pct": 80}}, headers=h)
    assert "high_cpu" not in types(client, did)
    assert client.post("/api/thresholds", json={"scope": "device", "params": {"cpu_pct": {"warn": 75, "crit": 85}}}).json()["ok"]
    client.post("/api/telemetry", json={"metrics": {**HEALTHY, "cpu_pct": 80}}, headers=h)
    assert types(client, did)["high_cpu"]["severity"] == "medium"
    client.post("/api/thresholds", json={"scope": "kind:laptop", "params": {"cpu_pct": {"warn": 95}}})
    client.post("/api/telemetry", json={"metrics": {**HEALTHY, "cpu_pct": 80}}, headers=h)
    assert "high_cpu" not in types(client, did)                      # laptop override wins, issue resolves
    meter = client.get("/api/thresholds", params={"scope": "kind:laptop"}).json()
    cpu = next(p for p in meter["params"] if p["param"] == "cpu_pct")
    assert cpu["warn"] == 95 and cpu["crit"] == 85             # laptop warn, inherited global critical
    assert cpu["current_max"] == 80 and cpu["breaching_warn"] == 0
    assert client.post("/api/thresholds", json={"scope": "device",
                                                "params": {"cpu_pct": {"warn": 90, "crit": 50}}}).status_code == 400
    assert any(a["action"] == "thresholds.update" for a in client.get("/api/audit").json())


def test_app_thresholds_per_application(client):
    h, did = enroll(client)
    apps = [{"name": "Teams", "version": "1", "latency_ms": 1200}, {"name": "Outlook", "version": "1", "latency_ms": 1200}]
    client.post("/api/thresholds", json={"scope": "app:Teams", "params": {"latency_ms": {"warn": 1000}}})
    client.post("/api/telemetry", json={"metrics": HEALTHY, "apps": apps}, headers=h)
    t = types(client, did)
    assert "app_slow:Teams" in t and "app_slow:Outlook" not in t


def test_sustained_threshold_waits_for_history(client):
    h, did = enroll(client)
    client.post("/api/thresholds", json={"scope": "device", "params": {"cpu_pct": {"sustain_min": 5}}})
    client.post("/api/telemetry", json={"metrics": {**HEALTHY, "cpu_pct": 97}}, headers=h)
    assert "high_cpu" not in types(client, did)     # one spike, no 5-minute history yet


# ---------- scripts ----------
def test_script_lifecycle_approval_versions_and_run(client):
    h, did = enroll(client)
    _, ph = enroll(client, "ph-1", "mobile", "android")
    sid = client.post("/api/scripts", json={"name": "Hello", "language": "powershell", "body": "'hi'"}).json()["id"]
    assert client.post(f"/api/scripts/{sid}/run", json={"device_ids": [did]}).status_code == 400   # draft
    assert client.post(f"/api/scripts/{sid}/review/approve").json()["status"] == "approved"
    r = client.post(f"/api/scripts/{sid}/run", json={"device_ids": [did, ph], "dry_run": True}).json()["results"]
    assert {x["status"] for x in r} == {"dry_run", "skipped"}
    assert client.get("/api/agent/commands", headers=h).json()["scripts"] == []
    client.post(f"/api/scripts/{sid}/run", json={"device_ids": [did], "dry_run": False})
    sent = client.get("/api/agent/commands", headers=h).json()["scripts"]
    assert len(sent) == 1 and sent[0]["sha256"] == hashlib.sha256(b"'hi'").hexdigest()
    client.post(f"/api/agent/scripts/{sent[0]['id']}/result", json={"status": "done", "exit_code": 0, "output": "hi"},
                headers=h)
    assert client.get(f"/api/scripts/{sid}/runs").json()[0]["output"] == "hi"
    edited = client.put(f"/api/scripts/{sid}", json={"name": "Hello", "language": "powershell", "body": "'bye'"}).json()
    assert edited["version"] == 2 and edited["status"] == "draft"                # edit = new version, unapproved


def test_high_risk_script_needs_per_run_approval_and_separate_people(tmp_path):
    c = TestClient(create_app(str(tmp_path / "s.db"), enroll_token="tok", ai_enabled=False,
                              it_tokens="e1:engineer:Eve,e2:engineer:Sam,v:viewer"))
    E1, E2, V = ({"X-DWIP-Token": t} for t in ("e1", "e2", "v"))
    h, did = enroll(c)
    sid = c.post("/api/scripts", json={"name": "Reset", "language": "batch", "risk": "high", "body": "echo x"},
                 headers=E1).json()["id"]
    assert c.post(f"/api/scripts/{sid}/review/approve", headers=E1).status_code == 403   # author can't approve
    assert c.post(f"/api/scripts/{sid}/review/approve", headers=V).status_code == 403    # viewer can't
    assert c.post(f"/api/scripts/{sid}/review/approve", headers=E2).status_code == 200
    r = c.post(f"/api/scripts/{sid}/run", json={"device_ids": [did], "dry_run": False}, headers=E1).json()["results"]
    assert r[0]["status"] == "pending_approval"
    assert c.get("/api/agent/commands", headers=h).json()["scripts"] == []
    rid = r[0]["run_id"]
    assert c.post(f"/api/script-runs/{rid}/approve", headers=E1).status_code == 403
    assert c.post(f"/api/script-runs/{rid}/approve", headers=E2).json()["status"] == "queued"
    assert len(c.get("/api/agent/commands", headers=h).json()["scripts"]) == 1


def test_agent_refuses_when_disabled_or_tampered(tmp_path, monkeypatch):
    monkeypatch.setattr(Agent, "_azure", staticmethod(lambda: None))
    a = Agent("http://x", "t", 15, False, None)
    sc = {"language": "python", "body": "print(1)", "sha256": hashlib.sha256(b"print(1)").hexdigest(), "timeout": 30}
    assert a.run_script(sc)[0] == "refused"                       # --allow-scripts not set
    a.allow_scripts = True
    assert a.run_script({**sc, "body": "print(2)"})[0] == "refused"   # body changed after approval
    status, code, out = a.run_script(sc)
    assert status == "done" and code == 0 and out.strip() == "1"


def test_flow_can_run_approved_script(client):
    h, did = enroll(client)
    sid = client.post("/api/scripts", json={"name": "Flush", "language": "batch", "body": "ipconfig /flushdns"}).json()["id"]
    client.post(f"/api/scripts/{sid}/review/approve")
    g = {"nodes": [{"id": "s", "type": "start"}, {"id": "x", "type": "script", "config": {"script_id": sid}}],
         "edges": [{"from": "s", "port": "out", "to": "x"}]}
    fid = client.post("/api/flows", json={"name": "f", "graph": g}).json()["id"]
    r = client.post(f"/api/flows/{fid}/run", json={"device_id": did, "dry_run": False}).json()
    assert r["status"] == "completed" and "queued" in r["steps"][1]["result"]
    assert len(client.get("/api/agent/commands", headers=h).json()["scripts"]) == 1
