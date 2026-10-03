"""Staff-reported ballot record, never an effective board vote or resolution."""
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from app.core.database import Base


class HOABallotRecord(Base):
    __tablename__ = "hoa_ballot_records"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id = Column(Integer, ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    meeting_draft_id = Column(Integer, ForeignKey("hoa_meeting_drafts.id", ondelete="CASCADE"), nullable=False, index=True)
    motion_draft_id = Column(Integer, ForeignKey("hoa_motion_drafts.id", ondelete="CASCADE"), nullable=False, index=True)
    board_seat_id = Column(Integer, ForeignKey("hoa_board_seats.id", ondelete="RESTRICT"), nullable=False, index=True)
    staff_reported_choice = Column(String(12), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("motion_draft_id", "board_seat_id", name="uq_hoa_ballot_motion_seat"),
        Index("ix_hoa_ballot_scope", "organization_id", "association_id", "property_id", "meeting_draft_id"),
    )
