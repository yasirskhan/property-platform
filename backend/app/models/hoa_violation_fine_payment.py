"""Idempotent cash receipt allocation against one posted HOA violation fine."""
from datetime import date, datetime
from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from app.core.database import Base


class HOAViolationFinePayment(Base):
    __tablename__ = "hoa_violation_fine_payments"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    association_id = Column(Integer, ForeignKey("hoa_associations.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    fine_id = Column(Integer, ForeignKey("hoa_violation_fines.id"), nullable=False)
    member_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receipt_id = Column(Integer, ForeignKey("receipts.id"), nullable=False, unique=True)
    cash_gl_account_id = Column(Integer, ForeignKey("gl_accounts.id"), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    received_on = Column(Date, nullable=False)
    idempotency_key = Column(String(64), nullable=False)
    payment_reference = Column(String(60), nullable=False)
    status = Column(String(16), nullable=False, default="POSTED", server_default="POSTED")
    reversal_receipt_id = Column(Integer, ForeignKey("receipts.id"), unique=True)
    reversed_on = Column(Date)
    reversal_reason = Column(String(600))
    created_by_id = Column(Integer, ForeignKey("users.id"))
    reversed_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_hoa_fine_payment_request"),
        Index("ix_hoa_fine_payment_scope", "organization_id", "association_id", "property_id", "fine_id"),
    )
