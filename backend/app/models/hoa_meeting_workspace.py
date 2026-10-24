"""Staff-reported meeting participation and proposed motions, never board certification."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from app.core.database import Base


class HOAMeetingParticipation(Base):
    __tablename__ = "hoa_meeting_participation"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id = Column(Integer, ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    meeting_draft_id = Column(Integer, ForeignKey("hoa_meeting_drafts.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_link_id = Column(Integer, ForeignKey("hoa_contact_links.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_attendance = Column(String(16), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("meeting_draft_id", "contact_link_id", name="uq_hoa_meeting_participation_contact"),
        Index("ix_hoa_participation_scope", "organization_id", "association_id", "property_id"),
    )


class HOAMotionDraft(Base):
    __tablename__ = "hoa_motion_drafts"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id = Column(Integer, ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    meeting_draft_id = Column(Integer, ForeignKey("hoa_meeting_drafts.id", ondelete="CASCADE"), nullable=False, index=True)
    proposed_motion = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        Index("ix_hoa_motion_scope", "organization_id", "association_id", "property_id"),
    )
