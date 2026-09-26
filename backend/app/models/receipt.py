# ============================================================
# receipt.py
# ------------------------------------------------------------
# Receipts represent money coming IN to the business.
#
# Three types (see type field below):
#   TENANT  - tenant pays rent/fees. Has receipt_lines that
#             break the payment across GL accounts.
#   OWNER   - owner sends money in (contribution / reserve).
#   OTHER   - anything else, with "exclude from mgmt fee"
#             option.
#
# Every receipt posts through post_receipt() in
# app/services/receipt_posting.py, which calls
# post_transaction(). Nothing writes to the GL directly.
#
# Rule: never edit or delete a posted receipt. To undo,
# reverse it. Original stays, marked is_reversed=True,
# and a reversal transaction is posted. Net effect: zero.
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


class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # TENANT | OWNER | OTHER
    type = Column(String(20), nullable=False, index=True)

    # Business date the money was received.
    receipt_date = Column(Date, nullable=False, index=True)

    # Total dollar amount of the receipt. Must equal the sum of
    # receipt_lines.amount_to_pay (for TENANT) or match the
    # single GL line (for OWNER/OTHER).
    amount = Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))

    # Cash side of the entry. Defaults to 1150 Rental Trust,
    # but a manager can override (e.g. deposit went straight to
    # the bank account).
    cash_gl_account_id = Column(
        Integer,
        ForeignKey("gl_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ---------------- TENANT fields ----------------
    tenant_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ---------------- Owner scoping (AppFolio parity) ----------------
    # The owner this receipt economically belongs to. Nullable
    # because company-level receipts (bank fees, misc) have no
    # owner, and multi-owner properties require explicit choice.
    # Used by the trust sub-ledger and the 3-way reconciliation.
    owner_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ---------------- OWNER receipt fields ----------------
    # (The "who paid" pointer for OWNER-type receipts. Distinct
    #  from owner_id, which is the economic scoping tag.)
    owner_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    income_gl_account_id = Column(
        Integer,
        ForeignKey("gl_accounts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    payer_name = Column(String(200), nullable=True)

    # ---------------- OTHER fields ----------------
    received_from = Column(String(200), nullable=True)
    exclude_from_mgmt_fee = Column(
        Boolean, nullable=False, default=False
    )

    # ---------------- Common fields ----------------
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

    reference_number = Column(String(60), nullable=True)
    remarks = Column(Text, nullable=True)

    # ---------------- GL back-reference ----------------
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
        ForeignKey("receipts.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ---------------- Universal patterns ----------------
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)

    created_by_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ---------------- Relationships ----------------
    organization = relationship("Organization")
    cash_gl_account = relationship(
        "GLAccount", foreign_keys=[cash_gl_account_id]
    )
    income_gl_account = relationship(
        "GLAccount", foreign_keys=[income_gl_account_id]
    )
    tenant = relationship("User", foreign_keys=[tenant_user_id])
    # Two distinct FKs to users:
    #   owner       -> owner_user_id  (the OWNER-receipt payer)
    #   scoped_owner-> owner_id       (economic owner for the GL)
    owner = relationship("User", foreign_keys=[owner_user_id])
    scoped_owner = relationship("User", foreign_keys=[owner_id])
    property = relationship("Property")
    unit = relationship("Unit")
    gl_transaction = relationship("GLTransaction")
    reversal_of = relationship(
        "Receipt",
        remote_side=[id],
        foreign_keys=[reversal_of_id],
    )
    created_by = relationship("User", foreign_keys=[created_by_id])
    lines = relationship(
        "ReceiptLine",
        back_populates="receipt",
        cascade="all, delete-orphan",
        order_by="ReceiptLine.id",
    )

    def __repr__(self) -> str:
        return (
            f"<Receipt {self.id} {self.type} "
            f"{self.receipt_date} {self.amount}>"
        )