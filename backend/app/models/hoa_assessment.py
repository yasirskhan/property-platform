"""Staff-only HOA assessment proposals. NOT approved, issued, booked or receivable."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String
from app.core.database import Base


class HOAAssessmentProposal(Base):
    __tablename__ = "hoa_assessment_proposals"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id = Column(Integer, ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(120), nullable=False)
    assessment_type = Column(String(12), nullable=False)  # RECURRING or SPECIAL
    frequency = Column(String(12), nullable=False)  # MONTHLY / QUARTERLY / ANNUAL / ONE_TIME
    proposed_amount = Column(Numeric(14, 2), nullable=False)
    proposed_first_on = Column(Date, nullable=False)
    proposed_through = Column(Date, nullable=True)
    # Intentionally NO paid, approved, posted, receivable, payer, tax, due, GL or automatic workflow fields.
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_hoa_proposal_scope", "organization_id", "association_id", "property_id"),
    )
