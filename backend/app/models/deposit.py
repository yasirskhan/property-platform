# ============================================================
# deposit.py
# ------------------------------------------------------------
# Bank Deposits group un-deposited receipts into one batch
# that goes to the bank together.
#
# IMPORTANT: In this system, receipts already credit the cash
# GL account at the moment they're posted (DR Cash / CR Income).
# Deposits therefore do NOT move cash between GL accounts —
# they simply TAG receipts as "deposited" for reconciliation.
# No GL transaction is created by post_deposit().
#
# If we later model "cash on hand" (undeposited funds) as a
# separate GL account, this is where a DR Bank / CR Cash on Hand
# posting would live.
#
# Rule: deposits cannot be reversed. Corrections go through a
# journal entry (Section 19).
# ============================================================

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Date,
    DateTime,
    Numeric,
    Text,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Deposit(Base):
    __tablename__ = "deposits"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Which GL cash account this deposit went into.
    # Usually 1150 Rental Trust.
    bank_gl_account_id = Column(
        Integer,
        ForeignKey("gl_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Date the deposit was made at the bank.
    deposit_date = Column(Date, nullable=False, index=True)

    # Human-facing deposit slip number / batch id.
    deposit_number = Column(String(40), nullable=True, index=True)

    # Free-text description shown on the deposit slip.
    description = Column(String(500), nullable=True)

    # Total dollars in this deposit. Always equals sum of
    # receipts attached.
    total = Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))

    # Free-text notes.
    notes = Column(Text, nullable=True)

    # ---------------- Universal patterns ----------------
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    created_by_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ---------------- Relationships ----------------
    organization = relationship("Organization")
    bank_gl_account = relationship(
        "GLAccount", foreign_keys=[bank_gl_account_id]
    )
    created_by = relationship("User", foreign_keys=[created_by_id])
    lines = relationship(
        "DepositLine",
        back_populates="deposit",
        cascade="all, delete-orphan",
        order_by="DepositLine.id",
    )

    def __repr__(self) -> str:
        return (
            f"<Deposit {self.id} {self.deposit_date} {self.total}>"
        )