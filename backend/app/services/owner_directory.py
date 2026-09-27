"""Read-only organization-scoped owner contact directory.

Owner users see only themselves. Managers with explicit owner-directory
permission see only owners attached to currently assigned live properties.
No taxpayer profiles, banking or invented mailing addresses are read.
"""
from __future__ import annotations

from typing import Mapping

from sqlalchemy.orm import Session

from app.models.property import Property, PropertyAssignment, PropertyOwner
from app.models.user import User, UserRole
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import ReportDeliveryError, ReportPayload


HEADERS = ("Owner ID", "Recorded Name", "Email", "Phone (recorded)")


def _role(actor: User) -> str:
    role = actor.role.value if hasattr(actor.role, "value") else actor.role
    return str(role or "").upper()


def build_owner_directory(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if parameters:
        raise ReportDeliveryError("Unsupported owner directory parameter")
    role = _role(current_user)
    if (current_user.organization_id != organization_id
            or not current_user.is_active or current_user.deleted_at is not None
            or role not in {"ADMIN", "MANAGER", "OWNER"}):
        raise ReportDeliveryError("Owner directory permission required")
    for menu_key in ("REPORTING.ALL", "PEOPLE.OWNERS"):
        if not permission_allows_user(db, user=current_user, menu_key=menu_key):
            raise ReportDeliveryError("Owner directory permission required")

    visible = db.query(User).filter(
        User.organization_id == organization_id,
        User.role == UserRole.OWNER,
        User.is_active.is_(True),
        User.deleted_at.is_(None),
    )
    if role == "OWNER":
        visible = visible.filter(User.id == current_user.id)
    if role == "MANAGER":
        if not permission_allows_user(db, user=current_user, menu_key="PROPERTIES.ALL"):
            raise ReportDeliveryError("Owner directory permission required")
        managed_owners = (
            db.query(PropertyOwner.user_id)
            .join(Property, Property.id == PropertyOwner.property_id)
            .join(PropertyAssignment, PropertyAssignment.property_id == Property.id)
            .filter(
                PropertyOwner.organization_id == organization_id,
                PropertyOwner.is_active.is_(True),
                PropertyOwner.deleted_at.is_(None),
                Property.organization_id == organization_id,
                Property.is_active.is_(True),
                Property.deleted_at.is_(None),
                PropertyAssignment.user_id == current_user.id,
                PropertyAssignment.is_active.is_(True),
                PropertyAssignment.deleted_at.is_(None),
            )
        )
        visible = visible.filter(User.id.in_(managed_owners))
    owners = visible.order_by(User.last_name.asc(), User.first_name.asc(), User.id.asc()).all()
    rows = tuple((
        person.id,
        f"{person.first_name} {person.last_name}".strip(),
        person.email,
        person.phone or "",
    ) for person in owners)
    return ReportPayload(
        title="Current recorded owner contacts (no mailing addresses or taxpayer identifiers)",
        filename="owner-contact-directory.csv", headers=HEADERS, rows=rows,
    )
