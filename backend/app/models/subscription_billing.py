"""Subscription invoice and usage-record billing models."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    String,
)

from app.core.database import Base


class SubscriptionInvoiceStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    PAID = "PAID"
    VOID = "VOID"
    UNCOLLECTIBLE = "UNCOLLECTIBLE"


class SubscriptionInvoice(Base):
    __tablename__ = "subscription_invoices"
    __table_args__ = (
        CheckConstraint(
            "subtotal_cents >= 0",
            name="ck_subscription_invoices_subtotal",
        ),
        CheckConstraint(
            "discount_cents >= 0",
            name="ck_subscription_invoices_discount",
        ),
        CheckConstraint(
            "tax_cents >= 0",
            name="ck_subscription_invoices_tax",
        ),
        CheckConstraint(
            "total_cents >= 0",
            name="ck_subscription_invoices_total",
        ),
        CheckConstraint(
            "amount_paid_cents >= 0",
            name="ck_subscription_invoices_paid",
        ),
        CheckConstraint(
            "amount_due_cents >= 0",
            name="ck_subscription_invoices_due",
        ),
        CheckConstraint(
            "period_end IS NULL OR period_start IS NULL "
            "OR period_end >= period_start",
            name="ck_subscription_invoices_period_range",
        ),
    )

    id = Column(Integer, primary_key=True)
    subscription_id = Column(
        Integer,
        ForeignKey("subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    provider_invoice_id = Column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
    )
    invoice_number = Column(String(100), nullable=True, index=True)
    status = Column(
        SqlEnum(
            SubscriptionInvoiceStatus,
            name="subscription_invoice_status",
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=lambda statuses: [
                status.value for status in statuses
            ],
        ),
        nullable=False,
        default=SubscriptionInvoiceStatus.DRAFT,
        server_default=SubscriptionInvoiceStatus.DRAFT.value,
        index=True,
    )
    currency = Column(
        String(3),
        nullable=False,
        default="USD",
        server_default="USD",
    )
    subtotal_cents = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    discount_cents = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    tax_cents = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    total_cents = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    amount_paid_cents = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    amount_due_cents = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    due_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class UsageRecord(Base):
    __tablename__ = "usage_records"
    __table_args__ = (
        CheckConstraint(
            "quantity >= 0",
            name="ck_usage_records_quantity",
        ),
    )

    id = Column(Integer, primary_key=True)
    subscription_id = Column(
        Integer,
        ForeignKey("subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    subscription_item_id = Column(
        Integer,
        ForeignKey("subscription_items.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    metric_key = Column(String(120), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    usage_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )
    provider_usage_id = Column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
