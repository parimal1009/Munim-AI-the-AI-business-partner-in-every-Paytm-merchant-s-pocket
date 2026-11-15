"""Trust agent logic: transparent statistical anomaly detection on UPI payments."""
from collections import defaultdict
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import utcnow
from app.models import Sale
from app.seed import IST

Z_THRESHOLD = 6.0
BURST_COUNT = 4
BURST_WINDOW_MIN = 10
MIN_BURST_PAISE = 20000  # ignore tiny repeat purchases (e.g. identical Rs 10 biscuit sales)


def detect(s: Session, mid: int, days: int = 7) -> list[dict[str, Any]]:
    since = utcnow() - timedelta(days=days)
    # Baseline stats are aggregated in SQL; only the recent window is transferred.
    n, mean_raw, sd_raw = s.execute(
        select(func.count(Sale.id), func.avg(Sale.amount_paise), func.stddev_pop(Sale.amount_paise))
        .where(Sale.merchant_id == mid, Sale.ts >= utcnow() - timedelta(days=45))
    ).one()
    if n < 30:
        return []
    mean, sd = float(mean_raw), float(sd_raw or 0) or 1
    recent = s.execute(
        select(Sale.id, Sale.amount_paise, Sale.ts).where(Sale.merchant_id == mid, Sale.ts >= since)
    ).all()
    alerts: list[dict[str, Any]] = []
    for x in recent:
        z = (x.amount_paise - mean) / sd
        local = x.ts.astimezone(IST)
        if z >= Z_THRESHOLD:
            late = local.hour < 5
            alerts.append({
                "type": "unusual_amount", "severity": "high" if late else "medium", "sale_id": x.id,
                "amount_paise": x.amount_paise, "at": local.isoformat(timespec="minutes"),
                "reason": f"Payment is {z:.0f} standard deviations above your normal ticket size"
                          + (" and was received late at night" if late else ""),
            })
    groups: dict[int, list[Sale]] = defaultdict(list)
    for x in recent:
        if x.amount_paise >= MIN_BURST_PAISE:
            groups[x.amount_paise].append(x)
    for amount, xs in groups.items():
        xs.sort(key=lambda r: r.ts)
        for i in range(len(xs) - BURST_COUNT + 1):
            if xs[i + BURST_COUNT - 1].ts - xs[i].ts <= timedelta(minutes=BURST_WINDOW_MIN):
                alerts.append({
                    "type": "rapid_repeat", "severity": "medium", "sale_id": xs[i].id, "amount_paise": amount,
                    "at": xs[i].ts.astimezone(IST).isoformat(timespec="minutes"),
                    "reason": f"{BURST_COUNT}+ identical payments within {BURST_WINDOW_MIN} minutes (possible card-testing or duplicate collection)",
                })
                break
    return sorted(alerts, key=lambda a: a["at"], reverse=True)

