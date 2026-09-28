"""Scoped HOA staff observations, NOT a legal violation, notice, fine, or liability."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, String, Text
from app.core.database import Base


class HOAObservation(Base):
    __tablename__ = "hoa_observations"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id = Column(Integer, ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    summary = Column(String(240), nullable=False)
    observed_on = Column(Date, nullable=False)
    details = Column(Text, nullable=True)
    # Deliberately no defendant/tenant, cure deadline, notice, adjudication, fine, charge, or posting fields.
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_hoa_observation_scope", "organization_id", "association_id", "property_id"),
    )
