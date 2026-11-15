"""Demo expiry dates (nearest batch) for perishable products.

Run `python -m app.seed_expiry` to apply to the live database without reseeding. It is idempotent:
dates are always set relative to today, and any active clearance price is cleared.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db import engine, ensure_schema

_IST = timezone(timedelta(hours=5, minutes=30))

# product name -> days from today until the nearest batch expires
EXPIRY_DAYS: dict[str, int] = {
    "Amul Doodh 500ml": 3,
    "Amul Butter 100g": 21,
    "Amul Dahi 400g": 6,
    "Fresh Paneer 200g": 4,
    "Britannia Bread": 2,
    "Eggs (6 pack)": 9,
    "Real Juice 1L": 12,
    "Mithai Box 500g": 5,
    "Haldiram Bhujia 200g": 45,
    "Dry Fruits Box 250g": 60,
    # merchant 2 (medical store)
    "Paracetamol Strip": 9,
    "ORS Sachet": 25,
    "Biscuit Pack": 6,
}


def apply_expiry(conn: Connection, merchant_id: int | None = None) -> int:
    """Set demo expiry dates relative to today and clear markdowns (optionally for one merchant)."""
    today = datetime.now(_IST).date()
    n = 0
    for name, days in EXPIRY_DAYS.items():
        res = conn.execute(
            text("UPDATE products SET expiry_date=:d, clearance_pct=NULL WHERE name=:n "
                 "AND (CAST(:m AS INTEGER) IS NULL OR merchant_id=:m)"),
            {"d": today + timedelta(days=days), "n": name, "m": merchant_id},
        )
        n += res.rowcount or 0
    return n


if __name__ == "__main__":
    ensure_schema()
    with engine.begin() as c:
        print(f"Expiry dates set on {apply_expiry(c)} products.")
