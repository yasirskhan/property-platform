"""Phase 4.12 short-term-rental channel reference foundation.

These records are staff-entered listing references only. They do not contain
provider credentials and do not claim live Airbnb/Vrbo API connectivity,
reservation synchronization, calendar synchronization, payouts, or pricing sync.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint

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


class ShortTermRentalNightlyPrice(Base):
    """Explicit staff-entered nightly rate for an existing unit.

    This is operational pricing metadata only. It is not synchronized to a
    provider and does not create a booking, lease, charge, invoice, receipt,
    payout, or accounting entry.
    """

    __tablename__ = "short_term_rental_nightly_prices"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    unit_id = Column(Integer, ForeignKey("units.id", ondelete="CASCADE"), nullable=False, index=True)
    night_date = Column(Date, nullable=False, index=True)
    nightly_rate = Column(Numeric(12, 2), nullable=False)
    minimum_stay_nights = Column(Integer, nullable=False, default=1, server_default="1")
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "property_id", "unit_id", "night_date",
            name="uq_short_term_rental_nightly_price_unit_date",
        ),
        Index(
            "ix_short_term_rental_nightly_price_scope",
            "organization_id", "property_id", "unit_id", "night_date", "is_active",
        ),
    )


class ShortTermRentalTurnover(Base):
    """Staff-recorded turnover schedule for an existing unit.

    A turnover may reference an existing cleaning work order and/or an existing
    inspection record. Those references are informational only: this record
    never creates, advances, closes, or otherwise mutates either workflow and
    is not linked to an external reservation or provider calendar.
    """

    __tablename__ = "short_term_rental_turnovers"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    unit_id = Column(Integer, ForeignKey("units.id", ondelete="CASCADE"), nullable=False, index=True)
    scheduled_start = Column(DateTime, nullable=False, index=True)
    scheduled_end = Column(DateTime, nullable=False, index=True)
    status = Column(String(24), nullable=False, default="SCHEDULED", server_default="SCHEDULED")
    cleaning_work_order_id = Column(Integer, ForeignKey("work_orders.id", ondelete="SET NULL"), nullable=True, index=True)
    inspection_record_id = Column(Integer, ForeignKey("unit_inspection_records.id", ondelete="SET NULL"), nullable=True, index=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "property_id", "unit_id", "scheduled_start",
            name="uq_short_term_rental_turnover_unit_start",
        ),
        Index(
            "ix_short_term_rental_turnover_scope",
            "organization_id", "property_id", "unit_id", "scheduled_start", "is_active",
        ),
    )
