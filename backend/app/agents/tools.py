"""LangChain tools for the six agents.

Rules: (1) merchant_id comes from RunnableConfig (set by the authenticated API layer), never from model args;
(2) numbers are computed by services, the LLM only explains them; (3) propose_* tools create *pending*
actions only. Nothing is sent or paid until the merchant approves.
"""
import json
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.core import UpstreamError
from app.db import SessionLocal, session_scope
from app.services import actions, analytics, finance, growth, inventory, khata, sql_guard, trust


def _mid(config: RunnableConfig) -> int:
    return int(config["configurable"]["merchant_id"])


def _rupees(obj: Any) -> Any:
    """Convert *_paise fields to *_rs so the model never has to divide by 100."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k.endswith("_paise") and isinstance(v, (int, float)):
                out[k[:-6] + "_rs"] = round(v / 100, 2)
            else:
                out[k] = _rupees(v)
        return out
    if isinstance(obj, list):
        return [_rupees(x) for x in obj]
    return obj


def _dump(obj: Any) -> str:
    return json.dumps(_rupees(obj), ensure_ascii=False, default=str)


# ---------------- Insights ----------------
@tool
def sales_summary(config: RunnableConfig) -> str:
    """Yesterday's sales total, transaction count and % change versus the same weekday last week."""
    with session_scope() as s:
        y = analytics.yesterday(s, _mid(config))
        return _dump(y.__dict__)


@tool
def best_products(days: int = 30, config: RunnableConfig = None) -> str:  # type: ignore[assignment]
    """Top 5 products by profit over the last `days` days (revenue, units, profit)."""
    with session_scope() as s:
        return _dump(analytics.top_products(s, _mid(config), max(1, min(days, 90))))


@tool
def peak_hours(config: RunnableConfig) -> str:
    """Transactions and sales by hour of day (IST) for the last 14 days."""
    with session_scope() as s:
        rows = sorted(analytics.peak_hours(s, _mid(config)), key=lambda r: -r["txns"])[:5]
        return _dump(rows)


@tool
def peer_benchmark(config: RunnableConfig) -> str:
    """Compare this merchant's average daily sales with similar nearby merchants."""
    with session_scope() as s:
        return _dump(analytics.peer_comparison(s, _mid(config)))


@tool
def run_sql(sql: str, config: RunnableConfig) -> str:
    """Run ONE read-only SELECT on views v_sales, v_sale_items, v_products, v_khata for custom questions.
    Use only when no other tool fits. Results are capped at 50 rows."""
    try:
        with SessionLocal() as s:
            return _dump(sql_guard.run_scoped(s, _mid(config), sql))
    except sql_guard.UnsafeSQLError as exc:
        return json.dumps({"error": exc.message})
    except Exception as exc:  # noqa: BLE001
        detail = str(getattr(exc, "orig", exc)).splitlines()[0][:160]
        return json.dumps({"error": f"query failed: {detail}. Fix the PostgreSQL syntax and retry."})


# ---------------- Khata ----------------
@tool
def list_overdue_udhaar(config: RunnableConfig) -> str:
    """List customers whose udhaar is overdue (14+ days) with amount and days pending."""
    with session_scope() as s:
        rows = [{k: v for k, v in e.items() if k != "phone"} for e in khata.overdue(s, _mid(config))]
        return _dump({"overdue": rows, "summary": khata.summary(s, _mid(config))})


@tool
def propose_udhaar_reminders(config: RunnableConfig) -> str:
    """Draft polite WhatsApp reminders with a Paytm payment link for all overdue customers.
    Creates a PENDING action awaiting the merchant's approval; nothing is sent yet."""
    with session_scope() as s:
        a = actions.propose_khata_reminders(s, _mid(config))
        if not a:
            return json.dumps({"message": "No overdue udhaar"})
        return _dump({"action_id": a.id, "title": a.title, "customers": [
            {"name": e["name"], "amount_paise": e["amount_paise"], "days": e["days_pending"]} for e in a.payload["entries"]]})


# ---------------- Inventory ----------------
@tool
def stock_risks(config: RunnableConfig) -> str:
    """Products predicted to run out within ~3.5 days, with current stock, daily sales rate and days of cover."""
    with session_scope() as s:
        rows = [{k: r[k] for k in ("name", "stock_qty", "avg_daily_units", "days_of_cover")} for r in inventory.at_risk(s, _mid(config))]
        return _dump(rows or {"message": "No product is at risk of stocking out"})


@tool
def propose_reorder(config: RunnableConfig) -> str:
    """Draft purchase orders to distributors for at-risk products. Creates PENDING actions for approval."""
    with session_scope() as s:
        acts = actions.propose_reorders(s, _mid(config))
        if not acts:
            return json.dumps({"message": "Nothing needs reordering"})
        return _dump([{"action_id": a.id, "distributor": a.payload["distributor_name"],
                       "items": [{"name": i["name"], "qty": i["qty"]} for i in a.payload["items"]]} for a in acts])


@tool
def expiring_products(config: RunnableConfig) -> str:
    """Products expiring within 14 days: days left, units likely to go unsold, money at risk and the suggested discount."""
    with session_scope() as s:
        keys = ("name", "days_left", "stock_qty", "units_at_risk", "value_at_risk_paise", "suggested_discount_pct", "clearance_pct")
        rows = [{k: r[k] for k in keys} for r in inventory.expiring(s, _mid(config))]
        return _dump(rows or {"message": "No product is close to expiry"})


@tool
def propose_clearance_offer(config: RunnableConfig) -> str:
    """Create a PENDING clearance action: discount near-expiry products (never below cost) and message recent customers."""
    with session_scope() as s:
        a = actions.propose_clearance(s, _mid(config))
        if not a:
            return json.dumps({"message": "Nothing needs a clearance discount"})
        return _dump({"action_id": a.id, "title": a.title, "items": [
            {"name": i["name"], "discount_pct": i["pct"], "days_left": i["days_left"]} for i in a.payload["items"]]})


# ---------------- Growth ----------------
@tool
def customer_stats(config: RunnableConfig) -> str:
    """Counts of active, known and lapsed regular customers, plus the top 5 lapsed regulars."""
    with session_scope() as s:
        mid = _mid(config)
        top = [{k: c[k] for k in ("name", "visits", "days_absent")} for c in growth.lapsed_customers(s, mid)[:5]]
        return _dump({**growth.repeat_customer_stats(s, mid), "top_lapsed": top})


@tool
def propose_winback_offer(cashback_rupees: int = 20, festival: str = "", offer_text: str = "",
                          config: RunnableConfig = None) -> str:  # type: ignore[assignment]
    """Create a PENDING cashback campaign for all lapsed regulars. cashback_rupees: 5-100.
    festival: optional festival name. offer_text: optional short WhatsApp message (max 280 chars, no links)
    written in the merchant's language; if empty a safe template is used."""
    cb = max(5, min(int(cashback_rupees), 100)) * 100
    text = offer_text.strip()[:280] if offer_text and "http" not in offer_text.lower() else None
    with session_scope() as s:
        a = actions.propose_winback(s, _mid(config), cb, festival or None, text)
        if not a:
            return json.dumps({"message": "No lapsed customers to target"})
        return _dump({"action_id": a.id, "title": a.title, "audience": len(a.payload["customers"]),
                      "offer_text": a.payload["offer_text"]})


# ---------------- Finance ----------------
@tool
def cashflow_forecast(config: RunnableConfig) -> str:
    """Expected daily sales for the next 7 days (weekday-seasonal statistical forecast)."""
    with session_scope() as s:
        rows = finance.cashflow_forecast(s, _mid(config))
        return _dump({"next_7_days": rows, "total_expected_paise": sum(r["expected_paise"] for r in rows)})


@tool
def loan_eligibility(config: RunnableConfig) -> str:
    """Indicative loan eligibility from the merchant's UPI cash flow (limit, tenure, stability)."""
    with session_scope() as s:
        return _dump(finance.loan_eligibility(s, _mid(config)))


@tool
def gst_summary(config: RunnableConfig) -> str:
    """GST summary for the last 30 days: taxable value and tax collected per slab."""
    with session_scope() as s:
        return _dump(finance.gst_summary(s, _mid(config)))


# ---------------- Trust ----------------
@tool
def fraud_alerts(config: RunnableConfig) -> str:
    """Unusual or suspicious payments in the last 7 days with the reason each was flagged."""
    with session_scope() as s:
        return _dump(trust.detect(s, _mid(config)) or {"message": "No unusual payments found"})


AGENT_TOOLS: dict[str, list[Any]] = {
    "insights": [sales_summary, best_products, peak_hours, peer_benchmark, run_sql],
    "khata": [list_overdue_udhaar, propose_udhaar_reminders],
    "inventory": [stock_risks, propose_reorder, expiring_products, propose_clearance_offer],
    "growth": [customer_stats, propose_winback_offer],
    "finance": [cashflow_forecast, loan_eligibility, gst_summary],
    "trust": [fraud_alerts],
}

# Deterministic fallback: if the model cannot call tools, these still produce a grounded answer.
FALLBACK_TOOLS: dict[str, list[Any]] = {
    "insights": [sales_summary, best_products],
    "khata": [list_overdue_udhaar, propose_udhaar_reminders],
    "inventory": [stock_risks, propose_reorder],
    "growth": [customer_stats, propose_winback_offer],
    "finance": [loan_eligibility, cashflow_forecast],
    "trust": [fraud_alerts],
}

__all__ = ["AGENT_TOOLS", "FALLBACK_TOOLS", "UpstreamError"]
