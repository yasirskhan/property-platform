"""Durable owner payout drafts and externally-confirmed accounting records."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class OwnerPayout(Base):
    __tablename__ = "owner_payouts"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "batch_reference",
            "owner_id",
            name="uq_owner_payout_org_batch_owner",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_reference = Column(String(50), nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    bank_account_id = Column(Integer, ForeignKey("bank_accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    effective_date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(14, 2), nullable=False)
    destination_last4 = Column(String(4), nullable=False)
    status = Column(String(20), nullable=False, default="DRAFT", server_default="DRAFT", index=True)
    gl_transaction_id = Column(Integer, ForeignKey("gl_transactions.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    confirmed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)

    organization = relationship("Organization")
    owner = relationship("User", foreign_keys=[owner_id])
    bank_account = relationship("BankAccount")
    gl_transaction = relationship("GLTransaction")
    created_by = relationship("User", foreign_keys=[created_by_id])
    confirmed_by = relationship("User", foreign_keys=[confirmed_by_id])
