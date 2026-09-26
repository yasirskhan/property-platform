"""Manually sourced 1099 preparation records; never infer tax amounts from the GL."""
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Text,
    UniqueConstraint,
)

from app.core.database import Base


class Tax1099Review(Base):
    __tablename__ = "tax_1099_reviews"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    idempotency_key = Column(String(64), nullable=False)
    payload_fingerprint = Column(String(64), nullable=False)
    tax_year = Column(Integer, nullable=False, index=True)
    form_type = Column(String(16), nullable=False)
    income_category = Column(String(48), nullable=False)
    payer_profile_id = Column(Integer, ForeignKey("tax_profiles.id", ondelete="RESTRICT"), nullable=False, index=True)
    recipient_profile_id = Column(Integer, ForeignKey("tax_profiles.id", ondelete="RESTRICT"), nullable=False, index=True)
    amount = Column(Numeric(14, 2), nullable=False)
    source_type = Column(String(32), nullable=False)
    source_reference = Column(String(160), nullable=False)
    source_note = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default="PREPARED", server_default="PREPARED", index=True)
    source_review_confirmed = Column(Boolean, nullable=False, default=False, server_default="false")
    threshold_review_confirmed = Column(Boolean, nullable=False, default=False, server_default="false")
    recipient_review_confirmed = Column(Boolean, nullable=False, default=False, server_default="false")
    prepared_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_payer_revision = Column(Integer, nullable=True)
    reviewed_recipient_revision = Column(Integer, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_tax_1099_review_idempotency"),
        Index("ix_tax_1099_review_scope", "organization_id", "tax_year", "status", "id"),
    )
