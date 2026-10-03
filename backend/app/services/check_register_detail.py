"""Recorded allocation detail for posted issued/void checks.

Reuse the verified Check Register for org/role/menu, bank mappings and
original/void GL markers. Allocation rows are recorded allocations, not
independent evidence of bank clearance or historic bill balances.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.bill import Bill
from app.models.check import Check, CheckBillAllocation
from app.models.user import User
from app.services.check_register_report import build_check_register
from app.services.report_delivery import ReportDeliveryError, ReportPayload

HEADERS = (
    "Row Kind", "Check ID", "Check Date", "Check Number",
    "Recorded Status", "Recorded Payee", "Bank Display Name",
    "Nominal Check Amount", "Bill ID", "Bill Number",
    "Recorded Allocation Amount", "Original Check GL ID", "Void GL ID",
)
CENT = Decimal("0.01")


def build_check_register_detail(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    """Fail closed on cross-org allocations and mismatched check totals."""
    verified = build_check_register(
        db, organization_id=organization_id, current_user=current_user,
        parameters=parameters,
    )
    rows: list[tuple[object, ...]] = []
    for line in verified.rows:
        check_id = int(line[0])
        # Verified summary fields are safe; never read bank routing/account.
        check = db.query(Check).filter(
            Check.id == check_id, Check.organization_id == organization_id,
        ).first()
        if check is None:
            raise ReportDeliveryError("Check not found")
        allocations = (
            db.query(CheckBillAllocation)
            .filter(CheckBillAllocation.check_id == check_id)
            .order_by(CheckBillAllocation.id.asc())
            .all()
        )
        if not allocations:
            raise ReportDeliveryError("Check has no recorded bill allocations")
        total = Decimal("0")
        detail: list[tuple[object, ...]] = []
        for allocation in allocations:
            amount = Decimal(allocation.amount or 0)
            if amount <= 0 or amount.as_tuple().exponent < -2:
                raise ReportDeliveryError("Invalid recorded check allocation")
            bill = db.query(Bill).filter(
                Bill.id == allocation.bill_id,
                Bill.organization_id == organization_id,
            ).first()
            if bill is None:
                raise ReportDeliveryError("Check allocation bill needs review")
            total += amount
            detail.append((
                "ALLOCATION", check_id, "", "", "", "", "", "",
                bill.id, bill.bill_number or "", amount, "", "",
            ))
        nominal = Decimal(check.amount or 0)
        if nominal <= 0 or total.quantize(CENT) != nominal.quantize(CENT):
            raise ReportDeliveryError("Check and allocation totals disagree")
        rows.append((
            "CHECK", check_id, line[1], line[2], line[5],
            line[3], line[4], nominal, "", "", "",
            line[7], line[8],
        ))
        rows.extend(detail)
        if len(rows) > 5000:
            raise ReportDeliveryError("Narrow Check Register Detail filters before exporting")
    return ReportPayload(
        title=(
            "Recorded check allocation detail; original GL issue/void markers, "
            "NOT cleared bank payments or historical bill balances"
        ),
        filename="recorded-check-register-detail.csv",
        headers=HEADERS, rows=tuple(rows),
    )
