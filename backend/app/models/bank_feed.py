"""Durable provider-neutral bank-feed inbox for Phase 3.6.

Rows imported manually in Phase 3.6 and rows synchronized by a future provider
such as Plaid in Phase 8 share this table. Importing a feed row never writes to
the general ledger.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class BankFeedTransaction(Base):
    __tablename__ = "bank_feed_transactions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "bank_account_id",
            "import_key",
            name="uq_bank_feed_org_bank_import_key",
        ),
        UniqueConstraint(
            "bank_account_id",
            "matched_source_type",
            "matched_source_id",
            name="uq_bank_feed_bank_match",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bank_account_id = Column(
        Integer,
        ForeignKey("bank_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_provider = Column(
        String(40),
        nullable=False,
        default="CSV",
        server_default="CSV",
        index=True,
    )
    external_id = Column(String(200), nullable=True, index=True)
    import_key = Column(String(64), nullable=False, index=True)

    posted_date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(14, 2), nullable=False)
    payee = Column(String(300), nullable=True)
    description = Column(String(500), nullable=True)
    memo = Column(Text, nullable=True)
    reference_number = Column(String(100), nullable=True)

    status = Column(
        String(20),
        nullable=False,
        default="UNMATCHED",
        server_default="UNMATCHED",
        index=True,
    )
    matched_source_type = Column(String(30), nullable=True, index=True)
    matched_source_id = Column(Integer, nullable=True, index=True)

    created_by_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    bank_account = relationship("BankAccount")
    created_by = relationship("User", foreign_keys=[created_by_id])
