"""Staff-recorded prospect interest; never an ordered/official assistance waitlist."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, UniqueConstraint

from app.core.database import Base


class AffordableInterest(Base):
    __tablename__ = "affordable_program_interests"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    program_id = Column(Integer, ForeignKey("affordable_programs.id", ondelete="CASCADE"), nullable=False, index=True)
    prospect_id = Column(Integer, ForeignKey("leasing_prospects.id", ondelete="RESTRICT"), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    recorded_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "program_id", "prospect_id", name="uq_affordable_interest_org_program_prospect"),
        Index("ix_affordable_interest_org_program_active", "organization_id", "program_id", "is_active"),
    )
