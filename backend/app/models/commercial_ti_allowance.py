"""Source-backed Commercial tenant-improvement allowance utilization tracking."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import (
    Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text,
    UniqueConstraint,
)
from app.core.database import Base


class CommercialTIAllowanceUse(Base):
    __tablename__ = "commercial_ti_allowance_uses"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    unit_id = Column(Integer, ForeignKey("units.id", ondelete="RESTRICT"), nullable=False, index=True)
    lease_id = Column(Integer, ForeignKey("leases.id", ondelete="RESTRICT"), nullable=False, index=True)
    abstract_id = Column(Integer, ForeignKey("commercial_lease_abstracts.id", ondelete="RESTRICT"), nullable=False, index=True)
    terms_id = Column(Integer, ForeignKey("commercial_lease_terms.id", ondelete="RESTRICT"), nullable=False, index=True)
    tenant_user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    evidence_attachment_id = Column(Integer, ForeignKey("entity_attachments.id", ondelete="RESTRICT"), nullable=False, index=True)
    incurred_on = Column(Date, nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    allowance_total = Column(Numeric(14, 2), nullable=False)
    remaining_after = Column(Numeric(14, 2), nullable=False)
    note = Column(Text, nullable=False)
    request_key = Column(String(96), nullable=False)
    status = Column(String(16), nullable=False, default="ACTIVE", server_default="ACTIVE")
    voided_on = Column(Date, nullable=True)
    void_reason = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "request_key", name="uq_commercial_ti_use_request"),
        Index("ix_commercial_ti_use_scope", "organization_id", "property_id", "lease_id", "status"),
    )
