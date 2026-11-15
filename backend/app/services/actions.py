"""Action lifecycle: propose -> (merchant approves) -> execute. Idempotent; the LLM never calls execute."""
import logging
import random
import secrets
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import ConflictError, NotFoundError, fmt_inr, log, utcnow
from app.models import (
    Action,
    Campaign,
    CampaignTarget,
    Customer,
    Distributor,
    KhataEntry,
    Merchant,
    Message,
    Outcome,
    PaymentLink,
    Product,
    PurchaseOrder,
    Sale,
)
from app.services import growth, inventory, khata

logger = logging.getLogger("actions")
REDEEM_MODE = "UPI+CB"  # sales created by simulated campaign redemptions (removed on demo reset)


# ---------------- propose ----------------
def _existing_pending(s: Session, mid: int, kind: str, key: str) -> Action | None:
    for a in s.scalars(select(Action).where(Action.merchant_id == mid, Action.kind == kind, Action.status == "pending")):
        if a.payload.get("dedupe_key") == key:
            return a
    return None


def _merchant(s: Session, mid: int) -> Merchant:
    m = s.get(Merchant, mid)
    if not m:
        raise NotFoundError("Merchant not found")
    return m


def _already_reminded(s: Session, mid: int) -> set[int]:
    """Khata entries that already have an unpaid payment link (reminder already sent)."""
    rows = s.scalars(select(PaymentLink.khata_entry_id).where(PaymentLink.merchant_id == mid, PaymentLink.status == "pending"))
    return set(rows)


def _recently_ordered(s: Session, mid: int, days: int = 3) -> set[int]:
    since = utcnow() - timedelta(days=days)
    ids: set[int] = set()
    for po in s.scalars(select(PurchaseOrder).where(PurchaseOrder.merchant_id == mid, PurchaseOrder.created_at >= since)):
        ids.update(int(i["product_id"]) for i in po.items)
    return ids


def _already_targeted(s: Session, mid: int) -> set[int]:
    rows = s.scalars(
        select(CampaignTarget.customer_id).join(Campaign, Campaign.id == CampaignTarget.campaign_id)
        .where(Campaign.merchant_id == mid, Campaign.status == "live")
    )
    return set(rows)


def propose_khata_reminders(s: Session, mid: int) -> Action | None:
    done = _already_reminded(s, mid)
    od = [e for e in khata.overdue(s, mid) if e["khata_id"] not in done]
    if not od:
        return None
    m = _merchant(s, mid)
    key = ",".join(str(e["khata_id"]) for e in od)
    if (a := _existing_pending(s, mid, "khata_reminders", key)):
        return a
    total = sum(e["amount_paise"] for e in od)
    action = Action(
        merchant_id=mid, kind="khata_reminders",
        title=f"Send {len(od)} udhaar reminders with Paytm payment links",
        reason=f"{len(od)} customers owe {fmt_inr(total)} and are {min(e['days_pending'] for e in od)}+ days overdue. "
               "Polite reminders with a pay link recover faster than calling.",
        payload={"dedupe_key": key, "language": m.language, "entries": [
            {k: e[k] for k in ("khata_id", "customer_id", "name", "phone", "amount_paise", "days_pending")} for e in od]},
    )
    s.add(action)
    s.flush()
    return action


def propose_reorders(s: Session, mid: int) -> list[Action]:
    out: list[Action] = []
    ordered = _recently_ordered(s, mid)
    for draft in inventory.draft_reorders(s, mid):
        draft["items"] = [i for i in draft["items"] if i["product_id"] not in ordered]
        if not draft["items"]:
            continue
        key = f"{draft['distributor_id']}:" + ",".join(f"{i['product_id']}x{i['qty']}" for i in draft["items"])
        if (a := _existing_pending(s, mid, "reorder", key)):
            out.append(a)
            continue
        worst = min(i["days_of_cover"] for i in draft["items"])
        names = ", ".join(f"{i['name']} x{i['qty']}" for i in draft["items"])
        a = Action(
            merchant_id=mid, kind="reorder", title=f"Reorder from {draft['distributor_name']}: {names}",
            reason=f"Stock will run out in about {worst:g} days at current sales speed. "
                   f"Quantities cover the next {inventory.TARGET_COVER_DAYS} days of demand.",
            payload={**draft, "dedupe_key": key},
        )
        s.add(a)
        s.flush()
        out.append(a)
    return out


CLEARANCE_MAX_DAYS = 7  # propose markdowns for batches expiring within a week
CLEARANCE_AUDIENCE = 20


def propose_clearance(s: Session, mid: int) -> Action | None:
    """Near-expiry stock likely to go unsold -> pending markdown + WhatsApp offer for approval."""
    rows = [r for r in inventory.expiring(s, mid, CLEARANCE_MAX_DAYS)
            if r["days_left"] >= 0 and r["units_at_risk"] > 0 and r["suggested_discount_pct"] > 0 and not r["clearance_pct"]]
    if not rows:
        return None
    items = [{
        "product_id": r["product_id"], "name": r["name"], "pct": r["suggested_discount_pct"],
        "days_left": r["days_left"], "units_at_risk": r["units_at_risk"],
        "value_at_risk_paise": r["value_at_risk_paise"],
        "new_price_paise": r["price_paise"] * (100 - r["suggested_discount_pct"]) // 100,
    } for r in rows]
    key = ",".join(f"{i['product_id']}@{i['pct']}" for i in items)
    if (a := _existing_pending(s, mid, "clearance", key)):
        return a
    m = _merchant(s, mid)
    audience = growth.recent_customers(s, mid, CLEARANCE_AUDIENCE)
    names = ", ".join(f"{i['name']} {i['pct']}% off" for i in items)
    total = sum(i["value_at_risk_paise"] for i in items)
    a = Action(
        merchant_id=mid, kind="clearance", title=f"Clear near-expiry stock: {names}",
        reason=f"{len(items)} product(s) expire within {CLEARANCE_MAX_DAYS} days and will not all sell at the current pace "
               f"(about {fmt_inr(total)} at cost at risk). The discount never goes below your cost.",
        payload={"dedupe_key": key, "language": m.language, "items": items, "customers": audience},
    )
    s.add(a)
    s.flush()
    return a


def propose_winback(s: Session, mid: int, cashback_paise: int = growth.DEFAULT_CASHBACK_PAISE,
                    festival: str | None = None, offer_override: str | None = None) -> Action | None:
    targeted = _already_targeted(s, mid)
    lapsed = [c for c in growth.lapsed_customers(s, mid) if c["customer_id"] not in targeted]
    if not lapsed:
        return None
    m = _merchant(s, mid)
    key = f"{len(lapsed)}:{cashback_paise}:{festival or ''}"
    if (a := _existing_pending(s, mid, "campaign", key)):
        return a
    text = offer_override or growth.offer_text(m.language, m.name, cashback_paise, festival)
    a = Action(
        merchant_id=mid, kind="campaign",
        title=f"Win back {len(lapsed)} regulars with Rs {cashback_paise // 100} cashback",
        reason=f"{len(lapsed)} regular customers have not visited in {growth.LAPSED_DAYS}+ days. "
               "Bringing back lapsed regulars is cheaper than finding new customers.",
        payload={"dedupe_key": key, "name": f"{festival + ' ' if festival else ''}Win-back Rs {cashback_paise // 100}",
                 "offer_text": text, "cashback_paise": cashback_paise,
                 "customers": [{k: c[k] for k in ("customer_id", "name", "phone")} for c in lapsed]},
    )
    s.add(a)
    s.flush()
    return a


def pending(s: Session, mid: int) -> list[Action]:
    return list(s.scalars(select(Action).where(Action.merchant_id == mid, Action.status == "pending").order_by(Action.id)))


# ---------------- decide / execute ----------------
def get_action(s: Session, mid: int, action_id: int) -> Action:
    a = s.scalar(select(Action).where(Action.id == action_id, Action.merchant_id == mid).with_for_update())
    if not a:
        raise NotFoundError("Action not found")
    return a


def reject(s: Session, mid: int, action_id: int) -> Action:
    a = get_action(s, mid, action_id)
    if a.status == "pending":
        a.status, a.decided_at = "rejected", utcnow()
    elif a.status != "rejected":
        raise ConflictError(f"Action already {a.status}")
    return a


def approve(s: Session, mid: int, action_id: int) -> Action:
    """Idempotent: a second approve returns the stored result without re-executing."""
    a = get_action(s, mid, action_id)
    if a.status in ("executed",):
        return a
    if a.status == "rejected":
        raise ConflictError("Action was rejected")
    a.result = {"kind": a.kind, **_EXECUTORS[a.kind](s, mid, a)}
    a.status, a.decided_at = "executed", utcnow()
    log(logger, "action executed", action_id=a.id, kind=a.kind, merchant_id=mid)
    return a


def _wa_link(phone: str, text: str) -> str:
    from urllib.parse import quote

    return f"https://wa.me/91{phone[-10:]}?text={quote(text)}"


def _exec_khata(s: Session, mid: int, a: Action) -> dict[str, Any]:
    m = _merchant(s, mid)
    web = get_settings().public_web_url
    sent = []
    for e in a.payload["entries"]:
        entry = s.get(KhataEntry, e["khata_id"])
        if not entry or entry.merchant_id != mid or entry.status != "open":
            continue
        link = s.scalar(select(PaymentLink).where(PaymentLink.khata_entry_id == entry.id, PaymentLink.status == "pending"))
        if not link:
            link = PaymentLink(id=secrets.token_urlsafe(6), merchant_id=mid, khata_entry_id=entry.id, amount_paise=entry.amount_paise)
            s.add(link)
            s.flush()
        url = f"{web}/pay/{link.id}"
        body = khata.reminder_text(a.payload.get("language", "hi"), e["name"], m.name, entry.amount_paise, e["days_pending"], url)
        s.add(Message(merchant_id=mid, channel="whatsapp", to_name=e["name"], to_phone=e["phone"], body=body, payment_link_id=link.id))
        sent.append({"name": e["name"], "amount_paise": entry.amount_paise, "link_id": link.id, "pay_url": url,
                     "whatsapp_url": _wa_link(e["phone"], body)})
    return {"sent": sent, "count": len(sent)}


def _exec_reorder(s: Session, mid: int, a: Action) -> dict[str, Any]:
    p = a.payload
    dist = s.get(Distributor, p["distributor_id"])
    m = _merchant(s, mid)
    lines = "\n".join(f"- {i['name']}: {i['qty']}" for i in p["items"])
    text = f"Namaste {dist.name if dist else ''}, {m.name} ({m.city}) ki taraf se order:\n{lines}\nKal tak delivery ho sake to bhej dijiye. Dhanyavaad!"
    po = PurchaseOrder(merchant_id=mid, distributor_id=p["distributor_id"], items=p["items"], status="sent", message_text=text)
    s.add(po)
    if dist:
        s.add(Message(merchant_id=mid, channel="whatsapp", to_name=dist.name, to_phone=dist.phone, body=text))
    for i in p["items"]:
        s.add(Outcome(merchant_id=mid, kind="stockout_prevented", ref=f"po:{i['product_id']}",
                      value_paise=int(i["daily_revenue_paise"]) * 2))
    s.flush()
    return {"purchase_order_id": po.id, "distributor": p["distributor_name"], "items": p["items"],
            "whatsapp_url": _wa_link(dist.phone, text) if dist else None}


def _exec_campaign(s: Session, mid: int, a: Action) -> dict[str, Any]:
    p = a.payload
    c = Campaign(merchant_id=mid, name=p["name"], offer_text=p["offer_text"], cashback_paise=p["cashback_paise"], status="live")
    s.add(c)
    s.flush()
    for cust in p["customers"]:
        s.add(CampaignTarget(campaign_id=c.id, customer_id=cust["customer_id"]))
        s.add(Message(merchant_id=mid, channel="whatsapp", to_name=cust["name"], to_phone=cust["phone"], body=p["offer_text"]))
    return {"campaign_id": c.id, "targets": len(p["customers"])}


def _exec_clearance(s: Session, mid: int, a: Action) -> dict[str, Any]:
    p = a.payload
    m = _merchant(s, mid)
    applied: list[dict[str, Any]] = []
    for i in p["items"]:
        prod = s.get(Product, i["product_id"])
        if not prod or prod.merchant_id != mid:
            continue
        prod.clearance_pct = int(i["pct"])
        s.add(Outcome(merchant_id=mid, kind="clearance", ref=f"clr:{prod.id}", value_paise=int(i["value_at_risk_paise"])))
        applied.append(i)
    body = growth.clearance_text(p.get("language", m.language), m.name, applied) if applied else ""
    reached = 0
    for c in p["customers"] if applied else []:
        s.add(Message(merchant_id=mid, channel="whatsapp", to_name=c["name"], to_phone=c["phone"], body=body))
        reached += 1
    s.flush()
    return {"items": applied, "customers": reached}


_EXECUTORS = {"khata_reminders": _exec_khata, "reorder": _exec_reorder, "campaign": _exec_campaign,
              "clearance": _exec_clearance}


# ---------------- payment (mock Paytm gateway) ----------------
def pay_link(s: Session, link_id: str) -> PaymentLink:
    """Idempotent payment confirmation. Row lock prevents double credit on double-click."""
    link = s.scalar(select(PaymentLink).where(PaymentLink.id == link_id).with_for_update())
    if not link:
        raise NotFoundError("Payment link not found")
    if link.status == "paid":
        return link
    now = utcnow()
    link.status, link.paid_at = "paid", now
    entry = s.get(KhataEntry, link.khata_entry_id)
    if entry:
        entry.status, entry.paid_at = "recovered", now
    s.add(Outcome(merchant_id=link.merchant_id, kind="recovered", value_paise=link.amount_paise, ref=f"link:{link.id}"))
    return link


def redeem_campaign(s: Session, mid: int, campaign_id: int, count: int = 9) -> dict[str, Any]:
    """Demo helper: simulate lapsed customers walking back in and paying with the cashback offer."""
    camp = s.scalar(select(Campaign).where(Campaign.id == campaign_id, Campaign.merchant_id == mid))
    if not camp:
        raise NotFoundError("Campaign not found")
    targets = list(s.scalars(select(CampaignTarget).where(CampaignTarget.campaign_id == camp.id, CampaignTarget.redeemed.is_(False))))
    random.shuffle(targets)
    n = 0
    for t in targets[:count]:
        t.redeemed, t.redeemed_at = True, utcnow()
        basket = random.choice([18000, 24000, 31000, 42000])
        s.add(Sale(merchant_id=mid, customer_id=t.customer_id, ts=utcnow(), amount_paise=basket, mode=REDEEM_MODE))
        s.add(Outcome(merchant_id=mid, kind="customer_won_back", value_paise=basket, ref=f"camp:{camp.id}:{t.customer_id}"))
        n += 1
    return {"redeemed": n, "remaining": len(targets) - n}


# ---------------- ROI ----------------
def outcomes_summary(s: Session, mid: int, days: int = 7) -> dict[str, Any]:
    since = utcnow() - timedelta(days=days)
    rows = s.execute(
        select(Outcome.kind, func.count(Outcome.id), func.coalesce(func.sum(Outcome.value_paise), 0))
        .where(Outcome.merchant_id == mid, Outcome.created_at >= since).group_by(Outcome.kind)
    ).all()
    d = {r[0]: (int(r[1]), int(r[2])) for r in rows}
    rec = d.get("recovered", (0, 0))
    return {
        "days": days,
        "recovered_paise": rec[1], "recovered_count": rec[0],
        "stockouts_prevented": d.get("stockout_prevented", (0, 0))[0],
        "customers_won_back": d.get("customer_won_back", (0, 0))[0],
        "won_back_revenue_paise": d.get("customer_won_back", (0, 0))[1],
    }


def customer_by_phone(s: Session, phone: str) -> Customer | None:
    return s.scalar(select(Customer).where(Customer.phone == phone))
