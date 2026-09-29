"""Immutable individual authenticated board-member motion choices.

Separate from staff-reported ballot notes. A recorded choice is not an
automatically certified association resolution or quorum determination.
"""
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from app.core.database import Base


class HOABoardVote(Base):
    __tablename__ = "hoa_board_votes"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    association_id = Column(Integer, ForeignKey("hoa_associations.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    meeting_draft_id = Column(Integer, ForeignKey("hoa_meeting_drafts.id"), nullable=False)
    motion_draft_id = Column(Integer, ForeignKey("hoa_motion_drafts.id"), nullable=False)
    board_seat_id = Column(Integer, ForeignKey("hoa_board_seats.id"), nullable=False)
    voter_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    motion_sha256 = Column(String(64), nullable=False)
    choice = Column(String(12), nullable=False)
    voted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("motion_draft_id", "board_seat_id",
                         name="uq_hoa_board_vote_motion_seat"),
        Index("ix_hoa_board_vote_scope", "organization_id",
              "association_id", "property_id", "meeting_draft_id"),
    )
