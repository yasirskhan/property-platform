"""Scheduled lease end dates from recorded contracts, not verified move-outs.

This is not a payment, GL, occupancy-as-of or renewal forecast. The summary
aggregates the same authorized detailed contract rows, without double counting.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.lease import Lease, LeaseStatus
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import User, UserRole
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import ReportDeliveryError, ReportPayload, _date_param, _int_param


DETAIL_HEADERS = (
    "Scheduled Contract End", "Property", "Unit", "Tenant",
    "Lease ID", "Tenant ID", "Recorded Lease Status",
    "Recorded Monthly Contract Rent", "Days Until Scheduled End",
    "Property ID", "Unit ID",
)
SUMMARY_HEADERS = (
    "Scheduled End Month", "Property", "Recorded Lease Endings",
    "Recorded Monthly Contract Rents (not revenue)", "Property ID",
)
DETAIL_KEY = "property.lease_expiration_detail"
SUMMARY_KEY = "property.lease_expiration_summary"


def _role(user: User) -> str:
    role = user.role.value if hasattr(user.role, "value") else user.role
    return str(role or "").upper()


def build_lease_expiration_report(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object], report_key: str,
) -> ReportPayload:
    if report_key not in (DETAIL_KEY, SUMMARY_KEY):
        raise ReportDeliveryError("Report not available")
    if set(parameters) - {"date_from", "date_to", "property_id"}:
        raise ReportDeliveryError("Unsupported lease expiration parameter")
    start = _date_param(parameters, "date_from")
    end = _date_param(parameters, "date_to")
    if start is None or end is None:
        raise ReportDeliveryError("date_from and date_to are required")
    if start > end or (end - start).days > 366 * 5:
        raise ReportDeliveryError("Invalid lease expiration date range")
    property_id = _int_param(parameters, "property_id")

    if (current_user.organization_id != organization_id
            or not current_user.is_active or current_user.deleted_at is not None
            or _role(current_user) not in {"ADMIN", "MANAGER"}):
        raise ReportDeliveryError("Lease expiration report permission required")
    for menu in ("REPORTING.ALL", "LEASING", "PROPERTIES.ALL"):
        if not permission_allows_user(db, user=current_user, menu_key=menu):
            raise ReportDeliveryError("Lease expiration report permission required")

    properties = db.query(Property.id).filter(
        Property.organization_id == organization_id,
        Property.is_active.is_(True),
        Property.deleted_at.is_(None),
    )
    if _role(current_user) == "MANAGER":
        assigned = db.query(PropertyAssignment.property_id).filter(
            PropertyAssignment.user_id == current_user.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        properties = properties.filter(Property.id.in_(assigned))
    if property_id is not None:
        properties = properties.filter(Property.id == property_id)
        if properties.first() is None:
            raise ReportDeliveryError("Property not found")

    # A historic EXPIRED status is allowed: it is a recorded contractual
    # expiry, not proof that anyone moved out or that an extension exists.
    rows = db.query(Lease, Unit, Property, User).join(
        Unit, Unit.id == Lease.unit_id,
    ).join(
        Property, Property.id == Unit.property_id,
    ).join(
        User, User.id == Lease.tenant_id,
    ).filter(
        Property.id.in_(properties),
        Unit.is_active.is_(True), Unit.deleted_at.is_(None),
        User.organization_id == organization_id,
        User.role == UserRole.TENANT,
        User.is_active.is_(True), User.deleted_at.is_(None),
        Lease.status.in_((LeaseStatus.ACTIVE, LeaseStatus.EXPIRED)),
        Lease.end_date >= start, Lease.end_date <= end,
    ).order_by(
        Lease.end_date.asc(), Property.name.asc(),
        Unit.unit_number.asc(), Lease.id.asc(),
    ).all()

    detail: list[tuple[object, ...]] = []
    for lease, unit, prop, tenant in rows:
        detail.append((
            lease.end_date, prop.name, unit.unit_number,
            f"{tenant.first_name} {tenant.last_name}".strip(),
            lease.id, tenant.id, lease.status.name,
            Decimal(lease.monthly_rent or 0).quantize(Decimal("0.01")),
            (lease.end_date - date.today()).days,
            prop.id, unit.id,
        ))
    if report_key == DETAIL_KEY:
        return ReportPayload(
            title=f"Scheduled lease expiration detail, {start} to {end} (contract dates only)",
            filename=f"lease-expiration-detail-{start}-{end}.csv",
            headers=DETAIL_HEADERS, rows=tuple(detail),
        )

    grouped: dict[tuple[str, int, str], tuple[int, Decimal]] = defaultdict(
        lambda: (0, Decimal("0.00"))
    )
    for row in detail:
        month = row[0].strftime("%Y-%m")
        prop_name, prop_id = row[1], row[9]
        key = (month, prop_id, prop_name)
        count, amount = grouped[key]
        grouped[key] = (count + 1, amount + row[7])
    summary = tuple(
        (month, prop_name, count, amount, prop_id)
        for (month, prop_id, prop_name), (count, amount)
        in sorted(grouped.items(), key=lambda item: item[0])
    )
    return ReportPayload(
        title=f"Scheduled lease expiration summary by month, {start} to {end}",
        filename=f"lease-expiration-summary-{start}-{end}.csv",
        headers=SUMMARY_HEADERS, rows=summary,
    )
