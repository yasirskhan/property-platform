"""Phase 4.11 staff-recorded senior-housing age restriction facts.

These records are operational references only. They do not determine resident
eligibility, certify Fair Housing/HOPA compliance, or establish HUD status.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from app.core.database import Base


class SeniorAgeRestriction(Base):
    __tablename__ = "senior_age_restrictions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    restriction_type = Column(String(32), nullable=False)
    label = Column(String(120), nullable=False)
    minimum_age = Column(Integer, nullable=True)
    recorded_authority = Column(String(180), nullable=True)
    reference_identifier = Column(String(180), nullable=True)
    effective_start = Column(Date, nullable=True)
    effective_end = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "property_id", "label", name="uq_senior_age_restriction_property_label"),
        Index("ix_senior_age_restriction_scope", "organization_id", "property_id", "is_active"),
    )


class SeniorCareResource(Base):
    """Property-level care-coordination resource placeholder.

    This is a service/contact directory only. It is intentionally not resident
    specific and must not be used as a diagnosis, treatment plan, eligibility
    record, or proof of a legal care obligation.
    """

    __tablename__ = "senior_care_resources"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_type = Column(String(40), nullable=False)
    provider_name = Column(String(180), nullable=False)
    contact_name = Column(String(180), nullable=True)
    phone = Column(String(60), nullable=True)
    email = Column(String(255), nullable=True)
    reference_url = Column(String(500), nullable=True)
    availability_notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "property_id",
            "resource_type",
            "provider_name",
            name="uq_senior_care_resource_property_type_provider",
        ),
        Index(
            "ix_senior_care_resource_scope",
            "organization_id",
            "property_id",
            "is_active",
        ),
    )
