"""Read-only commercial lease staff-reference report.

A staff-entered rent commencement date is not an executed contractual
term, an invoice commencement instruction, an as-of lease snapshot, or
an authority to assess CAM, NNN or percentage rent.
"""
from __future__ import annotations

from typing import Mapping

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.commercial_lease_abstract import CommercialLeaseAbstract
from app.models.lease import Lease
from app.models.property import Property, PropertyAssignment, PropertyType, Unit
from app.models.user import User, UserRole
from app.routers.commercial_lease_abstracts import _property as visible_commercial_property
from app.services.customer_features import resolve_customer_features
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import ReportDeliveryError, ReportPayload, _int_param

REPORT_KEY = "commercial.lease_references"
HEADERS = (
    "Property", "Unit", "Lease ID", "Recorded Lease Start",
    "Recorded Lease End", "Recorded Lease Status",
    "Staff-Recorded Rent Commencement (UNVERIFIED)",
    "Reference Status", "Property ID", "Unit ID",
)


def build_commercial_lease_report(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"property_id"}:
        raise ReportDeliveryError("Unsupported commercial lease report parameter")
    property_id = _int_param(parameters, "property_id")

    role = current_user.role
    if (
        current_user.organization_id != organization_id
        or not current_user.is_active or current_user.deleted_at is not None
        or role not in {UserRole.ADMIN, UserRole.MANAGER}
    ):
        raise ReportDeliveryError("Commercial lease report permission required")
    for key in ("REPORTING.ALL", "PROPERTIES.ALL", "LEASING"):
        if not permission_allows_user(db, user=current_user, menu_key=key):
            raise ReportDeliveryError("Commercial lease report permission required")
    gate = next(
        (item for item in resolve_customer_features(db, user=current_user)
         if item.key == "release.properties.compliance"), None,
    )
    if gate is None or not gate.allowed:
        raise ReportDeliveryError("Commercial compliance feature unavailable")

    eligible = db.query(Property.id).filter(
        Property.organization_id == organization_id,
        Property.property_type == PropertyType.COMMERCIAL,
        Property.is_active.is_(True),
        Property.deleted_at.is_(None),
    )
    if role == UserRole.MANAGER:
        assigned = db.query(PropertyAssignment.property_id).filter(
            PropertyAssignment.user_id == current_user.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        eligible = eligible.filter(Property.id.in_(assigned))
    if property_id is not None:
        # Reuse the same exact property/role/gate/assignment boundary
        # as the verified property-level staff reference API.
        try:
            visible_commercial_property(db, property_id, current_user)
        except HTTPException as exc:
            if exc.status_code == 403:
                raise ReportDeliveryError("Commercial lease report permission required") from exc
            raise ReportDeliveryError("Commercial property not found") from exc
        eligible = eligible.filter(Property.id == property_id)

    rows = db.query(
        CommercialLeaseAbstract, Lease, Unit, Property,
    ).join(
        Lease, Lease.id == CommercialLeaseAbstract.lease_id,
    ).join(
        Unit, Unit.id == Lease.unit_id,
    ).join(
        Property, Property.id == Unit.property_id,
    ).join(
        User, User.id == Lease.tenant_id,
    ).filter(
        CommercialLeaseAbstract.organization_id == organization_id,
        CommercialLeaseAbstract.is_active.is_(True),
        Property.id.in_(eligible),
        Property.id == CommercialLeaseAbstract.property_id,
        Unit.is_active.is_(True), Unit.deleted_at.is_(None),
        User.organization_id == organization_id,
        User.role == UserRole.TENANT,
        User.is_active.is_(True), User.deleted_at.is_(None),
    ).order_by(
        Property.name, Property.id, Unit.unit_number, Lease.id,
    ).limit(5001).all()
    if len(rows) > 5000:
        raise ReportDeliveryError("Commercial reference report exceeds 5000 rows")

    return ReportPayload(
        title="Staff commercial lease commencement references (UNVERIFIED; NOT BILLING)",
        filename="commercial-lease-staff-references.csv",
        headers=HEADERS,
        rows=tuple(
            (
                prop.name, unit.unit_number, lease.id,
                lease.start_date, lease.end_date,
                lease.status.value if hasattr(lease.status, "value") else str(lease.status),
                row.rent_commencement_on.isoformat() if row.rent_commencement_on else "",
                "STAFF_RECORDED_UNVERIFIED", prop.id, unit.id,
            )
            for row, lease, unit, prop in rows
        ),
    )
