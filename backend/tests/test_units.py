"""Pure unit tests: no network, no database."""
import pytest

from app.agents.graph import _keyword_route, _result_line, _scan_action_ids
from app.agents.tools import _rupees
from app.core import fmt_inr, mask_pii
from app.services import briefing, growth, inventory, khata, sql_guard, voice_intent


def test_mask_pii_hides_phone_numbers() -> None:
    assert "9822000001" not in mask_pii("call Ramesh on 9822000001 now")
    assert mask_pii("call +91 9822000001").endswith("XXXXXX0001")
    assert mask_pii("amount 1200 rupees") == "amount 1200 rupees"


def test_fmt_inr() -> None:
    assert fmt_inr(120000) == "₹1,200"


@pytest.mark.parametrize("sql", [
    "SELECT category, SUM(amount_rupees) FROM v_sale_items GROUP BY 1",
    "WITH t AS (SELECT * FROM v_sales) SELECT COUNT(*) FROM t",
])
def test_sql_guard_allows_safe_selects(sql: str) -> None:
    assert sql_guard.validate(sql).upper().startswith(("SELECT", "WITH"))


@pytest.mark.parametrize("sql", [
    "DELETE FROM sales",
    "DROP TABLE sales",
    "SELECT * FROM merchants",
    "SELECT * FROM v_sales; DROP TABLE sales",
    "UPDATE products SET stock_qty = 0",
    "SELECT pg_read_file('/etc/passwd')",
    "SELECT * FROM sales",
])
def test_sql_guard_blocks_unsafe_sql(sql: str) -> None:
    with pytest.raises(sql_guard.UnsafeSQLError):
        sql_guard.validate(sql)


def test_reminder_text_is_localised_and_has_link() -> None:
    t = khata.reminder_text("hi", "Ramesh Kulkarni", "Sharma General Store", 120000, 15, "http://x/pay/abc")
    assert "Ramesh" in t and "₹1,200" in t and "http://x/pay/abc" in t and "15" in t
    assert "Hello" in khata.reminder_text("en", "Ramesh K", "Shop", 5000, 3, "l")


def test_offer_text_mentions_cashback() -> None:
    assert "20" in growth.offer_text("en", "Shop", 2000, "Diwali")


def test_rupees_conversion_is_recursive() -> None:
    out = _rupees({"a_paise": 12345, "b": [{"c_paise": 100}]})
    assert out == {"a_rs": 123.45, "b": [{"c_rs": 1.0}]}


def test_scan_action_ids() -> None:
    assert _scan_action_ids('{"action_id": 4}') == [4]
    assert _scan_action_ids('[{"action_id": 1}, {"action_id": 2}, {"x": 1}]') == [1, 2]
    assert _scan_action_ids("not json") == []


@pytest.mark.parametrize("q,expected", [
    ("udhaar reminder bhejo", "khata"), ("doodh khatam ho raha hai stock", "inventory"),
    ("Diwali pe kya offer chalaun", "growth"), ("loan milega?", "finance"),
    ("suspicious payment", "trust"), ("kal ki sale", "insights"),
])
def test_keyword_router_fallback(q: str, expected: str) -> None:
    assert _keyword_route(q) == expected


@pytest.mark.parametrize("text,expected", [
    ("haan kar do", True), ("Yes", True), ("हाँ", True), ("nahi", False), ("mat bhejo", False), ("नहीं", False),
])
def test_voice_yes_no_keywords(text: str, expected: bool) -> None:
    assert voice_intent.classify(text) is expected


def test_result_line_language() -> None:
    e = {"status": "executed", "title": "t", "result": {"kind": "reorder", "distributor": "Gupta"}}
    assert "Order sent to Gupta" in _result_line(e, "en")
    assert "Gupta" in _result_line(e, "hi")
    assert "cancelled" in _result_line({"status": "rejected", "title": "X"}, "en")


FACTS = {"sales_paise": 2147300, "pct_vs_last_week": 8.9, "overdue_count": 3, "lapsed_count": 41}


def test_briefing_validation_accepts_correct_script() -> None:
    assert briefing.validate_script("Kal 21473 rupaye ki sale, 8.9 percent zyada (more) than last week. 3 logon ka udhaar, 41 purane grahak.", FACTS)


def test_briefing_validation_rejects_wrong_direction_or_number() -> None:
    assert not briefing.validate_script("Kal 21473 rupaye ki sale, 8.9 percent kam. 3 udhaar, 41 grahak.", FACTS)
    assert not briefing.validate_script("Kal 21000 rupaye ki sale, 8.9 percent more. 3 udhaar, 41 grahak.", FACTS)
    assert not briefing.validate_script("इक्कीस हजार रुपये की बिक्री", FACTS)


def test_keyword_match_has_no_default() -> None:
    from app.agents.graph import _keyword_match

    assert _keyword_match("Doodh kab tak chalega? Order kar do") == "inventory"
    assert _keyword_match("namaste") is None


# ---------------- expiry / clearance ----------------
@pytest.mark.parametrize("days,price,cost,expected", [
    (1, 3000, 2000, 30),    # 2 days or less -> 30%, margin 33% allows it
    (2, 3000, 2000, 30),
    (4, 3000, 2000, 20),
    (6, 3000, 2000, 10),
    (4, 3000, 2800, 6),     # thin margin caps the discount (price stays >= cost)
    (4, 3000, 2900, 0),     # margin 3% < 5% -> not worth a markdown
    (-1, 3000, 2000, 0),    # already expired
])
def test_clearance_discount_never_below_cost(days: int, price: int, cost: int, expected: int) -> None:
    pct = inventory.clearance_discount_pct(days, price, cost)
    assert pct == expected
    assert price * (100 - pct) // 100 >= cost or pct == 0


@pytest.mark.parametrize("days,label", [(-1, "expired"), (0, "critical"), (3, "critical"), (5, "soon"), (7, "soon"), (12, "watch")])
def test_expiry_severity(days: int, label: str) -> None:
    assert inventory.expiry_severity(days) == label


def test_units_at_risk() -> None:
    assert inventory.units_at_risk(40, 5.0, 4) == 20      # sells 20 before expiry, 20 left
    assert inventory.units_at_risk(10, 5.0, 4) == 0       # sells out in time
    assert inventory.units_at_risk(10, 5.0, -1) == 10     # expired: everything is at risk


def test_clearance_text_uses_service_numbers() -> None:
    t = growth.clearance_text("en", "Sharma Store", [{"name": "Amul Dahi 400g", "pct": 20, "new_price_paise": 3600}])
    assert "Amul Dahi 400g 20% off (Rs 36)" in t and "Sharma Store" in t
