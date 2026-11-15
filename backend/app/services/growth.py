"""Growth agent logic: repeat/lapsed customer detection and offer drafting."""
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import utcnow
from app.models import Customer, Sale

LAPSED_DAYS = 30
MIN_PRIOR_VISITS = 4
DEFAULT_CASHBACK_PAISE = 2000  # Rs 20

OFFER_TEMPLATES = {
    "hi": "{shop} mein aapki yaad aa rahi hai! {festival}Is hafte Paytm se Rs {cb} ke upar ka bill bharein aur Rs {cb} cashback payein. Aapka intezaar hai!",
    "mr": "{shop} madhe tumchi aathvan yete! {festival}Ya aathvdyat Paytm ne bill bhara ani Rs {cb} cashback mila. Vaat pahto!",
    "en": "We miss you at {shop}! {festival}Pay with Paytm this week and get Rs {cb} cashback. See you soon!",
}


def lapsed_customers(s: Session, mid: int) -> list[dict[str, Any]]:
    """Regulars (>= MIN_PRIOR_VISITS before the window) with no purchase in the last LAPSED_DAYS."""
    now = utcnow()
    recent_cut = now - timedelta(days=LAPSED_DAYS)
    rows = s.execute(
        select(Customer.id, Customer.name, Customer.phone, func.count(Sale.id), func.max(Sale.ts),
               func.coalesce(func.sum(Sale.amount_paise), 0))
        .join(Sale, Sale.customer_id == Customer.id)
        .where(Customer.merchant_id == mid)
        .group_by(Customer.id, Customer.name, Customer.phone)
        .having(func.max(Sale.ts) < recent_cut, func.count(Sale.id) >= MIN_PRIOR_VISITS)
        .order_by(func.sum(Sale.amount_paise).desc())
    ).all()
    return [
        {"customer_id": r[0], "name": r[1], "phone": r[2], "visits": int(r[3]),
         "days_absent": (now - r[4]).days, "lifetime_paise": int(r[5])}
        for r in rows
    ]


def repeat_customer_stats(s: Session, mid: int) -> dict[str, Any]:
    since = utcnow() - timedelta(days=LAPSED_DAYS)
    active = s.execute(
        select(func.count(func.distinct(Sale.customer_id))).where(Sale.merchant_id == mid, Sale.ts >= since, Sale.customer_id.isnot(None))
    ).scalar_one()
    total_known = s.execute(
        select(func.count(func.distinct(Sale.customer_id))).where(Sale.merchant_id == mid, Sale.customer_id.isnot(None))
    ).scalar_one()
    return {"active_30d": int(active), "known_customers": int(total_known), "lapsed": len(lapsed_customers(s, mid))}


CLEARANCE_TEMPLATES = {
    "hi": "{shop} mein aaj khaas offer! {items}. Sirf kuch din ke liye, aaj hi aaiye!",
    "mr": "{shop} madhe aaj khaas offer! {items}. Fakt kahi diwas, aajach ya!",
    "ta": "{shop} kadaiyil indru sirappu offer! {items}. Konja naal mattume, ippave vaanga!",
    "en": "Special offer at {shop}! {items}. Only for a few days, drop by today!",
}


def clearance_text(lang: str, shop: str, items: list[dict[str, Any]]) -> str:
    """items: [{name, pct, new_price_paise}] -> short WhatsApp offer (numbers come from the service, not an LLM)."""
    line = ", ".join(f"{i['name']} {i['pct']}% off (Rs {i['new_price_paise'] / 100:g})" for i in items)
    return CLEARANCE_TEMPLATES.get(lang, CLEARANCE_TEMPLATES["hi"]).format(shop=shop, items=line)


def recent_customers(s: Session, mid: int, limit: int = 20) -> list[dict[str, Any]]:
    """Customers who bought in the last LAPSED_DAYS, most recent first (audience for in-store offers)."""
    since = utcnow() - timedelta(days=LAPSED_DAYS)
    rows = s.execute(
        select(Customer.id, Customer.name, Customer.phone, func.max(Sale.ts))
        .join(Sale, Sale.customer_id == Customer.id)
        .where(Customer.merchant_id == mid, Sale.ts >= since)
        .group_by(Customer.id, Customer.name, Customer.phone)
        .order_by(func.max(Sale.ts).desc()).limit(limit)
    ).all()
    return [{"customer_id": r[0], "name": r[1], "phone": r[2]} for r in rows]


def offer_text(lang: str, shop: str, cashback_paise: int, festival: str | None = None) -> str:
    fest = f"{festival} ki shubhkamnayein! " if festival and lang != "en" else (f"Happy {festival}! " if festival else "")
    return OFFER_TEMPLATES.get(lang, OFFER_TEMPLATES["hi"]).format(shop=shop, cb=cashback_paise // 100, festival=fest)
