"""Board-adopted HOA violation fine with central GL receivable posting."""
from datetime import date, datetime
from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from app.core.database import Base


class HOAViolationFine(Base):
    __tablename__ = "hoa_violation_fines"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    association_id = Column(Integer, ForeignKey("hoa_associations.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    case_id = Column(Integer, ForeignKey("hoa_violation_cases.id"), nullable=False, unique=True)
    service_record_id = Column(Integer, ForeignKey("hoa_violation_service_records.id"), nullable=False)
    hearing_record_id = Column(Integer, ForeignKey("hoa_violation_hearing_records.id"), nullable=True)
    board_seat_id = Column(Integer, ForeignKey("hoa_board_seats.id"), nullable=False)
    board_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    member_user_id = Column(Integer, ForeignKey("users.id"))
    contact_link_id = Column(Integer, ForeignKey("hoa_contact_links.id"))
    decision = Column(String(16), nullable=False)
    status = Column(String(16), nullable=False)
    amount = Column(Numeric(14, 2))
    amount_paid = Column(Numeric(14, 2), nullable=False, default=0, server_default="0.00")
    decision_note = Column(Text, nullable=False)
    hearing_disposition = Column(String(32), nullable=False)
    hearing_held_on = Column(Date)
    hearing_record_attachment_id = Column(Integer, ForeignKey("entity_attachments.id"))
    decided_on = Column(Date, nullable=False)
    decided_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    request_key = Column(String(64), nullable=False)
    policy_revision = Column(Integer, nullable=False)
    receivable_gl_account_id = Column(Integer, ForeignKey("gl_accounts.id"))
    income_gl_account_id = Column(Integer, ForeignKey("gl_accounts.id"))
    gl_transaction_id = Column(Integer, ForeignKey("gl_transactions.id"), unique=True)
    reversal_transaction_id = Column(Integer, ForeignKey("gl_transactions.id"), unique=True)
    posted_on = Column(Date)
    reversed_on = Column(Date)
    reversal_reason = Column(Text)
    __table_args__ = (
        UniqueConstraint("organization_id", "request_key", name="uq_hoa_violation_fine_request"),
        Index("ix_hoa_violation_fine_scope", "organization_id", "association_id", "property_id", "case_id"),
    )
