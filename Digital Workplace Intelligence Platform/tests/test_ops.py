"""Device notification box, remote access, demo purge, agent download."""
import pytest
from fastapi.testclient import TestClient

from server.main import create_app

HEALTHY = {"cpu_pct": 20, "mem_pct": 50, "disk_pct": 60, "uptime_hours": 10, "network_latency_ms": 40}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(str(tmp_path / "o.db"), enroll_token="tok", ai_enabled=False, it_tokens=""))


def enroll(c, name, demo=False, kind="laptop", platform="windows"):
    r = c.post("/api/enroll", json={"token": "tok", "hostname": name, "kind": kind, "platform": platform,
                                    "demo": demo}).json()
    return {"X-Device-Key": r["key"]}, r["device_id"]


def test_notification_box_shows_only_monitored_devices(client):
    h, _ = enroll(client, "real-1")
    h2, _ = enroll(client, "sim-1", demo=True)
    client.post("/api/telemetry", json={"metrics": {**HEALTHY, "disk_pct": 97}}, headers=h)
    client.post("/api/telemetry", json={"metrics": {**HEALTHY, "disk_pct": 97}}, headers=h2)
    n = client.get("/api/device-notifications").json()
    hosts = {i["hostname"] for i in n["items"]}
    assert hosts == {"real-1"} and n["monitored"] == 1
    last = n["items"][0]["id"]
    assert client.get("/api/device-notifications", params={"after": last}).json()["items"] == []


def test_purge_removes_only_synthetic_devices(client):
    h, real = enroll(client, "real-1")
    h2, sim = enroll(client, "sim-1", demo=True)
    for x in (h, h2):
        client.post("/api/telemetry", json={"metrics": {**HEALTHY, "cpu_pct": 97}}, headers=x)
    assert client.post("/api/admin/purge-demo").json() == {"removed_devices": 1}
    assert [d["id"] for d in client.get("/api/devices").json()] == [real]
    assert client.get(f"/api/devices/{sim}").status_code == 404
    assert client.post("/api/telemetry", json={"metrics": HEALTHY}, headers=h2).status_code == 401


def test_remote_options_rdp_file_and_assist(client):
    h, did = enroll(client, "lt-1")
    client.post("/api/telemetry", json={"metrics": {**HEALTHY, "ip_addresses": ["10.0.0.5"],
                                                    "azure": {"resourceId": "/subscriptions/s/resourceGroups/g/"
                                                              "providers/Microsoft.Compute/virtualMachines/vm1",
                                                              "osType": "Windows"}}}, headers=h)
    r = client.get(f"/api/devices/{did}/remote").json()
    assert {o["id"] for o in r["options"]} == {"rdp", "assist", "bastion"} and r["online"]
    rdp = client.get(f"/api/devices/{did}/remote.rdp")
    assert "full address:s:10.0.0.5" in rdp.text and rdp.headers["content-type"].startswith("application/x-rdp")
    assert client.post(f"/api/devices/{did}/remote/assist").json()["sent"]
    notes = client.get("/api/agent/commands", headers=h).json()["notifications"]
    assert any("Quick Assist" in n["message"] for n in notes)
    assert any(a["action"] == "remote.rdp" for a in client.get("/api/audit").json())
    _, ph = enroll(client, "ph-1", kind="mobile", platform="android")
    assert client.get(f"/api/devices/{ph}/remote").json()["options"] == []


def test_agent_download_and_roles(tmp_path):
    c = TestClient(create_app(str(tmp_path / "r.db"), enroll_token="tok", ai_enabled=False,
                              it_tokens="a:analyst,e:engineer"))
    assert c.get("/download/dwip-agent.exe").status_code in (200, 404)   # no IT token needed
    _, did = enroll(c, "lt-1")
    assert c.get(f"/api/devices/{did}/remote", headers={"X-DWIP-Token": "a"}).status_code == 403
    assert c.get(f"/api/devices/{did}/remote", headers={"X-DWIP-Token": "e"}).status_code == 200
    assert c.post("/api/admin/purge-demo", headers={"X-DWIP-Token": "e"}).status_code == 403
