"""Read-only current-config GPR projection and separate posted journal markers.

The original posting logic derives candidate amounts from CURRENT editable
Unit and Lease fields, even for older months. This report does not claim those
values are historical frozen amounts, nor does it call post_gpr.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.gl_transaction import GLTransaction
from app.models.property import Unit
from app.models.user import User
from app.services.gpr_posting import _active_lease_for_month, month_bounds
from app.services.gl_posting import PostingError
from app.services.menu_resolver import permission_allows_user
from app.services.property_budgets import visible_budget_property
from app.services.report_delivery import (
    ReportDeliveryError, ReportPayload, _date_param, _int_param,
)


HEADERS = (
    "Property", "Unit", "Reporting Month", "Occupancy in Month",
    "Current Config Market Rent", "Current Config Scheduled Rent",
    "Current Config Loss / Gain", "Lease ID (Current Config)",
    "GPR Journal Marker", "Original GPR Transaction ID",
    "Reversal Transaction ID", "Property ID", "Unit ID",
)


def build_gpr_report(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"property_id", "month"}:
        raise ReportDeliveryError("Unsupported GPR report parameter")
    property_id = _int_param(parameters, "property_id", required=True)
    month = _date_param(parameters, "month")
    if month is None:
        raise ReportDeliveryError("month is required")
    if not 2000 <= month.year <= 2100:
        raise ReportDeliveryError("GPR reporting month is out of range")
    assert property_id is not None

    # AUTHORIZE property scope and the lease/journal disclosures BEFORE
    # evaluating candidate leases or reading any source journal rows.
    prop = visible_budget_property(
        db, organization_id=organization_id,
        current_user=current_user, property_id=property_id,
    )
    for key in ("LEASING", "ACCOUNTING.JOURNAL_ENTRIES"):
        if not permission_allows_user(db, user=current_user, menu_key=key):
            raise ReportDeliveryError("GPR report permission required")
    start, end = month_bounds(month)
    units = db.query(Unit).filter(
        Unit.property_id == prop.id,
        Unit.is_active.is_(True),
        Unit.deleted_at.is_(None),
        Unit.monthly_rent > 0,
    ).order_by(Unit.unit_number.asc(), Unit.id.asc()).all()

    originals = db.query(GLTransaction).filter(
        GLTransaction.organization_id == organization_id,
        GLTransaction.source_type == "gpr",
        GLTransaction.transaction_type == "JOURNAL_ENTRY",
        GLTransaction.transaction_date == start,
        GLTransaction.source_id.in_([u.id for u in units]),
    ).order_by(GLTransaction.id.desc()).all() if units else []
    by_unit: dict[int, list[GLTransaction]] = {}
    for txn in originals:
        if txn.source_id is not None:
            by_unit.setdefault(txn.source_id, []).append(txn)
    original_ids = [txn.id for txn in originals]
    reversals = db.query(GLTransaction).filter(
        GLTransaction.organization_id == organization_id,
        GLTransaction.reversal_of_id.in_(original_ids),
        GLTransaction.transaction_type == "REVERSAL",
    ).order_by(GLTransaction.id.desc()).all() if original_ids else []
    reversed_by_original: dict[int, int] = {}
    for txn in reversals:
        if txn.reversal_of_id is not None:
            reversed_by_original.setdefault(txn.reversal_of_id, txn.id)

    result: list[tuple[object, ...]] = []
    for unit in units:
        try:
            lease = _active_lease_for_month(
                db, unit_id=unit.id, month_start=start, month_end=end,
            )
        except PostingError as exc:
            # Do not silently select one of several conflicting active leases.
            raise ReportDeliveryError(str(exc)) from exc
        market = Decimal(unit.monthly_rent or 0).quantize(Decimal("0.01"))
        scheduled = Decimal(lease.monthly_rent if lease else 0).quantize(Decimal("0.01"))
        booked = by_unit.get(unit.id, [])
        current_post = next((txn for txn in booked if not txn.is_reversed), None)
        original = current_post or (booked[0] if booked else None)
        if current_post is not None:
            marker = "POSTED (journal marker, not current-config amount)"
        elif original is not None:
            marker = "REVERSED (journal marker, not current-config amount)"
        else:
            marker = "NOT POSTED"
        result.append((
            prop.name, unit.unit_number, start.isoformat(),
            "LEASED" if lease else "VACANT",
            market, scheduled, (market - scheduled).quantize(Decimal("0.01")),
            lease.id if lease else "",
            marker, original.id if original else "",
            reversed_by_original.get(original.id, "") if original else "",
            prop.id, unit.id,
        ))
    return ReportPayload(
        title=f"Gross potential rent projection, {prop.name}, {start:%Y-%m} "
              "(current unit/lease configuration; journal markers separate)",
        filename=f"gross-potential-rent-{property_id}-{start:%Y-%m}.csv",
        headers=HEADERS, rows=tuple(result),
    )
