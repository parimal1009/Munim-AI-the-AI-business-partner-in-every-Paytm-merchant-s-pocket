"""Khata (udhaar) agent logic: ledger queries and polite multilingual reminder drafting."""
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import fmt_inr, utcnow
from app.models import Customer, KhataEntry

OVERDUE_DAYS = 14

TEMPLATES = {
    "hi": "Namaste {name} ji, {shop} se ek chhoti si yaad dilaani thi. Aapka {amount} ka udhaar {days} din se baaki hai. "
          "Aap is link se aasani se Paytm par bhar sakte hain: {link} Dhanyavaad!",
    "mr": "Namaskar {name}, {shop} kadun ek chhoti aathvan. Tumcha {amount} cha udhaar {days} divsanpasun baaki aahe. "
          "Krupaya ya link varun Paytm ne bhara: {link} Dhanyavad!",
    "en": "Hello {name}, a gentle reminder from {shop}: your balance of {amount} has been pending for {days} days. "
          "You can pay easily via Paytm here: {link} Thank you!",
}


def ledger(s: Session, mid: int, status: str = "open") -> list[dict[str, Any]]:
    now = utcnow()
    rows = s.execute(
        select(KhataEntry, Customer).join(Customer, Customer.id == KhataEntry.customer_id)
        .where(KhataEntry.merchant_id == mid, KhataEntry.status == status)
        .order_by(KhataEntry.created_at)
    ).all()
    out = []
    for k, c in rows:
        days = (now - _aware(k.created_at)).days
        out.append({
            "khata_id": k.id, "customer_id": c.id, "name": c.name, "phone": c.phone,
            "amount_paise": k.amount_paise, "note": k.note, "days_pending": days,
            "overdue": days >= OVERDUE_DAYS, "status": k.status,
        })
    return out


def overdue(s: Session, mid: int) -> list[dict[str, Any]]:
    return [e for e in ledger(s, mid) if e["overdue"]]


def summary(s: Session, mid: int) -> dict[str, Any]:
    open_ = ledger(s, mid)
    od = [e for e in open_ if e["overdue"]]
    rec = ledger(s, mid, "recovered")
    return {
        "open_total_paise": sum(e["amount_paise"] for e in open_),
        "overdue_total_paise": sum(e["amount_paise"] for e in od),
        "overdue_count": len(od), "open_count": len(open_),
        "recovered_total_paise": sum(e["amount_paise"] for e in rec),
    }


def reminder_text(lang: str, name: str, shop: str, amount_paise: int, days: int, link: str) -> str:
    tpl = TEMPLATES.get(lang, TEMPLATES["hi"])
    return tpl.format(name=name.split()[0], shop=shop, amount=fmt_inr(amount_paise), days=days, link=link)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=utcnow().tzinfo)
