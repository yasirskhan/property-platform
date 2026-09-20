# ============================================================
# gl_transaction.py
# ------------------------------------------------------------
# The parent table of the General Ledger.
#
# One row per financial event. Every receipt, bill, journal
# entry, deposit, management fee, owner draw, transfer, and
# reversal writes exactly one row here.
#
# The actual debit/credit lines live in GLEntry, linked by
# transaction_id. See app/models/gl_entry.py.
#
# Rule: never edit or delete a posted transaction. If it must
# be undone, post a new transaction that reverses it. See the
# is_reversed / reversal_of_id fields below.
# ============================================================

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Date,
    DateTime,
    Text,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class GLTransaction(Base):
    __tablename__ = "gl_transactions"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The business date the transaction occurred.
    transaction_date = Column(Date, nullable=False, index=True)

    # When the row was written to the system. Almost always
    # identical to transaction_date but can differ for
    # backdated entries.
    posted_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # RECEIPT | BILL | JOURNAL_ENTRY | DEPOSIT | MGMT_FEE |
    # OWNER_DRAW | TRANSFER | NSF | REVERSAL | ...
    transaction_type = Column(String(40), nullable=False, index=True)

    # Human-facing identifier: check #, receipt #, bill #, etc.
    reference_number = Column(String(40), nullable=True)

    # Whole-transaction remarks. Line-level notes live on GLEntry.
    memo = Column(Text, nullable=True)

    # What created this transaction — "receipt", "bill", etc.
    # Optional because manual journal entries have no external source.
    source_type = Column(String(40), nullable=True, index=True)
    source_id = Column(Integer, nullable=True)

    created_by_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Reversal bookkeeping. When a transaction is reversed, the
    # ORIGINAL gets is_reversed=True and the NEW transaction gets
    # reversal_of_id pointing at the original.
    is_reversed = Column(Boolean, nullable=False, default=False)
    reversal_of_id = Column(
        Integer,
        ForeignKey("gl_transactions.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    created_by = relationship("User", foreign_keys=[created_by_id])
    entries = relationship(
        "GLEntry",
        back_populates="transaction",
        cascade="all, delete-orphan",
        order_by="GLEntry.id",
    )
    reversal_of = relationship(
        "GLTransaction",
        remote_side=[id],
        foreign_keys=[reversal_of_id],
    )

    def __repr__(self) -> str:
        return (
            f"<GLTransaction {self.id} {self.transaction_type} "
            f"{self.transaction_date}>"
        )