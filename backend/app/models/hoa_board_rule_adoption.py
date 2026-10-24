"""Immutable association-member adoption of explicitly configured voting rules."""
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from app.core.database import Base


class HOABoardRuleAdoption(Base):
    __tablename__ = "hoa_board_rule_adoptions"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    association_id = Column(Integer, ForeignKey("hoa_associations.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    rule_draft_id = Column(Integer, ForeignKey("hoa_board_rule_drafts.id"), nullable=False)
    proposal_sha256 = Column(String(64), nullable=False)
    quorum_min = Column(Integer, nullable=False)
    approval_min = Column(Integer, nullable=False)
    board_seat_id = Column(Integer, ForeignKey("hoa_board_seats.id"), nullable=False)
    adopted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    adopted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("rule_draft_id", "proposal_sha256", name="uq_hoa_board_rule_adoption_revision"),
        Index("ix_hoa_board_rule_adoption_scope", "organization_id", "association_id", "property_id"),
    )
