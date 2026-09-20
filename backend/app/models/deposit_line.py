# ============================================================
# deposit_line.py
# ------------------------------------------------------------
# One line of a Deposit: a link to one Receipt that is part of
# this deposit batch.
#
# A deposit can contain many receipts (deposit_lines -> receipts).
# A receipt belongs to AT MOST ONE deposit (via receipts.deposit_id).
#
# No money amounts are stored here — the deposit's total is
# the sum of its receipts, and each receipt already has its
# own GL posting. deposit_lines is purely a grouping table.
# ============================================================

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class DepositLine(Base):
    __tablename__ = "deposit_lines"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    deposit_id = Column(
        Integer,
        ForeignKey("deposits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    receipt_id = Column(
        Integer,
        ForeignKey("receipts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    created_at = Column(DateTime, default=datetime.utcnow)

    # ---------------- Relationships ----------------
    organization = relationship("Organization")
    deposit = relationship("Deposit", back_populates="lines")
    receipt = relationship("Receipt")

    def __repr__(self) -> str:
        return (
            f"<DepositLine {self.id} deposit={self.deposit_id} "
            f"receipt={self.receipt_id}>"
        )