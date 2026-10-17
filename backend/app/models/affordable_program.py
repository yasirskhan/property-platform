"""Staff-recorded property program inventory, not an eligibility determination."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint

from app.core.database import Base


class AffordableProgram(Base):
    __tablename__ = "affordable_programs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    program_type = Column(String(32), nullable=False)
    label = Column(String(120), nullable=False)
    agency_name = Column(String(160), nullable=True)
    recorded_start = Column(Date, nullable=True)
    recorded_end = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "property_id", "label", name="uq_affordable_program_property_label"),
        Index("ix_affordable_program_scope", "organization_id", "property_id", "is_active"),
    )
