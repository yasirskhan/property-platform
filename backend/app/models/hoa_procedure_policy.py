"""HOA staff-configured procedural assumptions, never verified legal authority."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from app.core.database import Base


class HOAProcedurePolicy(Base):
    __tablename__ = "hoa_procedure_policies"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id = Column(Integer, ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    jurisdiction_state = Column(String(64), nullable=True)
    jurisdiction_locality = Column(String(160), nullable=True)
    notice_preparation_days = Column(Integer, nullable=True)
    cure_preparation_days = Column(Integer, nullable=True)
    hearing_request_days = Column(Integer, nullable=True)
    proposed_fine_cap = Column(Numeric(14, 2), nullable=True)
    draft_notice_text = Column(Text, nullable=True)
    supporting_evidence_id = Column(Integer, ForeignKey("hoa_governing_evidence.id", ondelete="RESTRICT"), nullable=True)
    revision = Column(Integer, nullable=False, default=1, server_default="1")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("association_id", "property_id", name="uq_hoa_procedure_association_property"),
        Index("ix_hoa_procedure_scope", "organization_id", "association_id", "property_id"),
    )
