"""Staff-recorded LIHTC building BINs, not agency allocation or Form 8609 filing."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from app.core.database import Base


class AffordableBuilding(Base):
    __tablename__ = "affordable_lihtc_buildings"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    program_id = Column(Integer, ForeignKey("affordable_programs.id", ondelete="CASCADE"), nullable=False, index=True)
    building_label = Column(String(100), nullable=False)
    agency_bin = Column(String(40), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    recorded_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "program_id", "agency_bin", name="uq_lihtc_building_bin"),
        Index("ix_lihtc_building_scope", "organization_id", "property_id", "program_id", "is_active"),
    )
