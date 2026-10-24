"""One scoped, idempotent application-fee quote reservation.

A PREPARED row is NOT a payment intent, checkout URL, receipt or paid status.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from app.core.database import Base


class ApplicationFeeAttempt(Base):
    __tablename__ = "application_fee_attempts"
    __table_args__ = (
        UniqueConstraint("application_id", name="uq_application_fee_attempt_application"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(Integer, ForeignKey("lease_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    applicant_user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id", ondelete="RESTRICT"), nullable=False)
    idempotency_key = Column(String(80), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    status = Column(String(20), nullable=False, default="PREPARED")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
