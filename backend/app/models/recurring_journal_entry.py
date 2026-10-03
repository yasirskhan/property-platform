"""Recurring journal-entry templates and schedule state."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class RecurringJournalEntry(Base):
    __tablename__ = "recurring_journal_entries"
    __table_args__ = (
        Index(
            "ix_recurring_journal_entries_due",
            "organization_id",
            "is_active",
            "next_post_date",
        ),
    )

    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    day_of_month = Column(Integer, nullable=False)
    next_post_date = Column(Date, nullable=False, index=True)
    last_posted_date = Column(Date, nullable=True)
    reference_number = Column(String(60), nullable=True)
    memo = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_by_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    lines = relationship(
        "RecurringJournalEntryLine",
        back_populates="recurring_entry",
        cascade="all, delete-orphan",
        order_by="RecurringJournalEntryLine.id",
    )
    created_by = relationship("User", foreign_keys=[created_by_id])


class RecurringJournalEntryLine(Base):
    __tablename__ = "recurring_journal_entry_lines"

    id = Column(Integer, primary_key=True)
    recurring_journal_entry_id = Column(
        Integer,
        ForeignKey("recurring_journal_entries.id", ondelete="CASCADE"),
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
    owner_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    description = Column(String(500), nullable=True)
    debit = Column(Numeric(12, 2), nullable=False, default=0)
    credit = Column(Numeric(12, 2), nullable=False, default=0)

    recurring_entry = relationship("RecurringJournalEntry", back_populates="lines")
