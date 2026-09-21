# ============================================================
# gl_account.py
# ------------------------------------------------------------
# General Ledger accounts (the Chart of Accounts).
#
# Every org gets the same 57 standard accounts seeded on
# creation. Orgs can add custom accounts, but the 57 are
# the baseline that every report and every transaction
# posting expects to exist.
#
# Fields:
#   gl_number              — e.g. "1150", "4100"
#   name                   — e.g. "Rental Trust", "Rent Income"
#   account_type           — ASSET | LIABILITY | EQUITY | INCOME | EXPENSE
#   sub_account_of         — optional FK to another gl_accounts.id
#                            (for nested accounts like 6171 Electric
#                            under a parent "Utilities" account)
#   offset_account         — GL number this account pairs with
#                            (bank reconciliation, clearing, etc.)
#   subject_to_mgmt_fees   — bool; used by the Management Fees engine
#                            in Phase 2 Step 9
#   include_on_cash_flow   — bool; used by Cash Flow reports
#   is_active              — soft delete (matches properties pattern)
#   deleted_at, deleted_by_id, delete_reason — soft-delete audit
# ============================================================

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


# ------------------------------------------------------------
# Account types (uppercase, matching role convention)
# ------------------------------------------------------------
ACCOUNT_TYPES = ("ASSET", "LIABILITY", "EQUITY", "INCOME", "EXPENSE")


class GLAccount(Base):
    __tablename__ = "gl_accounts"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # GL account number. Stored as string so leading zeros and
    # non-numeric codes are preserved.
    gl_number = Column(String(20), nullable=False, index=True)

    name = Column(String(255), nullable=False)

    # ASSET | LIABILITY | EQUITY | INCOME | EXPENSE
    account_type = Column(String(20), nullable=False, index=True)

    # Nested accounts: e.g. 6171 Electric could be a sub of 6100
    # Utilities. Nullable — most accounts are top-level.
    sub_account_of = Column(
        Integer,
        ForeignKey("gl_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Optional pairing to another GL number (bank reconciliation
    # uses this; the diagnostics engine uses it too).
    offset_account = Column(String(20), nullable=True)

    subject_to_mgmt_fees = Column(Boolean, nullable=False, default=False)
    include_on_cash_flow = Column(Boolean, nullable=False, default=True)
    
        # Diagnostics flag: accounts that must net to $0 after each
    # cycle (fee clearing accounts). Drives the "Positive Balance
    # on Fee GL Accounts" diagnostic.
    must_clear = Column(Boolean, nullable=False, default=False)

    # Soft delete (matches the properties pattern).
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    delete_reason = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    parent = relationship("GLAccount", remote_side=[id], backref="children")

    def __repr__(self) -> str:
        return f"<GLAccount {self.gl_number} {self.name} ({self.account_type})>"