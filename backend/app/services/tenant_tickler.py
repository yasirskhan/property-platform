"""Tenant contacts with the latest VERIFIABLY RECORDED lease event.

Tenant Tickler does not invent move-in, move-out or notice events from
contractual dates/status. It uses actual lease timestamps and, where
present, timestamped lease notes (without leaking the note text).
"""
from __future__ import annotations

from datetime import datetime
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.entity_note import EntityNote
from app.models.lease import Lease
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import User, UserRole
from app.services.report_delivery import ReportDeliveryError, ReportPayload, _int_param

HEADERS = (
    "Tenant ID", "Tenant", "Email", "Phone",
    "Property", "Unit", "Lease ID", "Lease Status",
    "Lease From", "Lease To", "Last Recorded Event",
    "Recorded At", "Property ID",
)


def _role(user: User) -> str:
    value = user.role.value if hasattr(user.role, "value") else user.role
    return str(value or "").upper()


def build_tenant_tickler(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    role = _role(current_user)
    if (current_user.organization_id != organization_id
            or not current_user.is_active or current_user.deleted_at is not None
            or role not in {"ADMIN", "MANAGER"}):
        raise ReportDeliveryError("Tenant tickler is not available to this user")
    if set(parameters) - {"property_id"}:
        raise ReportDeliveryError("Unsupported tenant tickler parameter")
    property_id = _int_param(parameters, "property_id")

    visible = db.query(Property.id).filter(
        Property.organization_id == organization_id,
        Property.is_active.is_(True),
        Property.deleted_at.is_(None),
    )
    if role == "MANAGER":
        assigned = db.query(PropertyAssignment.property_id).filter(
            PropertyAssignment.user_id == current_user.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        visible = visible.filter(Property.id.in_(assigned))
    if property_id is not None:
        visible = visible.filter(Property.id == property_id)
        if visible.first() is None:
            raise ReportDeliveryError("Property not found")

    associations = (
        db.query(User, Lease, Unit, Property)
        .join(Lease, Lease.tenant_id == User.id)
        .join(Unit, Unit.id == Lease.unit_id)
        .join(Property, Property.id == Unit.property_id)
        .filter(
            User.organization_id == organization_id,
            User.role == UserRole.TENANT,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
            Property.id.in_(visible),
            Unit.is_active.is_(True),
            Unit.deleted_at.is_(None),
        )
        .order_by(User.id.asc(), Lease.id.asc())
        .all()
    )
    lease_ids = [lease.id for _, lease, _, _ in associations]
    latest_note: dict[int, tuple[datetime, int]] = {}
    if lease_ids:
        notes = db.query(EntityNote).filter(
            EntityNote.organization_id == organization_id,
            EntityNote.entity_type == "leases",
            EntityNote.entity_id.in_(lease_ids),
        ).order_by(EntityNote.created_at.desc(), EntityNote.id.desc())
        for note in notes.all():
            latest_note.setdefault(note.entity_id, (note.created_at, note.id))

    # One contact row per tenant: latest timestamped event in the
    # currently authorized lease scope. Historical leases remain
    # eligible because an actual past event can be the most recent.
    entries: dict[int, tuple[datetime, int, tuple[object, ...]]] = {}
    for tenant, lease, unit, prop in associations:
        candidates: list[tuple[datetime, int, str]] = []
        if lease.created_at is not None:
            candidates.append((lease.created_at, 0, "Lease record created"))
        if lease.updated_at is not None and (
            lease.created_at is None or lease.updated_at > lease.created_at
        ):
            candidates.append((lease.updated_at, 1, "Lease record updated"))
        if lease.signed_at is not None:
            candidates.append((lease.signed_at, 2, "Lease signed"))
        if lease.id in latest_note:
            event_at, _ = latest_note[lease.id]
            candidates.append((event_at, 3, "Lease note recorded"))
        if not candidates:
            continue
        event_at, priority, event_name = max(candidates)
        row = (
            tenant.id, f"{tenant.first_name} {tenant.last_name}".strip(),
            tenant.email, tenant.phone or "", prop.name, unit.unit_number,
            lease.id, lease.status.value if hasattr(lease.status, "value") else str(lease.status),
            lease.start_date, lease.end_date,
            event_name, event_at.isoformat(sep=" ", timespec="seconds"),
            prop.id,
        )
        existing = entries.get(tenant.id)
        if existing is None or (event_at, priority, lease.id) > (
            existing[0], existing[1], int(existing[2][6])
        ):
            entries[tenant.id] = (event_at, priority, row)

    rows = [v[2] for v in entries.values()]
    if role == "ADMIN" and property_id is None:
        # Unassigned contacts are admin-only; don't infer events
        # from inaccessible/history-only property records.
        remaining = db.query(User).filter(
            User.organization_id == organization_id,
            User.role == UserRole.TENANT,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        ).order_by(User.id.asc())
        for tenant in remaining.all():
            if tenant.id in entries:
                continue
            rows.append((
                tenant.id, f"{tenant.first_name} {tenant.last_name}".strip(),
                tenant.email, tenant.phone or "", "", "", "", "", "", "",
                "No eligible recorded lease event", "", "",
            ))
    rows.sort(key=lambda row: (str(row[1]).casefold(), int(row[0])))
    return ReportPayload(
        title="Tenant Tickler — latest recorded lease activity",
        filename="tenant-tickler.csv",
        headers=HEADERS, rows=tuple(rows),
    )
