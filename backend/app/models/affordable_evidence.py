"""Staff evidence-index readiness for a property program; never HUD/LIHTC certification."""
from __future__ import annotations

from datetime import date, datetime
from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from app.core.database import Base


class AffordableEvidence(Base):
    __tablename__ = "affordable_program_evidence"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    program_id = Column(Integer, ForeignKey("affordable_programs.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(40), nullable=False)
    status = Column(String(24), nullable=False, default="NOT_RECORDED")
    staff_follow_up_on = Column(Date, nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "program_id", "category", name="uq_affordable_evidence_category"),
        Index("ix_affordable_evidence_scope", "organization_id", "program_id"),
    )
