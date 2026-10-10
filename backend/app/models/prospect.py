"""Property-scoped leasing CRM lead; linked to existing address-book Contact."""
from datetime import datetime, date
from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, String, Boolean
from app.core.database import Base

class Prospect(Base):
    __tablename__ = "leasing_prospects"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="RESTRICT"), nullable=False, index=True)
    stage = Column(String(24), nullable=False, default="NEW")
    source = Column(String(60), nullable=False, default="OTHER")
    next_follow_up = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        Index("ix_leasing_prospects_org_property_stage", "organization_id", "property_id", "stage"),
    )
