"""Demo helpers: reset a merchant's mutable agent state so the story can be replayed."""
from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.models import (
    Action,
    AgentEvent,
    Briefing,
    Campaign,
    CampaignTarget,
    KhataEntry,
    Message,
    Outcome,
    PaymentLink,
    PurchaseOrder,
    Sale,
)
from app.seed_expiry import apply_expiry


def reset_state(s: Session, mid: int) -> None:
    camp_ids = s.scalars(Campaign.__table__.select().with_only_columns(Campaign.id).where(Campaign.merchant_id == mid)).all()
    if camp_ids:
        s.execute(delete(CampaignTarget).where(CampaignTarget.campaign_id.in_(camp_ids)))
    s.execute(delete(Sale).where(Sale.merchant_id == mid, Sale.mode == "UPI+CB"))
    apply_expiry(s.connection(), mid)  # fresh demo expiry dates, markdowns cleared
    s.execute(delete(Message).where(Message.merchant_id == mid))
    s.execute(delete(PaymentLink).where(PaymentLink.merchant_id == mid))
    s.execute(delete(Outcome).where(Outcome.merchant_id == mid))
    s.execute(delete(Campaign).where(Campaign.merchant_id == mid))
    s.execute(delete(PurchaseOrder).where(PurchaseOrder.merchant_id == mid))
    s.execute(delete(Action).where(Action.merchant_id == mid))
    s.execute(delete(Briefing).where(Briefing.merchant_id == mid))
    s.execute(delete(AgentEvent).where(AgentEvent.merchant_id == mid))
    s.execute(
        update(KhataEntry).where(KhataEntry.merchant_id == mid, KhataEntry.note != "Old udhaar")
        .values(status="open", paid_at=None)
    )
