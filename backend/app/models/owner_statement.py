# ============================================================
# owner_statement.py
# ------------------------------------------------------------
# A frozen snapshot of an owner's statement for a period.
#
# AppFolio parity:
#   * One row per owner per period generated
#   * Per-property breakdown stored as JSON in `property_data`
#   * Once generated, the numbers never change — later GL
#     corrections don't rewrite the statement the owner was
#     sent.
#
# property_data JSON shape (array):
#   [
#     {
#       "property_id": int,
#       "property_name": str,
#       "ownership_pct": float,
#       "beginning_cash": str,   # Decimal as string
#       "ending_cash": str,
#       "income": str,
#       "expense": str,
#       "net": str,
#       "transactions": [
#         {
#           "date": "YYYY-MM-DD",
#           "description": str,
#           "reference": str | null,
#           "income": str,
#           "expense": str,
#           "running_balance": str,
#           "gl_transaction_id": int,
#         },
#         ...
#       ]
#     },
#     ...
#   ]
# ============================================================

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

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


class OwnerStatement(Base):
    __tablename__ = "owner_statements"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    owner_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Period covered (inclusive)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    generated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Snapshot totals across all properties this owner has a stake in
    total_beginning_cash = Column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    total_ending_cash = Column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    total_income = Column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    total_expense = Column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    total_net = Column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )

    # JSON blob — see docstring at top of file for shape
    property_data = Column(Text, nullable=False, default="[]")

    # Optional generated PDF
    pdf_url = Column(String(500), nullable=True)

    notes = Column(Text, nullable=True)

    is_active = Column(Boolean, nullable=False, default=True, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)

    generated_by_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    owner = relationship("User", foreign_keys=[owner_id])
    generated_by = relationship("User", foreign_keys=[generated_by_id])

    def __repr__(self) -> str:
        return (
            f"<OwnerStatement {self.id} owner={self.owner_id} "
            f"{self.period_start}..{self.period_end}>"
        )