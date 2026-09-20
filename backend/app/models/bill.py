# ============================================================
# bill.py
# ------------------------------------------------------------
# Bills represent money going OUT to vendors and payees.
#
# Two-step accrual accounting (matches AppFolio):
#
#   1. Enter Bill    -> GL: DR Expense / CR Accounts Payable
#   2. Pay Bill      -> GL: DR Accounts Payable / CR Cash
#
# The bill stays "UNPAID" until it's paid. Then it's "PAID"
# (or "PARTIAL" if paid partially).
#
# Every bill posts through post_bill() in
# app/services/bill_posting.py, which calls post_transaction().
# Nothing writes to the GL directly.
#
# Rule: never edit or delete a posted bill. To undo, reverse it.
# Original stays, marked is_reversed=True, and a reversal
# transaction is posted. Net effect: zero.
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


class Bill(Base):
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Human-facing bill number, e.g. "B-0001" or vendor's
    # invoice #. Manager can override.
    bill_number = Column(String(40), nullable=True, index=True)

    # The payee (vendor name, company, or person). Free text
    # for now — Vendors become a real entity in Phase 4.
    payee_name = Column(String(200), nullable=False)

    # Optional link to a User if the payee happens to be one
    # (e.g. paying an owner, a manager, or a Vendor-type user).
    payee_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Business date of the bill (when it was incurred).
    bill_date = Column(Date, nullable=False, index=True)

    # When payment is due.
    due_date = Column(Date, nullable=True, index=True)

    # Vendor's invoice / reference number.
    reference_number = Column(String(60), nullable=True)

    # Total dollars owed. Must equal sum(bill_lines.amount).
    amount = Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))

    # How much has been paid so far. Updated by pay_bill().
    amount_paid = Column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )

    # UNPAID | PARTIAL | PAID | VOID
    status = Column(String(20), nullable=False, default="UNPAID", index=True)

    # Which property/unit this bill applies to (optional —
    # some bills are company-level).
    property_id = Column(
        Integer,
        ForeignKey("properties.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    unit_id = Column(
        Integer,
        ForeignKey("units.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # The AP account (usually 2100 Accounts Payable) used on
    # the credit side of the initial bill posting.
    payable_gl_account_id = Column(
        Integer,
        ForeignKey("gl_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Free-text remarks.
    remarks = Column(Text, nullable=True)

    # Link to the source if this bill was created from something
    # else (work order, project, recurring template, etc.).
    source_type = Column(String(40), nullable=True, index=True)
    source_id = Column(Integer, nullable=True)

    # ---------------- GL back-reference ----------------
    # The GL transaction created when the bill was entered.
    gl_transaction_id = Column(
        Integer,
        ForeignKey("gl_transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ---------------- Reversal bookkeeping ----------------
    is_reversed = Column(Boolean, nullable=False, default=False)
    reversal_of_id = Column(
        Integer,
        ForeignKey("bills.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ---------------- Universal patterns ----------------
    notes = Column(Text, nullable=True)
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
    payee_user = relationship("User", foreign_keys=[payee_user_id])
    payable_gl_account = relationship(
        "GLAccount", foreign_keys=[payable_gl_account_id]
    )
    property = relationship("Property")
    unit = relationship("Unit")
    gl_transaction = relationship("GLTransaction")
    reversal_of = relationship(
        "Bill",
        remote_side=[id],
        foreign_keys=[reversal_of_id],
    )
    created_by = relationship("User", foreign_keys=[created_by_id])
    lines = relationship(
        "BillLine",
        back_populates="bill",
        cascade="all, delete-orphan",
        order_by="BillLine.id",
    )

    def __repr__(self) -> str:
        return (
            f"<Bill {self.id} {self.payee_name} "
            f"{self.bill_date} {self.amount} {self.status}>"
        )