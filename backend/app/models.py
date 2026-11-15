"""Typed ORM models. All money is stored as integer paise."""
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class Merchant(Base):
    __tablename__ = "merchants"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    owner_name: Mapped[str] = mapped_column(String(80))
    city: Mapped[str] = mapped_column(String(60))
    language: Mapped[str] = mapped_column(String(10), default="hi")
    phone: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = _now()


class Distributor(Base):
    __tablename__ = "distributors"
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20))


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    distributor_id: Mapped[int | None] = mapped_column(ForeignKey("distributors.id"))
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(60))
    unit: Mapped[str] = mapped_column(String(20), default="pcs")
    price_paise: Mapped[int] = mapped_column(Integer)
    cost_paise: Mapped[int] = mapped_column(Integer)
    gst_rate: Mapped[int] = mapped_column(Integer, default=5)
    stock_qty: Mapped[int] = mapped_column(Integer, default=0)
    reorder_qty: Mapped[int] = mapped_column(Integer, default=24)
    expiry_date: Mapped[date | None] = mapped_column(Date)  # nearest batch expiry; NULL = non-perishable
    clearance_pct: Mapped[int | None] = mapped_column(Integer)  # active near-expiry markdown, set on approval


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(20))


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (Index("ix_sales_merchant_ts", "merchant_id", "ts"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    amount_paise: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(10), default="UPI")


class SaleItem(Base):
    __tablename__ = "sale_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    qty: Mapped[int] = mapped_column(Integer)
    amount_paise: Mapped[int] = mapped_column(Integer)


class KhataEntry(Base):
    __tablename__ = "khata_entries"
    __table_args__ = (Index("ix_khata_merchant_status", "merchant_id", "status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    amount_paise: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(12), default="open")  # open | recovered
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaymentLink(Base):
    __tablename__ = "payment_links"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    khata_entry_id: Mapped[int] = mapped_column(ForeignKey("khata_entries.id"))
    amount_paise: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | paid
    created_at: Mapped[datetime] = _now()
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Message(Base):
    """Outbox. Stands in for WhatsApp/SMS; shown in the Customer Phone simulator."""

    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    channel: Mapped[str] = mapped_column(String(12), default="whatsapp")
    to_name: Mapped[str] = mapped_column(String(80))
    to_phone: Mapped[str] = mapped_column(String(20), index=True)
    body: Mapped[str] = mapped_column(Text)
    payment_link_id: Mapped[str | None] = mapped_column(ForeignKey("payment_links.id"))
    created_at: Mapped[datetime] = _now()


class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    offer_text: Mapped[str] = mapped_column(Text)
    cashback_paise: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), default="live")
    created_at: Mapped[datetime] = _now()


class CampaignTarget(Base):
    __tablename__ = "campaign_targets"
    __table_args__ = (UniqueConstraint("campaign_id", "customer_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    redeemed: Mapped[bool] = mapped_column(Boolean, default=False)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    distributor_id: Mapped[int] = mapped_column(ForeignKey("distributors.id"))
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(12), default="sent")
    message_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = _now()


class Action(Base):
    """A proposed agent action awaiting merchant approval. Idempotent by status."""

    __tablename__ = "actions"
    __table_args__ = (Index("ix_actions_merchant_status", "merchant_id", "status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    kind: Mapped[str] = mapped_column(String(30))  # khata_reminders | reorder | campaign
    title: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(12), default="pending")
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = _now()
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Outcome(Base):
    __tablename__ = "outcomes"
    __table_args__ = (Index("ix_outcomes_merchant_ts", "merchant_id", "created_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    kind: Mapped[str] = mapped_column(String(30))  # recovered | stockout_prevented | customer_won_back
    value_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    ref: Mapped[str] = mapped_column(String(60), default="")
    created_at: Mapped[datetime] = _now()


class Briefing(Base):
    __tablename__ = "briefings"
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    language: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    audio_file: Mapped[str | None] = mapped_column(String(120))
    facts: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = _now()


class AgentEvent(Base):
    """Audit trail of every agent step."""

    __tablename__ = "agent_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    thread_id: Mapped[str] = mapped_column(String(60), index=True)
    agent: Mapped[str] = mapped_column(String(30))
    event: Mapped[str] = mapped_column(String(30))
    detail: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = _now()
