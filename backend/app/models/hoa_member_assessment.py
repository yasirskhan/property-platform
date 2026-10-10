"""Final association assessment decisions and real, member-scoped receivables.

Association board authority is recorded, not independently certified by
the platform. Financial posting requires live verified payer and GL checks.
"""
from datetime import datetime
from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from app.core.database import Base


class HOAAssessmentDecision(Base):
    __tablename__ = "hoa_assessment_decisions"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    association_id = Column(Integer, ForeignKey("hoa_associations.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    proposal_id = Column(Integer, ForeignKey("hoa_assessment_proposals.id"), nullable=False, unique=True)
    board_seat_id = Column(Integer, ForeignKey("hoa_board_seats.id"), nullable=False)
    board_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    decision = Column(String(16), nullable=False)
    decision_note = Column(Text, nullable=False)
    decided_on = Column(Date, nullable=False)
    decided_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    record_method = Column(String(16), nullable=False, default="DIRECT")
    supporting_attachment_id = Column(Integer, ForeignKey("entity_attachments.id"))
    decision_maker_seat_id = Column(Integer, ForeignKey("hoa_board_seats.id"))
    contact_link_id = Column(Integer, ForeignKey("hoa_contact_links.id"))
    member_user_id = Column(Integer, ForeignKey("users.id"))
    approved_amount = Column(Numeric(14, 2))
    proposal_revision_at = Column(DateTime, nullable=False)
    __table_args__ = (Index("ix_hoa_assessment_decision_scope", "organization_id", "association_id", "property_id"),)


class HOAMemberAssessmentCharge(Base):
    __tablename__ = "hoa_member_assessment_charges"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    association_id = Column(Integer, ForeignKey("hoa_associations.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    decision_id = Column(Integer, ForeignKey("hoa_assessment_decisions.id"), nullable=False)
    occurrence_id = Column(Integer, ForeignKey("hoa_planned_occurrences.id"), nullable=False, unique=True)
    member_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    contact_link_id = Column(Integer, ForeignKey("hoa_contact_links.id"), nullable=False)
    receivable_gl_account_id = Column(Integer, ForeignKey("gl_accounts.id"), nullable=False)
    income_gl_account_id = Column(Integer, ForeignKey("gl_accounts.id"), nullable=False)
    gl_transaction_id = Column(Integer, ForeignKey("gl_transactions.id"), nullable=False, unique=True)
    reversal_transaction_id = Column(Integer, ForeignKey("gl_transactions.id"), unique=True)
    amount = Column(Numeric(14, 2), nullable=False)
    amount_paid = Column(Numeric(14, 2), nullable=False, default=0, server_default="0.00")
    due_on = Column(Date, nullable=False)
    status = Column(String(16), nullable=False, default="OPEN", server_default="OPEN")
    reversal_reason = Column(Text)
    issued_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (Index("ix_hoa_member_assessment_scope", "organization_id", "association_id", "property_id", "member_user_id"),)
