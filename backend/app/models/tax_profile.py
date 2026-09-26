"""Encrypted taxpayer-profile prerequisite; NEVER persist unencrypted W-9 data."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from app.core.database import Base


class TaxProfile(Base):
    __tablename__ = "tax_profiles"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_type = Column(String(16), nullable=False)  # ORGANIZATION, OWNER, VENDOR
    subject_id = Column(Integer, nullable=False)
    encrypted_payload = Column(Text, nullable=False)  # legal name, address, TIN; authenticated ciphertext only
    # Substantive taxpayer/W-9 revision; key rewrapping does NOT increment this.
    profile_revision = Column(Integer, nullable=False, default=1, server_default="1")
    w9_on_file = Column(Boolean, nullable=False, default=False, server_default="false")
    w9_received_on = Column(Date, nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "subject_type", "subject_id", name="uq_tax_profile_subject"),
        Index("ix_tax_profile_subject", "organization_id", "subject_type", "subject_id"),
    )
