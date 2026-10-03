"""Staff-prepared HOA meeting minutes, never legally certified minutes."""
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from app.core.database import Base


class HOAMeetingMinutesDraft(Base):
    __tablename__ = "hoa_meeting_minutes_drafts"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id = Column(Integer, ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    meeting_draft_id = Column(Integer, ForeignKey("hoa_meeting_drafts.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_minutes = Column(Text, nullable=False)
    revision = Column(Integer, nullable=False, default=1, server_default="1")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("meeting_draft_id", name="uq_hoa_minutes_per_meeting"),
        Index("ix_hoa_minutes_scope", "organization_id", "association_id", "property_id"),
    )

class HOAMeetingMinutesApproval(Base):
    """One final, immutable board-member approval of an exact minutes revision."""
    __tablename__ = "hoa_meeting_minutes_approvals"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    association_id = Column(Integer, ForeignKey("hoa_associations.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    meeting_draft_id = Column(Integer, ForeignKey("hoa_meeting_drafts.id"), nullable=False)
    minutes_draft_id = Column(Integer, ForeignKey("hoa_meeting_minutes_drafts.id"), nullable=False, unique=True)
    minutes_revision = Column(Integer, nullable=False)
    content_sha256 = Column(String(64), nullable=False)
    board_seat_id = Column(Integer, ForeignKey("hoa_board_seats.id"), nullable=False)
    approved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    approval_note = Column(Text, nullable=False)
    approved_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        Index("ix_hoa_minutes_approval_scope", "organization_id", "association_id", "property_id", "meeting_draft_id"),
    )
