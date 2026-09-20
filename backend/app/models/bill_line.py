# ============================================================
# bill_line.py
# ------------------------------------------------------------
# One line of a Bill.
#
# Each line is one expense on the bill: which GL account,
# what it was for, and how much. The sum of amount across all
# lines equals Bill.amount.
#
# For a simple bill ("$500 plumber"), there's exactly one line:
#   6852 Plumbing | Fix kitchen sink | 500.00
#
# For a complex bill, there can be several: e.g. one vendor
# invoice covering landscaping + irrigation + mulch.
#
# Every line carries gl_account_id so the posting service
# knows which expense account to debit.
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
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class BillLine(Base):
    __tablename__ = "bill_lines"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    bill_id = Column(
        Integer,
        ForeignKey("bills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Which GL account this line posts to. Usually an EXPENSE
    # account (6xxx or 8xxx), but can be any account (e.g. an
    # asset purchase hitting 1710 Buildings).
    gl_account_id = Column(
        Integer,
        ForeignKey("gl_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Property/unit for this specific line. Usually inherited
    # from the parent Bill, but kept here because post_transaction()
    # places property/unit on each line, and a bill can span
    # properties (rare but legal).
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

    # Free-text description shown on the bill and in the GL
    # entry: "Fix kitchen sink", "March landscaping", etc.
    description = Column(String(500), nullable=True)

    # The amount of this line, in dollars. Always positive.
    amount = Column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ---------------- Relationships ----------------
    organization = relationship("Organization")
    bill = relationship("Bill", back_populates="lines")
    gl_account = relationship("GLAccount")
    property = relationship("Property")
    unit = relationship("Unit")

    def __repr__(self) -> str:
        return (
            f"<BillLine {self.id} bill={self.bill_id} "
            f"acct={self.gl_account_id} {self.amount}>"
        )