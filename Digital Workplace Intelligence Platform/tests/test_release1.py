"""Release 1: experience intelligence foundation."""
import pytest
from fastapi.testclient import TestClient

from server import impact
from server.main import create_app

HEALTHY = {"cpu_pct": 20, "mem_pct": 50, "disk_pct": 60, "crashes_24h": 0,
           "uptime_hours": 10, "network_latency_ms": 40}
TEAMS_OK = {"name": "Teams", "version": "24.1", "cpu_pct": 10, "mem_mb": 600, "crashes_24h": 0, "latency_ms": 300}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(str(tmp_path / "t.db"), enroll_token="tok", ai_enabled=False, it_tokens=""))


def enroll(client, name, kind="laptop", location=None, department=None, demo=False, user=None):
    r = client.post("/api/enroll", json={"token": "tok", "hostname": name, "kind": kind, "platform": "windows",
                                         "os_version": "11", "location": location, "department": department,
                                         "demo": demo, "user": user or name})
    assert r.status_code == 200
    return {"X-Device-Key": r.json()["key"]}, r.json()["device_id"]


def send(client, h, metrics=None, apps=None):
    r = client.post("/api/telemetry", json={"metrics": metrics or HEALTHY, "apps": apps or []}, headers=h)
    assert r.status_code == 200


def test_impact_score_is_explainable_and_configurable():
    cfg = impact.DEFAULTS
    inc = {"employees": 5, "severity": "high", "critical": True, "minutes_open": 60, "recurrences": 5,
           "spreading": True}
    s, br = impact.score(inc, 5, cfg)
    assert s == 100 and round(sum(b["points"] for b in br)) == 100
    s2, _ = impact.score({**inc, "employees": 1, "critical": False, "spreading": False}, 10, cfg)
    assert s2 < s
    custom = {**cfg, "weights": {**cfg["weights"], "critical_app": 0}}
    assert [b["points"] for b in impact.score(inc, 5, custom)[1] if b["factor"] == "critical_app"] == [0]


def test_incidents_group_issues_with_evidence_and_correlation(client):
    for i in range(3):
        h, _ = enroll(client, f"lt-{i}", location="Bangalore")
        send(client, h, {**HEALTHY, "mem_pct": 96}, [{**TEAMS_OK, "mem_mb": 3000}])
    h, _ = enroll(client, "lt-x", location="London")
    send(client, h)
    incs = client.get("/api/incidents").json()
    mem = next(i for i in incs if i["id"] == "high_memory")
    assert mem["devices"] == 3 and mem["employees"] == 3 and mem["total_employees"] == 4
    assert 0 < mem["impact"] <= 100 and {b["factor"] for b in mem["breakdown"]} >= {"reach", "severity"}
    assert mem["facts"] and mem["status"].startswith("Investigating")
    assert any(c["type"] == "app_memory:Teams" for c in mem["correlated"])
    assert mem["locations"] == {"Bangalore": 3}
    d = client.get("/api/incidents/app_memory:Teams").json()
    assert d["versions"] == {"24.1": 3} and len(d["device_list"]) == 3
    assert client.get("/api/incidents", params={"location": "London"}).json() == []


def test_dex_dashboard_filters_live_vs_demo(client):
    h, _ = enroll(client, "real-1", location="Bangalore")
    send(client, h)
    h2, _ = enroll(client, "sim-1", location="London", demo=True)
    send(client, h2, {**HEALTHY, "disk_pct": 97})
    all_ = client.get("/api/dex").json()
    assert all_["devices"] == 2 and all_["demo_devices"] == 1 and all_["impacted_employees"] == 1
    live = client.get("/api/dex", params={"data": "live"}).json()
    assert live["devices"] == 1 and live["demo_devices"] == 0 and live["top_problems"] == []
    assert {c["location"] for c in all_["heatmap"]} == {"Bangalore", "London"}
    assert all_["trend"] and all_["trend"][0]["dex"] is not None
    assert client.get("/api/dex", params={"period": "7d"}).json()["trend"]   # hourly rollups
    devs = client.get("/api/devices", params={"data": "demo"}).json()
    assert [d["hostname"] for d in devs] == ["sim-1"] and devs[0]["demo"] is True


def test_coverage_reports_missing_sources_instead_of_values(client):
    h, _ = enroll(client, "real-1")
    send(client, h, {**HEALTHY, "patch_age_days": 3}, [TEAMS_OK])
    cov = {c["signal"]: c for c in client.get("/api/monitoring/coverage").json()}
    assert cov["CPU, memory and disk"]["status"] == "live"
    assert cov["Compliance and BitLocker"]["status"] == "not_collected" and cov["Compliance and BitLocker"]["requires"]
    assert cov["Teams responsiveness, crashes, resources"]["real_devices"] == 1
    cons = {c["id"]: c for c in client.get("/api/connectors").json()}
    assert cons["dwip-agent"]["status"] == "connected" and cons["dwip-agent"]["volume_1h"] == 1
    assert cons["intune"]["status"] == "not_configured" and cons["intune"]["last_sync"] is None
    assert cons["dwip-simulator"]["status"] == "no_data"
    assert client.post("/api/connectors/intune/test").json()["ok"] is False


def test_benchmarks_compare_against_internal_baseline(client):
    for i, loc in enumerate(["Bangalore", "Bangalore", "London", "London"]):
        h, _ = enroll(client, f"d{i}", location=loc)
        bad = loc == "Bangalore"
        send(client, h, {**HEALTHY, "disk_pct": 97 if bad else 50, "cpu_pct": 95 if bad else 20})
    b = client.get("/api/benchmarks", params={"dimension": "location"}).json()
    rows = {r["group"]: r for r in b["rows"]}
    assert rows["Bangalore"]["delta_vs_enterprise"] < 0 < rows["London"]["delta_vs_enterprise"]
    assert b["history_note"]   # no 7-day history yet: says so instead of inventing it
    ins = client.get("/api/benchmarks/insights").json()
    assert any("Bangalore" in i["text"] and "below the enterprise baseline" in i["text"] for i in ins)
    assert client.get("/api/benchmarks", params={"dimension": "bogus"}).status_code == 400


def test_assist_separates_facts_and_gaps_without_llm(client):
    h, _ = enroll(client, "lt-1", location="Bangalore")
    send(client, h, {**HEALTHY, "cpu_pct": 97})
    h2, _ = enroll(client, "lt-2", location="London")
    send(client, h2, {**HEALTHY, "cpu_pct": 99})
    r = client.post("/api/assist", json={"question": "Identify endpoints with high CPU in Bangalore and "
                                                     "correlate with recent software updates"}).json()
    assert "location: Bangalore" in r["scope"]
    text = " ".join(f["text"] for f in r["facts"])
    assert "lt-1" in text and "lt-2" not in text and all(f["kind"] == "fact" for f in r["facts"])
    assert any("configuration-change history" in g for g in r["gaps"])
    assert r["source"] == "rules" and r["confidence"] != "high"
    assert r["actions"][0]["mode"] == "Policy-controlled automation"
    r = client.post("/api/assist", json={"question": "Recommend the safest remediation for BitLocker failures"}).json()
    assert any("BitLocker" in g for g in r["gaps"]) and r["confidence"] != "high"
    assert any(a["action"] == "assist.query" for a in client.get("/api/audit").json())
    assert client.get("/api/reports/ai").json()["resolved_without_llm_pct"] == 100


def test_patch_policy_breach_is_forecast(client):
    h, _ = enroll(client, "lt-1")
    for _ in range(9):
        send(client, h, {**HEALTHY, "patch_age_days": 25})
    p = [x for x in client.get("/api/predictions").json() if x["type"] == "patch_forecast"]
    assert p and p[0]["eta"] == "in ~5 days" and p[0]["model"] == "deterministic threshold"


def test_remediation_view_verifies_outcome(client):
    h, _ = enroll(client, "lt-1")
    client.get("/api/agent/commands", headers=h)
    send(client, h, {**HEALTHY, "disk_pct": 96})
    act = client.get("/api/agent/commands", headers=h).json()["actions"][0]
    client.post(f"/api/agent/actions/{act['id']}/result", json={"ok": True}, headers=h)
    r = client.get("/api/remediation").json()
    assert r["recent"][0]["verification"].startswith("pending verification")
    send(client, h)
    r = client.get("/api/remediation").json()
    assert r["recent"][0]["verification"] == "verified: issue cleared" and r["stats"]["success_rate"] == 100
    assert r["policy"]["llm_can_execute"] is False
    assert any(a["action"] == "remediation.auto" for a in client.get("/api/audit").json())


def test_rbac_roles_masking_and_audit(tmp_path):
    c = TestClient(create_app(str(tmp_path / "r.db"), enroll_token="tok", ai_enabled=False,
                              it_tokens="v1:viewer,e1:engineer:Eve,a1:admin"))
    h, _ = enroll(c, "lt-1", kind="desktop", user="Asha")        # device paths need no IT token
    send(c, h, {**HEALTHY, "uptime_hours": 200})
    assert c.get("/api/summary").status_code == 401
    V, E, A = ({"X-DWIP-Token": t} for t in ("v1", "e1", "a1"))
    assert c.get("/api/devices", headers=V).json()[0]["user"] == "A•••"
    assert c.get("/api/devices", headers=E).json()[0]["user"] == "Asha"
    assert c.post("/api/assist", json={"question": "what needs attention?"}, headers=V).status_code == 200
    act = c.get("/api/approvals", headers=V).json()[0]
    assert c.post(f"/api/actions/{act['id']}/approve", headers=V).status_code == 403
    assert c.post("/api/impact/config", json={"weights": {"reach": 50}}, headers=E).status_code == 403
    assert c.post(f"/api/actions/{act['id']}/approve", headers=E).status_code == 200
    assert c.post("/api/impact/config", json={"weights": {"reach": 50}}, headers=A).json()["weights"]["reach"] == 50
    assert c.get("/api/audit", headers=V).status_code == 403
    log = c.get("/api/audit", headers=E).json()
    assert any(a["actor"] == "Eve" and "approve" in a["action"] and a["status"] == "ok" for a in log)
    assert any(a["status"] == "denied" for a in log)
    assert c.get("/api/me", headers=V).json()["role"] == "viewer"
    with pytest.raises(Exception):
        with c.websocket_connect("/ws"):
            pass
