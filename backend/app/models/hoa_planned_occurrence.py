"""Idempotent staff-generated HOA assessment schedule occurrences, never receivables."""
from datetime import datetime
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from app.core.database import Base


class HOAPlannedOccurrence(Base):
    __tablename__ = "hoa_planned_occurrences"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id = Column(Integer, ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    proposal_id = Column(Integer, ForeignKey("hoa_assessment_proposals.id", ondelete="CASCADE"), nullable=False, index=True)
    payer_draft_id = Column(Integer, ForeignKey("hoa_payer_drafts.id", ondelete="RESTRICT"), nullable=False, index=True)
    # Immutable plan snapshot for audit. Current proposal/payer changes never alter history.
    proposed_on = Column(Date, nullable=False)
    proposed_amount = Column(Numeric(14, 2), nullable=False)
    proposal_revision_at = Column(DateTime, nullable=False)
    status = Column(String(16), nullable=False, default="PLANNED", server_default="PLANNED")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    voided_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    voided_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("proposal_id", "proposed_on", name="uq_hoa_planned_occurrence_proposal_date"),
        Index("ix_hoa_planned_occurrence_scope", "organization_id", "association_id", "property_id"),
    )
