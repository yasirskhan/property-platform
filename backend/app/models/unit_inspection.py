"""Explicit staff-recorded unit inspections, NOT the Phase 5 mobile workflow."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, Index

from app.core.database import Base


class UnitInspectionRecord(Base):
    __tablename__ = "unit_inspection_records"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False, index=True)
    unit_id = Column(Integer, ForeignKey("units.id", ondelete="RESTRICT"), nullable=False, index=True)
    inspection_date = Column(Date, nullable=False, index=True)
    recorded_condition = Column(String(24), nullable=False)
    findings = Column(Text, nullable=False, default="")
    recorded_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_unit_inspections_org_property_date", "organization_id", "property_id", "inspection_date"),
    )
