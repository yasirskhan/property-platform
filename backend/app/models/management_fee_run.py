# ============================================================
# management_fee_run.py
# ------------------------------------------------------------
# Records one management fee posting.
#
# AppFolio parity:
#   * One row per property per fee period
#   * Computed from ELIGIBLE income only (GL accounts flagged
#     `subject_to_mgmt_fees = True`)
#   * Percentage applied to rent income (4100/4105)
#   * 100% of additional fee income (4416, 4420, 4430, etc.)
#   * Respects `exclude_from_mgmt_fee` on receipts
#   * Honors `mgmt_fee_end_date` (no fees after this date)
#
# GL posting (one transaction per run):
#   DR 6001 Management Fees
#   CR 1150 Rental Trust
#
# Rule: never edit or delete a posted run. To undo, reverse it.
# Original stays, is_reversed=True, and a reversal is posted.
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
    Text,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class ManagementFeeRun(Base):
    __tablename__ = "management_fee_runs"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    property_id = Column(
        Integer,
        ForeignKey("properties.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Fee period this run covers (inclusive dates).
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    # Eligible income totals used in the calculation.
    rent_income_total = Column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    other_fee_income_total = Column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )

    # Percentages used at the time of the run (snapshot — so a
    # later change to property.mgmt_fee_pct doesn't rewrite history).
    rent_fee_pct = Column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )
    other_fee_pct = Column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )

    # Computed fee amounts.
    rent_fee_amount = Column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    other_fee_amount = Column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    total_fee = Column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )

    # Which GL accounts were used.
    expense_gl_account_id = Column(
        Integer,
        ForeignKey("gl_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cash_gl_account_id = Column(
        Integer,
        ForeignKey("gl_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # GL transaction created by this run.
    gl_transaction_id = Column(
        Integer,
        ForeignKey("gl_transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    notes = Column(Text, nullable=True)

    # Reversal bookkeeping.
    is_reversed = Column(Boolean, nullable=False, default=False)
    reversal_of_id = Column(
        Integer,
        ForeignKey("management_fee_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Universal patterns.
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    created_by_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships.
    organization = relationship("Organization")
    property = relationship("Property")
    expense_gl_account = relationship(
        "GLAccount", foreign_keys=[expense_gl_account_id]
    )
    cash_gl_account = relationship(
        "GLAccount", foreign_keys=[cash_gl_account_id]
    )
    gl_transaction = relationship("GLTransaction")
    reversal_of = relationship(
        "ManagementFeeRun",
        remote_side=[id],
        foreign_keys=[reversal_of_id],
    )
    created_by = relationship("User", foreign_keys=[created_by_id])

    def __repr__(self) -> str:
        return (
            f"<ManagementFeeRun {self.id} property={self.property_id} "
            f"{self.period_start}..{self.period_end} total={self.total_fee}>"
        )