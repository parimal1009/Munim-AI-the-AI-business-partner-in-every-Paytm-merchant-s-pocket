"""Inventory agent logic: statistical stock-out prediction and reorder drafting."""
import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import utcnow
from app.models import Distributor, Product, Sale, SaleItem
from app.seed import IST

LOOKBACK_DAYS = 14
TARGET_COVER_DAYS = 7
EXPIRY_WINDOW_DAYS = 14
MIN_DISCOUNT_PCT = 5  # below this margin a markdown is not worth proposing


def ist_today() -> date:
    return datetime.now(IST).date()


def daily_demand(s: Session, mid: int, days: int = LOOKBACK_DAYS) -> dict[int, float]:
    since = utcnow() - timedelta(days=days)
    rows = s.execute(
        select(SaleItem.product_id, func.sum(SaleItem.qty))
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(Sale.merchant_id == mid, Sale.ts >= since)
        .group_by(SaleItem.product_id)
    ).all()
    return {int(r[0]): int(r[1]) / days for r in rows}


def clearance_discount_pct(days_left: int, price_paise: int, cost_paise: int) -> int:
    """Markdown for near-expiry stock: tiered by days left, never below cost, 0 if the margin is too thin."""
    if days_left < 0 or price_paise <= 0:
        return 0
    tier = 30 if days_left <= 2 else 20 if days_left <= 5 else 10
    margin_pct = max(0, (price_paise - cost_paise) * 100 // price_paise)  # price after discount stays >= cost
    pct = min(tier, margin_pct)
    return pct if pct >= MIN_DISCOUNT_PCT else 0


def expiry_severity(days_left: int) -> str:
    if days_left < 0:
        return "expired"
    if days_left <= 3:
        return "critical"
    if days_left <= 7:
        return "soon"
    return "watch"


def units_at_risk(stock_qty: int, avg_daily_units: float, days_left: int) -> int:
    """Units that will probably still be on the shelf when the batch expires."""
    if days_left < 0:
        return stock_qty
    return max(0, math.ceil(stock_qty - avg_daily_units * days_left))


def stock_levels(s: Session, mid: int) -> list[dict[str, Any]]:
    demand = daily_demand(s, mid)
    today = ist_today()
    out: list[dict[str, Any]] = []
    for p in s.scalars(select(Product).where(Product.merchant_id == mid)):
        avg = demand.get(p.id, 0.0)
        cover = round(p.stock_qty / avg, 1) if avg > 0 else None
        days_left = (p.expiry_date - today).days if p.expiry_date else None
        # a markdown only applies while the batch is unexpired and in stock
        active_pct = p.clearance_pct if p.clearance_pct and days_left is not None and days_left >= 0 and p.stock_qty > 0 else None
        out.append({
            "product_id": p.id, "name": p.name, "category": p.category, "stock_qty": p.stock_qty,
            "avg_daily_units": round(avg, 1), "days_of_cover": cover, "unit": p.unit,
            "distributor_id": p.distributor_id, "price_paise": p.price_paise, "cost_paise": p.cost_paise,
            "expiry_date": p.expiry_date.isoformat() if p.expiry_date else None, "days_to_expiry": days_left,
            "clearance_pct": active_pct,
            "selling_price_paise": p.price_paise * (100 - active_pct) // 100 if active_pct else p.price_paise,
        })
    return sorted(out, key=lambda x: (x["days_of_cover"] is None, x["days_of_cover"] or 0))


def expiring(s: Session, mid: int, within_days: int = EXPIRY_WINDOW_DAYS) -> list[dict[str, Any]]:
    """In-stock products whose batch expires within `within_days` (or already expired), soonest first."""
    out: list[dict[str, Any]] = []
    for r in stock_levels(s, mid):
        days = r["days_to_expiry"]
        if days is None or days > within_days or r["stock_qty"] <= 0:
            continue
        risk_units = units_at_risk(r["stock_qty"], r["avg_daily_units"], days)
        out.append({
            "product_id": r["product_id"], "name": r["name"], "unit": r["unit"], "stock_qty": r["stock_qty"],
            "avg_daily_units": r["avg_daily_units"], "expiry_date": r["expiry_date"], "days_left": days,
            "severity": expiry_severity(days), "units_at_risk": risk_units,
            "value_at_risk_paise": risk_units * r["cost_paise"],
            "price_paise": r["price_paise"], "cost_paise": r["cost_paise"],
            "suggested_discount_pct": clearance_discount_pct(days, r["price_paise"], r["cost_paise"]) if risk_units > 0 else 0,
            "clearance_pct": r["clearance_pct"], "selling_price_paise": r["selling_price_paise"],
        })
    return sorted(out, key=lambda x: x["days_left"])


def at_risk(s: Session, mid: int, threshold_days: float = 3.5) -> list[dict[str, Any]]:
    return [x for x in stock_levels(s, mid) if x["days_of_cover"] is not None and x["days_of_cover"] <= threshold_days]


def draft_reorders(s: Session, mid: int, threshold_days: float = 3.5) -> list[dict[str, Any]]:
    """Group at-risk products by distributor, sizing each line to TARGET_COVER_DAYS of demand."""
    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in at_risk(s, mid, threshold_days):
        if r["distributor_id"] is None:
            continue
        need = math.ceil(r["avg_daily_units"] * TARGET_COVER_DAYS) - r["stock_qty"]
        if need <= 0:
            continue
        groups[r["distributor_id"]].append({
            "product_id": r["product_id"], "name": r["name"], "qty": need,
            "days_of_cover": r["days_of_cover"], "daily_revenue_paise": int(r["avg_daily_units"] * r["price_paise"]),
        })
    names = {d.id: d.name for d in s.scalars(select(Distributor).where(Distributor.merchant_id == mid))}
    return [{"distributor_id": d, "distributor_name": names.get(d, "Distributor"), "items": items} for d, items in groups.items()]
