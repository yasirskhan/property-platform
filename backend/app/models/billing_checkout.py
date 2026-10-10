"""Durable Stripe Checkout attempt storage for self-serve billing."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.core.database import Base


class BillingCheckoutStatus(str, enum.Enum):
    PENDING = "PENDING"
    CREATED = "CREATED"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class BillingCheckoutSession(Base):
    __tablename__ = "billing_checkout_sessions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_billing_checkout_sessions_org_idempotency",
        ),
    )

    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id = Column(
        Integer,
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    pricing_tier_id = Column(
        Integer,
        ForeignKey("pricing_tiers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    requested_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    idempotency_key = Column(String(128), nullable=False)
    provider = Column(
        String(32),
        nullable=False,
        default="stripe",
        server_default="stripe",
    )
    provider_session_id = Column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
    )
    checkout_url = Column(Text, nullable=True)
    status = Column(
        SqlEnum(
            BillingCheckoutStatus,
            name="billing_checkout_status",
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        nullable=False,
        default=BillingCheckoutStatus.PENDING,
        server_default=BillingCheckoutStatus.PENDING.value,
        index=True,
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
