"""Finance agent logic: cash-flow forecast, indicative loan eligibility, GST summary."""
import statistics
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import utcnow
from app.models import Product, Sale, SaleItem
from app.services.analytics import daily_sales, ist_today

LOAN_MULTIPLIER = 0.8  # of average monthly UPI revenue
MIN_HISTORY_DAYS = 45
MAX_CV = 0.35  # coefficient of variation threshold for "stable" income


def cashflow_forecast(s: Session, mid: int, horizon: int = 7) -> list[dict[str, Any]]:
    """Weekday-seasonal average of the last 8 weeks (statistical baseline)."""
    hist = daily_sales(s, mid, days=56)
    by_wd: dict[int, list[int]] = defaultdict(list)
    for h in hist:
        by_wd[date.fromisoformat(h["date"]).weekday()].append(h["sales_paise"])
    out = []
    for i in range(horizon):
        d = ist_today() + timedelta(days=i)
        vals = by_wd.get(d.weekday()) or [0]
        out.append({"date": d.isoformat(), "expected_paise": int(statistics.mean(vals))})
    return out


def loan_eligibility(s: Session, mid: int) -> dict[str, Any]:
    hist = daily_sales(s, mid, days=60)
    days = len(hist)
    vals = [h["sales_paise"] for h in hist if h["date"] != ist_today().isoformat()]
    if days < MIN_HISTORY_DAYS or not vals:
        return {"eligible": False, "reason": "Not enough UPI history (need ~45 days)", "history_days": days}
    avg_daily = statistics.mean(vals)
    cv = statistics.pstdev(vals) / avg_daily if avg_daily else 1
    monthly = int(avg_daily * 30)
    if cv > MAX_CV:
        return {"eligible": False, "reason": "Daily income is too uneven right now", "history_days": days,
                "avg_monthly_revenue_paise": monthly}
    limit = int(monthly * LOAN_MULTIPLIER // 1000 * 1000)
    return {
        "eligible": True, "history_days": days, "avg_monthly_revenue_paise": monthly,
        "stability_score": round(max(0.0, 1 - cv / MAX_CV) * 100),
        "indicative_limit_paise": limit,
        "indicative_tenure_months": 6,
        "note": "Indicative only, based on your Paytm UPI cash flow. Final offer subject to Paytm lending partner KYC and approval.",
    }


def gst_summary(s: Session, mid: int, days: int = 30) -> dict[str, Any]:
    """Prices are GST-inclusive; split taxable value and tax per slab."""
    since = utcnow() - timedelta(days=days)
    rows = s.execute(
        select(Product.gst_rate, func.sum(SaleItem.amount_paise))
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(Sale.merchant_id == mid, Sale.ts >= since)
        .group_by(Product.gst_rate).order_by(Product.gst_rate)
    ).all()
    slabs = []
    total_tax = total_taxable = 0
    for rate, gross in rows:
        gross = int(gross)
        taxable = round(gross * 100 / (100 + rate))
        tax = gross - taxable
        slabs.append({"rate": rate, "gross_paise": gross, "taxable_paise": taxable, "tax_paise": tax})
        total_tax += tax
        total_taxable += taxable
    return {"days": days, "slabs": slabs, "total_taxable_paise": total_taxable, "total_gst_paise": total_tax,
            "total_gross_paise": total_taxable + total_tax}
