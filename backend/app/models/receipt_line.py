# ============================================================
# receipt_line.py
# ------------------------------------------------------------
# One line of a Receipt.
#
# For TENANT receipts, each line is "tenant is paying $X toward
# GL account Y" (rent, late fee, pet fee, etc.). The charges
# table on the New Receipt screen builds these.
#
# For OWNER and OTHER receipts, there is usually exactly one
# line, and it's the non-cash side (Owner Funds for OWNER, or
# the income account the manager picked for OTHER).
#
# The sum of amount_to_pay across all lines equals
# Receipt.amount. Every line carries gl_account_id so the
# posting service knows exactly where to route the credit
# (or debit) side of the GL entry.
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


class ReceiptLine(Base):
    __tablename__ = "receipt_lines"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    receipt_id = Column(
        Integer,
        ForeignKey("receipts.id", ondelete="CASCADE"),
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
        index=True,
    )

    description = Column(String(500), nullable=True)

    amount_to_pay = Column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )

    line_date = Column(Date, nullable=True)

    is_prepayment = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ---------------- Relationships ----------------
    organization = relationship("Organization")
    receipt = relationship("Receipt", back_populates="lines")
    gl_account = relationship("GLAccount")
    property = relationship("Property")
    unit = relationship("Unit")

    def __repr__(self) -> str:
        return (
            f"<ReceiptLine {self.id} receipt={self.receipt_id} "
            f"acct={self.gl_account_id} {self.amount_to_pay}>"
        )