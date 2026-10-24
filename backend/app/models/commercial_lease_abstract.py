"""Commercial lease staff references and versioned source-linked term abstracts.

Nothing in these tables certifies execution or legal effect. Operative financial
workflows must recheck current scope, source and explicit accounting inputs.
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric,
    String, Text, UniqueConstraint,
)
from app.core.database import Base


class CommercialLeaseAbstract(Base):
    __tablename__ = "commercial_lease_abstracts"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    lease_id = Column(Integer, ForeignKey("leases.id", ondelete="CASCADE"), nullable=False, index=True)
    source_attachment_id = Column(Integer, ForeignKey("entity_attachments.id", ondelete="RESTRICT"), nullable=True, index=True)
    rent_commencement_on = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("organization_id", "lease_id", name="uq_commercial_lease_abstract_org_lease"),
        Index("ix_commercial_lease_abstract_scope", "organization_id", "property_id", "is_active"),
    )


class CommercialLeaseTerms(Base):
    __tablename__ = "commercial_lease_terms"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    lease_id = Column(Integer, ForeignKey("leases.id", ondelete="CASCADE"), nullable=False, index=True)
    abstract_id = Column(Integer, ForeignKey("commercial_lease_abstracts.id", ondelete="CASCADE"), nullable=False, index=True)
    source_attachment_id = Column(Integer, ForeignKey("entity_attachments.id", ondelete="RESTRICT"), nullable=False, index=True)
    revision = Column(Integer, nullable=False)
    effective_on = Column(Date, nullable=False)
    base_rent_monthly = Column(Numeric(14, 2), nullable=True)
    cam_estimate_monthly = Column(Numeric(14, 2), nullable=False, default=0, server_default="0.00")
    property_tax_estimate_monthly = Column(Numeric(14, 2), nullable=False, default=0, server_default="0.00")
    insurance_estimate_monthly = Column(Numeric(14, 2), nullable=False, default=0, server_default="0.00")
    cam_share_percent = Column(Numeric(7, 4), nullable=True)
    percentage_rent_rate = Column(Numeric(7, 4), nullable=True)
    percentage_rent_breakpoint_annual = Column(Numeric(14, 2), nullable=True)
    ti_allowance_total = Column(Numeric(14, 2), nullable=True)
    co_tenancy_summary = Column(Text, nullable=True)
    billing_authorized_at = Column(DateTime, nullable=True)
    billing_authorized_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    billing_authorization_note = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("abstract_id", "revision", name="uq_commercial_terms_abstract_revision"),
        Index("ix_commercial_terms_scope", "organization_id", "property_id", "lease_id", "is_active"),
    )


class CommercialRentEscalation(Base):
    __tablename__ = "commercial_rent_escalations"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    terms_id = Column(Integer, ForeignKey("commercial_lease_terms.id", ondelete="CASCADE"), nullable=False, index=True)
    starts_on = Column(Date, nullable=False)
    monthly_base_rent = Column(Numeric(14, 2), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("terms_id", "starts_on", name="uq_commercial_escalation_terms_start"),
    )


class CommercialLeaseOption(Base):
    __tablename__ = "commercial_lease_options"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    terms_id = Column(Integer, ForeignKey("commercial_lease_terms.id", ondelete="CASCADE"), nullable=False, index=True)
    option_type = Column(String(24), nullable=False)
    exercise_start_on = Column(Date, nullable=True)
    exercise_end_on = Column(Date, nullable=True)
    summary = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        Index("ix_commercial_option_terms", "terms_id", "option_type"),
    )
