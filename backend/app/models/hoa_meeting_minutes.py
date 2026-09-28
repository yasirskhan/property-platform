"""Staff-prepared HOA meeting minutes, never legally certified minutes."""
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint
from app.core.database import Base


class HOAMeetingMinutesDraft(Base):
    __tablename__ = "hoa_meeting_minutes_drafts"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id = Column(Integer, ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    meeting_draft_id = Column(Integer, ForeignKey("hoa_meeting_drafts.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_minutes = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("meeting_draft_id", name="uq_hoa_minutes_per_meeting"),
        Index("ix_hoa_minutes_scope", "organization_id", "association_id", "property_id"),
    )
