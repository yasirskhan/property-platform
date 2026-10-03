"""Association-authorized reserve book movements, separate from bank transfers."""
from datetime import datetime
from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from app.core.database import Base

class HOAReserveMovementDecision(Base):
    __tablename__ = "hoa_reserve_movement_decisions"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    association_id = Column(Integer, ForeignKey("hoa_associations.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    draft_id = Column(Integer, ForeignKey("hoa_reserve_movement_drafts.id"), unique=True, nullable=False)
    board_seat_id = Column(Integer, ForeignKey("hoa_board_seats.id"), nullable=False)
    maker_seat_id = Column(Integer, ForeignKey("hoa_board_seats.id"), nullable=False)
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    record_method = Column(String(16), nullable=False)
    supporting_attachment_id = Column(Integer, ForeignKey("entity_attachments.id"))
    decision = Column(String(16), nullable=False)
    decision_note = Column(Text, nullable=False)
    decided_on = Column(Date, nullable=False)
    approved_amount = Column(Numeric(14, 2))
    reserve_gl_account_id = Column(Integer, ForeignKey("gl_accounts.id"), nullable=False)
    counterparty_gl_account_id = Column(Integer, ForeignKey("gl_accounts.id"), nullable=False)
    direction = Column(String(16), nullable=False)
    status = Column(String(16), nullable=False)
    gl_transaction_id = Column(Integer, ForeignKey("gl_transactions.id"))
    reversal_transaction_id = Column(Integer, ForeignKey("gl_transactions.id"))
    posted_on = Column(Date)
    reversed_on = Column(Date)
    reversal_reason = Column(String(600))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (Index("ix_hoa_reserve_decision_scope", "organization_id", "association_id", "property_id"),)
