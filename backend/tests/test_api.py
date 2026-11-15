"""API + service integration tests against the seeded database (no LLM calls)."""
import pytest
from fastapi.testclient import TestClient

from app.db import session_scope
from app.services import actions, analytics, finance, growth, inventory, khata, trust

pytestmark = pytest.mark.integration


def test_health_and_ready(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}


def test_auth_required_and_error_shape(client: TestClient) -> None:
    r = client.get("/api/dashboard")
    assert r.status_code == 401
    err = r.json()["error"]
    assert err["code"] == "unauthorized" and err["request_id"] != "-"
    assert client.get("/api/dashboard", headers={"authorization": "Bearer junk"}).status_code == 401


def test_dashboard_numbers(client: TestClient, auth1: dict[str, str]) -> None:
    d = client.get("/api/dashboard", headers=auth1).json()
    assert d["yesterday"]["txns"] > 200
    assert d["khata"]["overdue_count"] == 3
    assert d["stock_at_risk"] >= 1
    assert d["lapsed"] > 30


def test_service_expectations() -> None:
    with session_scope() as s:
        risk = {r["name"]: r["days_of_cover"] for r in inventory.at_risk(s, 1)}
        assert risk["Amul Doodh 500ml"] <= 3
        assert len(khata.overdue(s, 1)) == 3
        assert len(growth.lapsed_customers(s, 1)) > 30
        kinds = {a["type"] for a in trust.detect(s, 1)}
        assert {"unusual_amount", "rapid_repeat"} <= kinds
        assert finance.loan_eligibility(s, 1)["eligible"] is True
        assert analytics.top_products(s, 1)[0]["product"] == "Amul Doodh 500ml"


def test_tenant_isolation(client: TestClient, auth1: dict[str, str], auth2: dict[str, str], clean_state: None) -> None:
    client.get("/api/briefing/today", headers=auth1)
    a = client.get("/api/actions", headers=auth1).json()
    assert a, "merchant 1 should have pending actions"
    assert client.get("/api/actions", headers=auth2).json() == []
    assert client.post(f"/api/actions/{a[0]['id']}/approve", headers=auth2).status_code == 404
    assert client.get("/api/khata", headers=auth2).json()["summary"]["open_count"] == 0


def test_action_approval_is_idempotent_and_pay_flow(client: TestClient, auth1: dict[str, str], clean_state: None) -> None:
    client.get("/api/briefing/today", headers=auth1)
    acts = client.get("/api/actions", headers=auth1).json()
    khata_action = next(a for a in acts if a["kind"] == "khata_reminders")
    first = client.post(f"/api/actions/{khata_action['id']}/approve", headers=auth1).json()
    second = client.post(f"/api/actions/{khata_action['id']}/approve", headers=auth1).json()  # double click
    assert first["status"] == second["status"] == "executed"
    assert first["result"] == second["result"]

    threads = client.get("/api/messages", headers=auth1).json()
    assert sum(len(t["messages"]) for t in threads) == 3  # not 6: no duplicate sends

    link_id = first["result"]["sent"][0]["link_id"]
    amount = first["result"]["sent"][0]["amount_paise"]
    assert client.post(f"/api/pay/{link_id}").json()["status"] == "paid"
    assert client.post(f"/api/pay/{link_id}").json()["status"] == "paid"  # double pay is a no-op
    out = client.get("/api/outcomes", headers=auth1).json()
    assert out["recovered_paise"] == amount and out["recovered_count"] == 1
    assert client.get("/api/khata", headers=auth1).json()["summary"]["overdue_count"] == 2


def test_rejected_action_cannot_be_approved(client: TestClient, auth1: dict[str, str], clean_state: None) -> None:
    client.get("/api/briefing/today", headers=auth1)
    a = client.get("/api/actions", headers=auth1).json()[0]
    assert client.post(f"/api/actions/{a['id']}/reject", headers=auth1).json()["status"] == "rejected"
    r = client.post(f"/api/actions/{a['id']}/approve", headers=auth1)
    assert r.status_code == 409 and r.json()["error"]["code"] == "conflict"


def test_campaign_redemption_updates_roi(client: TestClient, auth1: dict[str, str], clean_state: None) -> None:
    with session_scope() as s:
        act = actions.propose_winback(s, 1)
        assert act is not None
        aid = act.id
    done = client.post(f"/api/actions/{aid}/approve", headers=auth1).json()
    cid = done["result"]["campaign_id"]
    assert client.post(f"/api/growth/campaigns/{cid}/simulate-redemptions", headers=auth1).json()["redeemed"] == 9
    assert client.get("/api/outcomes", headers=auth1).json()["customers_won_back"] == 9


def test_khata_entry_validation(client: TestClient, auth1: dict[str, str]) -> None:
    bad = client.post("/api/khata/entries", headers=auth1, json={"customer_name": "X", "phone": "123", "amount_rupees": 10})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_error"


def test_voice_upload_validation(client: TestClient, auth1: dict[str, str]) -> None:
    r = client.post("/api/voice/transcribe", headers=auth1, files={"audio": ("a.txt", b"x" * 2000, "text/plain")})
    assert r.status_code == 400 and "Unsupported" in r.json()["error"]["message"]
    r = client.post("/api/voice/transcribe", headers=auth1, files={"audio": ("a.webm", b"x", "audio/webm")})
    assert r.status_code == 400
