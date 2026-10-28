import pytest
from fastapi.testclient import TestClient

from server import ai, analytics, brain
from server.main import create_app

HEALTHY = {"cpu_pct": 20, "mem_pct": 50, "disk_pct": 60, "crashes_24h": 0,
           "uptime_hours": 10, "network_latency_ms": 40}
TEAMS_OK = {"name": "Teams", "version": "24.1", "cpu_pct": 10, "mem_mb": 600, "crashes_24h": 0, "latency_ms": 300}


# ---------- brain ----------
def test_healthy_device_has_no_findings_and_high_score():
    assert brain.evaluate({"kind": "laptop", "platform": "windows"}, HEALTHY, [TEAMS_OK]) == []
    assert brain.score(HEALTHY, apps=[TEAMS_OK])["dex"] >= 90


def test_disk_full_on_laptop_gets_low_risk_cleanup():
    f = brain.evaluate({"kind": "laptop"}, {**HEALTHY, "disk_pct": 96})
    assert [(x["type"], x["action"], x["risk"]) for x in f] == [("disk_full", "clean_temp", "low")]


def test_disk_full_on_mobile_is_advice_only():
    f = brain.evaluate({"kind": "mobile", "platform": "android", "os_version": "14"},
                       {**HEALTHY, "disk_pct": 96})
    assert f[0]["action"] is None and f[0]["risk"] == "advise"


def test_reboot_needs_approval_and_outdated_mobile_os_flagged():
    f = brain.evaluate({"kind": "desktop"}, {**HEALTHY, "uptime_hours": 200})
    assert f[0]["risk"] == "high"
    f = brain.evaluate({"kind": "mobile", "platform": "ios", "os_version": "16.7"}, HEALTHY)
    assert f[0]["type"] == "os_outdated"


def test_app_os_and_vdi_findings():
    apps = [{**TEAMS_OK, "crashes_24h": 4}, {"name": "Outlook", "latency_ms": 2200}]
    types = {f["type"]: f for f in brain.evaluate({"kind": "laptop"}, {**HEALTHY, "patch_age_days": 45}, apps)}
    assert types["app_crash:Teams"]["action"] == "repair_app" and types["app_crash:Teams"]["target"] == "Teams"
    assert "app_slow:Outlook" in types
    assert types["os_patch_overdue"]["action"] == "install_updates"
    vdi = brain.evaluate({"kind": "vdi", "platform": "citrix"},
                         {**HEALTHY, "session_latency_ms": 260, "logon_seconds": 75})
    assert {f["type"] for f in vdi} == {"vdi_latency", "vdi_slow_logon"}


def test_problems_lower_the_score():
    bad = {**HEALTHY, "cpu_pct": 98, "disk_pct": 97, "crashes_24h": 5}
    assert brain.score(bad)["dex"] < brain.score(HEALTHY)["dex"] - 20
    assert brain.score(HEALTHY, sentiment=20)["dex"] < brain.score(HEALTHY, sentiment=100)["dex"]
    assert brain.score(HEALTHY, apps=[{**TEAMS_OK, "crashes_24h": 6}])["dex"] < brain.score(HEALTHY)["dex"]


def test_rule_based_assistant_answers_without_llm():
    ctx = {"summary": {"dex": 80, "devices": 3}, "apps": [{"app": "Teams", "score": 40, "crashes": 9,
                                                            "avg_latency_ms": 900, "devices": 3}]}
    assert "Teams" in ai.rule_it_answer("which apps are crashing?", ctx)
    assert "storage" in ai.rule_employee_answer("my disk is full", {"metrics": {"disk_pct": 97}})


# ---------- API ----------
@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(str(tmp_path / "t.db"), enroll_token="tok", ai_enabled=False))


def enroll(client, kind="laptop", name=None, **kw):
    r = client.post("/api/enroll", json={"token": "tok", "hostname": name or f"h-{kind}", "kind": kind,
                                         "platform": kw.get("platform", "windows"),
                                         "os_version": kw.get("os_version", "11"),
                                         "department": kw.get("department")})
    assert r.status_code == 200
    return {"X-Device-Key": r.json()["key"]}, r.json()["device_id"]


def send(client, h, metrics=None, apps=None):
    r = client.post("/api/telemetry", json={"metrics": metrics or HEALTHY, "apps": apps or []}, headers=h)
    assert r.status_code == 200
    return r.json()


def test_bad_token_and_bad_key_rejected(client):
    assert client.post("/api/enroll", json={"token": "x", "hostname": "h", "kind": "laptop",
                                            "platform": "w"}).status_code == 403
    assert client.post("/api/telemetry", json={"metrics": {}},
                       headers={"X-Device-Key": "nope"}).status_code == 401


def test_low_risk_issue_is_auto_fixed_and_user_notified(client):
    h, did = enroll(client)
    client.get("/api/agent/commands", headers=h)  # drain the welcome guide
    send(client, h, {**HEALTHY, "disk_pct": 96})
    cmds = client.get("/api/agent/commands", headers=h).json()
    assert [a["action"] for a in cmds["actions"]] == ["clean_temp"]
    assert client.get("/api/agent/commands", headers=h).json()["actions"] == []

    client.post(f"/api/agent/actions/{cmds['actions'][0]['id']}/result",
                json={"ok": True, "output": "freed"}, headers=h)
    kinds = {n["kind"] for n in client.get("/api/agent/commands", headers=h).json()["notifications"]}
    assert {"fix", "survey"} <= kinds

    send(client, h)
    detail = client.get(f"/api/devices/{did}").json()
    assert detail["issues"][0]["status"] == "resolved"
    assert detail["actions"][0]["status"] == "done"
    assert client.get("/api/summary").json()["fixed"] == 1


def test_high_risk_waits_for_approval(client):
    h, _ = enroll(client, "desktop")
    send(client, h, {**HEALTHY, "uptime_hours": 300})
    assert client.get("/api/agent/commands", headers=h).json()["actions"] == []
    appr = client.get("/api/approvals").json()
    assert len(appr) == 1 and appr[0]["action"] == "schedule_reboot"
    client.post(f"/api/actions/{appr[0]['id']}/approve")
    assert [a["action"] for a in client.get("/api/agent/commands", headers=h).json()["actions"]] \
        == ["schedule_reboot"]


def test_repeated_telemetry_does_not_duplicate_issues(client):
    h, did = enroll(client)
    for _ in range(3):
        send(client, h, {**HEALTHY, "cpu_pct": 97})
    assert len(client.get(f"/api/devices/{did}").json()["issues"]) == 1


def test_survey_feeds_sentiment_and_notification_cap(client):
    h, did = enroll(client, "mobile", platform="android", os_version="14")
    client.post("/api/agent/survey", json={"rating": 1}, headers=h)
    send(client, h)
    assert client.get(f"/api/devices/{did}").json()["scores"]["sentiment"] == 20
    sent = [client.post(f"/api/devices/{did}/survey").json()["sent"] for _ in range(7)]
    assert sent.count(True) == 5


def test_app_visibility_and_fleet_alert_from_shared_app_crash(client):
    crashing = [{**TEAMS_OK, "version": "24.3", "crashes_24h": 5}]
    for i in range(3):
        h, _ = enroll(client, name=f"pc{i}")
        send(client, h, apps=crashing)
    apps = client.get("/api/apps").json()
    assert apps[0]["app"] == "Teams" and apps[0]["devices"] == 3 and apps[0]["crashes"] == 15
    fleet = [a for a in client.get("/api/alerts").json() if a["scope"] == "fleet"]
    assert len(fleet) == 1 and fleet[0]["type"] == "app_crash:Teams"
    assert "24.3" in fleet[0]["insight"]
    detail = client.get("/api/apps/Teams").json()
    assert detail["versions"][0]["version"] == "24.3"
    assert len(client.get("/api/approvals").json()) == 3   # repair_app per device needs approval


def test_fleet_alert_clears_when_issues_resolve(client):
    keys = []
    for i in range(3):
        h, _ = enroll(client, name=f"pc{i}")
        keys.append(h)
        send(client, h, {**HEALTHY, "patch_age_days": 50})
    assert any(a["type"] == "os_patch_overdue" for a in client.get("/api/alerts").json())
    for h in keys[:2]:
        send(client, h)
    assert not any(a["type"] == "os_patch_overdue" for a in client.get("/api/alerts").json())


def test_predictions_detect_filling_disk(client):
    h, did = enroll(client)
    db_disk = 70.0
    for _ in range(10):
        db_disk += 1.5
        send(client, h, {**HEALTHY, "disk_pct": db_disk})
    preds = client.get("/api/predictions").json()
    assert any(p["type"] == "disk_forecast" and p["device_id"] == did for p in preds)
    assert analytics.eta(120) == "in ~2 min"


def test_noisy_disk_is_not_predicted(client):
    h, did = enroll(client)
    for v in [60, 63, 59, 64, 58, 62, 61, 60, 63, 59]:
        send(client, h, {**HEALTHY, "disk_pct": v})
    assert not any(p["device_id"] == did for p in client.get("/api/predictions").json())


def test_one_off_disk_jump_is_not_a_trend(client):
    h, did = enroll(client)
    for v in [70, 70.1, 69.9, 70, 70.1, 69.9, 70, 85, 85.1, 84.9, 85]:
        send(client, h, {**HEALTHY, "disk_pct": v})
    assert not any(p["device_id"] == did for p in client.get("/api/predictions").json())


def test_crash_trend_uses_per_device_gauge_and_needs_baseline():
    from server.db import DB
    db = DB(":memory:")
    now = 10_000.0
    rows = []
    for dev in ("a", "b", "c"):
        for t in range(0, 600, 30):              # 10 min of samples, 24h gauge = 1 before
            rows.append((dev, now - 900 + t, "Teams", 1))
        for t in range(0, 120, 30):              # last 2 min: gauge jumps to 5
            rows.append((dev, now - 110 + t, "Teams", 5))
    db.many("INSERT INTO app_samples(device_id,ts,app,crashes) VALUES(?,?,?,?)", rows)
    trends = analytics.app_crash_trends(db, now)
    assert len(trends) == 1 and "15 crashes" in trends[0]["detail"] and "was 3" in trends[0]["detail"]
    fresh = DB(":memory:")                        # no baseline window -> no trend
    fresh.many("INSERT INTO app_samples(device_id,ts,app,crashes) VALUES(?,?,?,?)",
               [(d, now - 10, "Teams", 9) for d in "abc"])
    assert analytics.app_crash_trends(fresh, now) == []


def test_guidance_auto_triggered_and_tracked(client):
    h, did = enroll(client, "mobile", platform="android", os_version="14")
    send(client, h, {**HEALTHY, "disk_pct": 97})
    delivered = client.get("/api/agent/guides", headers=h).json()["delivered"]
    titles = [g["title"] for g in delivered]
    assert "Free up phone storage" in titles and "Welcome to DWIP" in titles
    d = next(g for g in delivered if g["title"] == "Free up phone storage")
    assert client.post(f"/api/agent/guides/{d['delivery_id']}", json={"status": "completed"},
                       headers=h).status_code == 200
    g = next(x for x in client.get("/api/guides").json() if x["title"] == "Free up phone storage")
    assert g["completed"] == 1


def test_it_can_push_guides_and_create_their_own(client):
    _, did = enroll(client)
    gid = client.post("/api/guides", json={"title": "Use the new VPN", "steps": ["Open app", "Sign in"]}).json()["id"]
    assert client.post(f"/api/guides/{gid}/push", json={"device_id": did}).json()["sent"] == 1
    assert client.post(f"/api/guides/{gid}/push", json={"device_id": did}).json()["sent"] == 0  # once a day


def test_conversation_between_employee_ai_and_it(client):
    h, did = enroll(client)
    send(client, h, {**HEALTHY, "cpu_pct": 95})
    cid = client.post("/api/agent/conversations", json={"subject": "Laptop slow", "text": "Everything lags"},
                      headers=h).json()["id"]
    t = client.get(f"/api/conversations/{cid}").json()
    assert [m["sender"] for m in t["messages"]] == ["user", "ai"]
    assert client.get("/api/summary").json()["conversations"] == 1
    client.post(f"/api/conversations/{cid}/messages", json={"text": "Looking now"})
    notes = client.get("/api/agent/commands", headers=h).json()["notifications"]
    assert any(n["kind"] == "message" for n in notes)
    mine = client.get("/api/agent/conversations", headers=h).json()
    assert mine[0]["messages"][-1]["sender"] == "it"
    client.post(f"/api/conversations/{cid}/close")
    assert client.get("/api/summary").json()["conversations"] == 0


def test_pulse_campaign_and_engagement(client):
    h1, _ = enroll(client, name="a", department="Finance")
    h2, _ = enroll(client, "mobile", name="b", platform="ios", os_version="17.4", department="Sales")
    camp = client.post("/api/campaigns", json={"question": "How easy is it to join meetings?"}).json()
    assert camp["sent"] == 2
    client.post("/api/agent/survey", json={"rating": 5, "campaign_id": camp["id"], "comment": "great"}, headers=h1)
    client.post("/api/agent/survey", json={"rating": 2, "campaign_id": camp["id"]}, headers=h2)
    c = client.get("/api/campaigns").json()[0]
    assert c["responses"] == 2 and c["response_rate"] == 100 and c["rating"] == 3.5
    e = client.get("/api/engagement").json()
    assert {d["department"] for d in e["departments"]} == {"Finance", "Sales"}
    assert e["score"] == 0 and e["comments"][0]["comment"] == "great"


def test_assistants_fall_back_to_rules(client):
    h, _ = enroll(client)
    send(client, h, {**HEALTHY, "disk_pct": 93})
    r = client.post("/api/assistant/chat", json={"question": "what alerts are open?"}).json()
    assert r["source"] == "rules" and r["answer"]
    r = client.post("/api/agent/assistant", json={"question": "my disk is full"}, headers=h).json()
    assert "storage" in r["answer"]


def test_dashboard_pages_served(client):
    assert "DWIP" in client.get("/").text
    assert "Companion" in client.get("/companion").text
