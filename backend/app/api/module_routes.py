"""Khata, inventory, growth, finance, trust, messages and the public mock payment page."""
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import MerchantId
from app.cache import cached
from app.core import NotFoundError, utcnow
from app.db import get_session
from app.models import Campaign, CampaignTarget, Customer, KhataEntry, Merchant, Message, PaymentLink
from app.schemas import KhataEntryIn, MessageOut, PayInfo
from app.services import actions, finance, growth, inventory, khata, trust

router = APIRouter(prefix="/api")


@router.get("/khata")
@cached("khata")
def khata_ledger(mid: int = MerchantId, s: Session = Depends(get_session)) -> dict[str, Any]:
    rows = [{k: v for k, v in e.items() if k != "phone"} for e in khata.ledger(s, mid)]
    return {"summary": khata.summary(s, mid), "open": rows,
            "recovered": [{k: v for k, v in e.items() if k != "phone"} for e in khata.ledger(s, mid, "recovered")]}


@router.post("/khata/entries")
def add_khata(body: KhataEntryIn, mid: int = MerchantId, s: Session = Depends(get_session)) -> dict[str, int]:
    cust = s.scalar(select(Customer).where(Customer.merchant_id == mid, Customer.phone == body.phone))
    if not cust:
        cust = Customer(merchant_id=mid, name=body.customer_name, phone=body.phone)
        s.add(cust)
        s.flush()
    e = KhataEntry(merchant_id=mid, customer_id=cust.id, amount_paise=body.amount_rupees * 100, note=body.note,
                   created_at=utcnow(), status="open")
    s.add(e)
    s.commit()
    return {"khata_id": e.id}


@router.get("/inventory")
@cached("inventory")
def inventory_view(mid: int = MerchantId, s: Session = Depends(get_session)) -> dict[str, Any]:
    return {"products": inventory.stock_levels(s, mid), "drafts": inventory.draft_reorders(s, mid),
            "expiring": inventory.expiring(s, mid)}


@router.get("/growth")
@cached("growth")
def growth_view(mid: int = MerchantId, s: Session = Depends(get_session)) -> dict[str, Any]:
    camps = []
    for c in s.scalars(select(Campaign).where(Campaign.merchant_id == mid).order_by(Campaign.id.desc())):
        ts = s.scalars(select(CampaignTarget).where(CampaignTarget.campaign_id == c.id)).all()
        camps.append({"id": c.id, "name": c.name, "offer_text": c.offer_text, "cashback_paise": c.cashback_paise,
                      "targets": len(ts), "redeemed": sum(1 for t in ts if t.redeemed)})
    lapsed = [{k: v for k, v in c.items() if k != "phone"} for c in growth.lapsed_customers(s, mid)]
    return {"stats": growth.repeat_customer_stats(s, mid), "lapsed": lapsed[:50], "campaigns": camps}


@router.post("/growth/campaigns/{campaign_id}/simulate-redemptions")
def simulate(campaign_id: int, mid: int = MerchantId, s: Session = Depends(get_session)) -> dict[str, Any]:
    out = actions.redeem_campaign(s, mid, campaign_id)
    s.commit()
    return out


@router.get("/finance")
@cached("finance")
def finance_view(mid: int = MerchantId, s: Session = Depends(get_session)) -> dict[str, Any]:
    return {"forecast": finance.cashflow_forecast(s, mid), "loan": finance.loan_eligibility(s, mid), "gst": finance.gst_summary(s, mid)}


@router.get("/trust")
@cached("trust")
def trust_view(mid: int = MerchantId, s: Session = Depends(get_session)) -> dict[str, Any]:
    return {"alerts": trust.detect(s, mid)}


@router.get("/messages")
def messages(mid: int = MerchantId, s: Session = Depends(get_session)) -> list[dict[str, Any]]:
    """Customer Phone simulator: outbound WhatsApp messages grouped by recipient."""
    rows = s.scalars(select(Message).where(Message.merchant_id == mid).order_by(Message.id.desc()).limit(300)).all()
    grouped: dict[str, list[Message]] = defaultdict(list)
    for r in rows:
        grouped[r.to_phone].append(r)
    out = []
    for phone, msgs in grouped.items():
        links = {m.payment_link_id: s.get(PaymentLink, m.payment_link_id) for m in msgs if m.payment_link_id}
        out.append({
            "phone": phone, "name": msgs[0].to_name,
            "messages": [{**MessageOut.model_validate(m).model_dump(mode="json"),
                          "link_status": links[m.payment_link_id].status if m.payment_link_id and links.get(m.payment_link_id) else None}
                         for m in reversed(msgs)],
        })
    return sorted(out, key=lambda g: -g["messages"][-1]["id"])[:30]


# ---- public mock Paytm payment page (the customer opens this from WhatsApp) ----
@router.get("/pay/{link_id}", response_model=PayInfo)
def pay_info(link_id: str, s: Session = Depends(get_session)) -> PayInfo:
    link = s.get(PaymentLink, link_id)
    if not link:
        raise NotFoundError("Payment link not found")
    entry = s.get(KhataEntry, link.khata_entry_id)
    cust = s.get(Customer, entry.customer_id) if entry else None
    shop = s.get(Merchant, link.merchant_id)
    return PayInfo(id=link.id, merchant_name=shop.name if shop else "", customer_name=cust.name if cust else "",
                   amount_paise=link.amount_paise, status=link.status, note=entry.note if entry else "")


@router.post("/pay/{link_id}", response_model=PayInfo)
def pay_confirm(link_id: str, s: Session = Depends(get_session)) -> PayInfo:
    actions.pay_link(s, link_id)
    s.commit()
    return pay_info(link_id, s)
