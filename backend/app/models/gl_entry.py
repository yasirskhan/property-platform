# ============================================================
# gl_entry.py
# ------------------------------------------------------------
# The child table of the General Ledger.
#
# One row per debit OR credit line. Every GLTransaction has at
# least two of these — the sum of debits equals the sum of
# credits for any given transaction_id. Enforced in
# app/services/gl_posting.py, not at the DB level.
#
# Rules:
#   * Exactly one of debit / credit is nonzero per row.
#   * Never both, never zero on both.
#   * For a transaction: SUM(debit) == SUM(credit).
#
# property_id, unit_id, and owner_id are optional. Company-wide
# entries (bank fees, inter-property transfers on the parent
# leg) leave them null. Property-scoped and owner-scoped reports
# filter on them.
#
# The owner_id tag is what powers the trust sub-ledger and the
# 3-way reconciliation (AppFolio parity).
# ============================================================

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class GLEntry(Base):
    __tablename__ = "gl_entries"

    id = Column(Integer, primary_key=True, index=True)

    # Duplicated from the parent transaction so ledger queries
    # don't have to join through gl_transactions for scope checks.
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    transaction_id = Column(
        Integer,
        ForeignKey("gl_transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    gl_account_id = Column(
        Integer,
        ForeignKey("gl_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

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
    )

    # ---------------- Owner scoping (AppFolio parity) ----------------
    # The owner this GL line economically belongs to. Nullable
    # because company-level entries (bank fees, transfers between
    # properties) have no owner. This is the tag that lets us
    # group GL activity by owner — the foundation of the trust
    # sub-ledger and the 3-way reconciliation.
    owner_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    description = Column(String(500), nullable=True)

    debit = Column(Numeric(12, 2), nullable=False, default=0)
    credit = Column(Numeric(12, 2), nullable=False, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    transaction = relationship("GLTransaction", back_populates="entries")
    gl_account = relationship("GLAccount")
    property = relationship("Property")
    unit = relationship("Unit")
    owner = relationship("User", foreign_keys=[owner_id])

    def __repr__(self) -> str:
        side = "DR" if (self.debit or 0) else "CR"
        amount = self.debit if (self.debit or 0) else self.credit
        return f"<GLEntry {self.gl_account_id} {side} {amount}>"