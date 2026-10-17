"""Separate encrypted staff-held 8609 scans; NOT agency or IRS certification."""
from __future__ import annotations
from datetime import date, datetime
from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, LargeBinary

from app.core.database import Base


class Affordable8609Document(Base):
    __tablename__ = "affordable_lihtc_8609_documents"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    program_id = Column(Integer, ForeignKey("affordable_programs.id", ondelete="CASCADE"), nullable=False, index=True)
    building_id = Column(Integer, ForeignKey("affordable_lihtc_buildings.id", ondelete="CASCADE"), nullable=False, index=True)
    encrypted_pdf = Column(LargeBinary, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    received_on = Column(Date, nullable=False)
    uploaded_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_lihtc_8609_document_scope", "organization_id", "property_id", "program_id", "building_id"),
    )
