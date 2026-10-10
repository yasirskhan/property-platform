"""Immutable association-authorized outcome of an exact recorded motion tally."""
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from app.core.database import Base


class HOABoardMotionOutcome(Base):
    __tablename__ = "hoa_board_motion_outcomes"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    association_id = Column(Integer, ForeignKey("hoa_associations.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    meeting_draft_id = Column(Integer, ForeignKey("hoa_meeting_drafts.id"), nullable=False)
    motion_draft_id = Column(Integer, ForeignKey("hoa_motion_drafts.id"), nullable=False, unique=True)
    motion_sha256 = Column(String(64), nullable=False)
    rule_adoption_id = Column(Integer, ForeignKey("hoa_board_rule_adoptions.id"), nullable=False)
    vote_register_sha256 = Column(String(64), nullable=False)
    quorum_min = Column(Integer, nullable=False)
    approval_min = Column(Integer, nullable=False)
    votes_for = Column(Integer, nullable=False)
    votes_against = Column(Integer, nullable=False)
    votes_abstain = Column(Integer, nullable=False)
    outcome = Column(String(16), nullable=False)
    recorded_by_seat_id = Column(Integer, ForeignKey("hoa_board_seats.id"), nullable=False)
    recorded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        Index("ix_hoa_motion_outcome_scope", "organization_id", "association_id",
              "property_id", "meeting_draft_id"),
    )
