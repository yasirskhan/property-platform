"""Staff annual Form 8609-A reference index; not a filed statement or credit."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from app.core.database import Base


class Affordable8609Annual(Base):
    __tablename__ = "affordable_lihtc_8609_annual"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    program_id = Column(Integer, ForeignKey("affordable_programs.id", ondelete="CASCADE"), nullable=False, index=True)
    building_id = Column(Integer, ForeignKey("affordable_lihtc_buildings.id", ondelete="CASCADE"), nullable=False, index=True)
    tax_year = Column(Integer, nullable=False)
    allocation_category = Column(String(32), nullable=False)
    status = Column(String(24), nullable=False, default="NOT_RECORDED")
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "building_id", "tax_year", "allocation_category",
                         name="uq_lihtc_8609_annual_reference"),
        Index("ix_lihtc_8609_annual_scope",
              "organization_id", "property_id", "program_id", "building_id", "tax_year"),
    )
