"""Insights: sales trends, best products, peak hours. All numbers computed in SQL, never by the LLM."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import Date, cast, extract, func, select
from sqlalchemy.orm import Session

from app.core import utcnow
from app.models import Product, Sale, SaleItem
from app.seed import IST

# Synthetic peer benchmark (stand-in for anonymised similar-merchant data).
PEER_MEDIAN_DAILY_PAISE = 1_650_000


def _local_date_col() -> Any:
    return cast(func.timezone("Asia/Kolkata", Sale.ts), Date)


def ist_today() -> date:
    return datetime.now(IST).date()


def daily_sales(s: Session, mid: int, days: int = 30) -> list[dict[str, Any]]:
    d = _local_date_col()
    start = ist_today() - timedelta(days=days)
    rows = s.execute(
        select(d.label("d"), func.sum(Sale.amount_paise), func.count(Sale.id))
        .where(Sale.merchant_id == mid, d >= start, d < ist_today() + timedelta(days=1))
        .group_by(d).order_by(d)
    ).all()
    return [{"date": r[0].isoformat(), "sales_paise": int(r[1]), "txns": int(r[2])} for r in rows]


@dataclass
class DaySummary:
    date: str
    total_paise: int
    txns: int
    last_week_paise: int
    pct_vs_last_week: float | None


def day_summary(s: Session, mid: int, day: date) -> DaySummary:
    d = _local_date_col()

    def total(x: date) -> tuple[int, int]:
        r = s.execute(
            select(func.coalesce(func.sum(Sale.amount_paise), 0), func.count(Sale.id)).where(Sale.merchant_id == mid, d == x)
        ).one()
        return int(r[0]), int(r[1])

    t, n = total(day)
    lw, _ = total(day - timedelta(days=7))
    pct = round((t - lw) / lw * 100, 1) if lw else None
    return DaySummary(day.isoformat(), t, n, lw, pct)


def yesterday(s: Session, mid: int) -> DaySummary:
    return day_summary(s, mid, ist_today() - timedelta(days=1))


def top_products(s: Session, mid: int, days: int = 30, limit: int = 5) -> list[dict[str, Any]]:
    since = utcnow() - timedelta(days=days)
    profit = func.sum(SaleItem.amount_paise - SaleItem.qty * Product.cost_paise)
    rows = s.execute(
        select(Product.name, Product.category, func.sum(SaleItem.qty), func.sum(SaleItem.amount_paise), profit)
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(Sale.merchant_id == mid, Sale.ts >= since)
        .group_by(Product.name, Product.category)
        .order_by(profit.desc())
        .limit(limit)
    ).all()
    return [
        {"product": r[0], "category": r[1], "units": int(r[2]), "revenue_paise": int(r[3]), "profit_paise": int(r[4])}
        for r in rows
    ]


def peak_hours(s: Session, mid: int, days: int = 14) -> list[dict[str, Any]]:
    since = utcnow() - timedelta(days=days)
    hr = extract("hour", func.timezone("Asia/Kolkata", Sale.ts))
    rows = s.execute(
        select(hr, func.count(Sale.id), func.sum(Sale.amount_paise))
        .where(Sale.merchant_id == mid, Sale.ts >= since)
        .group_by(hr).order_by(hr)
    ).all()
    return [{"hour": int(r[0]), "txns": int(r[1]), "sales_paise": int(r[2])} for r in rows]


def category_mix(s: Session, mid: int, days: int = 30) -> list[dict[str, Any]]:
    since = utcnow() - timedelta(days=days)
    rows = s.execute(
        select(Product.category, func.sum(SaleItem.amount_paise))
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(Sale.merchant_id == mid, Sale.ts >= since)
        .group_by(Product.category).order_by(func.sum(SaleItem.amount_paise).desc())
    ).all()
    return [{"category": r[0], "revenue_paise": int(r[1])} for r in rows]


def peer_comparison(s: Session, mid: int, days: int = 14) -> dict[str, Any]:
    d = _local_date_col()
    since = ist_today() - timedelta(days=days)
    total = s.execute(
        select(func.coalesce(func.sum(Sale.amount_paise), 0)).where(Sale.merchant_id == mid, d >= since, d < ist_today())
    ).scalar_one()
    own_daily = int(total) // days
    return {
        "own_daily_avg_paise": own_daily,
        "peer_median_daily_paise": PEER_MEDIAN_DAILY_PAISE,
        "pct_vs_peers": round((own_daily - PEER_MEDIAN_DAILY_PAISE) / PEER_MEDIAN_DAILY_PAISE * 100, 1),
        "note": "Peer figure is a synthetic benchmark for the demo",
    }

