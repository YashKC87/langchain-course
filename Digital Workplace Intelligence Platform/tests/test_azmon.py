"""Agentless Azure Monitor telemetry: metric mapping, Azure VM rules, subscription config."""
from fastapi.testclient import TestClient

from server import azmon, brain
from server.main import create_app

VM = {"id": "/subscriptions/s1/resourceGroups/RG-1/providers/Microsoft.Compute/virtualMachines/vm1", "name": "vm1",
      "location": "centralindia", "properties": {"vmId": "ABC", "hardwareProfile": {"vmSize": "Standard_B2as_v2"},
                                                 "storageProfile": {"osDisk": {"osType": "Windows"}}}}
RAW = {"Percentage CPU": {"average": 12.34, "timeStamp": "t"}, "Available Memory Percentage": {"average": 60.0},
       "OS Disk IOPS Consumed Percentage": {"average": 95.0}, "Network In Total": {"average": 1, "total": 2_500_000},
       "VmAvailabilityMetric": {"average": 1.0}, "CPU Credits Remaining": {"average": 3.0}}


def test_platform_metrics_map_to_dwip_metrics():
    m = azmon.to_metrics(RAW, VM, "VM running", "s1", ["10.0.0.4"])
    assert m["cpu_pct"] == 12.3 and m["mem_pct"] == 40.0 and m["network_in_mb_5m"] == 2.5
    assert m["azure"]["resourceGroupName"] == "RG-1" and m["source"] == "azure-monitor"
    types = {f["type"]: f for f in brain.evaluate({"kind": "vdi", "platform": "windows"}, m)}
    assert types["disk_iops_saturated"]["severity"] == "medium"
    assert types["cpu_credits_low"]["severity"] == "high"          # 3 credits is past critical (5)
    assert "vm_unavailable" not in types
    down = brain.evaluate({"kind": "vdi"}, {**m, "vm_availability": 0})
    assert any(f["type"] == "vm_unavailable" for f in down)


def test_subscription_config_validated_and_audited(tmp_path):
    c = TestClient(create_app(str(tmp_path / "a.db"), enroll_token="tok", ai_enabled=False, it_tokens=""))
    assert c.post("/api/azure/monitor", json={"subscription_id": "not-a-guid"}).status_code == 400
    r = c.post("/api/azure/monitor", json={"subscription_id": "5C761EB4-81A0-4103-83CE-76F068E05227", "interval_s": 10})
    assert r.json() == {"subscription_id": "5c761eb4-81a0-4103-83ce-76f068e05227", "enabled": True, "interval_s": 60}
    assert c.get("/api/azure/monitor").json()["subscription_id"].startswith("5c761eb4")
    assert any(a["action"] == "azure.monitor.configure" for a in c.get("/api/audit").json())
    con = {x["id"]: x for x in c.get("/api/connectors").json()}["azure-vms"]
    assert con["status"] == "configured" and "5c761eb4" in con["note"]
