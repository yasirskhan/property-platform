"""Staff HOA review cases; no issued notice, assessed fine, legal ruling or charge."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from app.core.database import Base


class HOAViolationCase(Base):
    __tablename__ = "hoa_violation_cases"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id = Column(Integer, ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    observation_id = Column(Integer, ForeignKey("hoa_observations.id", ondelete="CASCADE"), nullable=False, index=True)
    stage = Column(String(32), nullable=False, default="OPEN", server_default="OPEN")
    draft_notice_on = Column(Date, nullable=True)
    tentative_cure_on = Column(Date, nullable=True)
    tentative_hearing_on = Column(Date, nullable=True)
    proposed_fine = Column(Numeric(14, 2), nullable=True)
    staff_resolution = Column(Text, nullable=True)
    policy_revision = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "observation_id", name="uq_hoa_case_org_observation"),
        Index("ix_hoa_case_scope", "organization_id", "association_id", "property_id", "stage"),
    )
