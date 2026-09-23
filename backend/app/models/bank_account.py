# ============================================================
# bank_account.py
# ------------------------------------------------------------
# Physical bank accounts mapped to GL cash accounts.
#
# AppFolio parity:
#   * Client Trust (OPERATING)  <-> GL 1150 Rental Trust
#   * Security Deposit Trust (ESCROW) <-> GL 1160 Security Deposit Cash
#
# Each org gets both accounts seeded by migration
# 7ca4251074bc_add_bank_accounts.
#
# Routing and account numbers are stored as strings (leading
# zeros matter). Encrypt at rest in Phase 11.
# ============================================================

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


# Allowed account types (matches AppFolio's two-account model)
BANK_ACCOUNT_TYPES = ("OPERATING", "ESCROW")

# ACH file formats
ACH_FORMATS = ("CSV", "NACHA")


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Display name ("Client Trust", "Security Deposit Trust")
    name = Column(String(120), nullable=False)

    bank_name = Column(String(200), nullable=True)
    routing_number = Column(String(20), nullable=True)
    account_number = Column(String(40), nullable=True)

    # The GL cash account this bank account maps to.
    # Usually 1150 or 1160.
    gl_account_id = Column(
        Integer,
        ForeignKey("gl_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # OPERATING | ESCROW
    account_type = Column(
        String(20), nullable=False, default="OPERATING"
    )

    # CSV | NACHA — set later when ACH is configured
    ach_format = Column(String(10), nullable=True)

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

    # Relationships
    organization = relationship("Organization")
    gl_account = relationship("GLAccount", foreign_keys=[gl_account_id])
    created_by = relationship("User", foreign_keys=[created_by_id])

    __table_args__ = (
        # A GL account maps to at most one bank account per org.
        UniqueConstraint(
            "organization_id",
            "gl_account_id",
            name="ux_bank_accounts_org_gl",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<BankAccount {self.id} {self.name} "
            f"({self.account_type}) -> GL {self.gl_account_id}>"
        )