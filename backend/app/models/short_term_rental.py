"""Phase 4.12 short-term-rental channel reference foundation.

These records are staff-entered listing references only. They do not contain
provider credentials and do not claim live Airbnb/Vrbo API connectivity,
reservation synchronization, calendar synchronization, payouts, or pricing sync.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from app.core.database import Base


class ShortTermRentalChannel(Base):
    __tablename__ = "short_term_rental_channels"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(16), nullable=False)
    label = Column(String(120), nullable=False)
    external_listing_id = Column(String(180), nullable=True)
    public_listing_url = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "property_id", "provider", "label",
            name="uq_short_term_rental_channel_property_provider_label",
        ),
        Index(
            "ix_short_term_rental_channel_scope",
            "organization_id", "property_id", "is_active",
        ),
    )
