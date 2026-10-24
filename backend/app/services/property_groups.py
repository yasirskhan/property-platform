"""Authorization, CRUD and report for actual named property memberships.

The group setting's existing hybrid feature decision is authoritative:
platform release, commercial entitlement, organization configuration and
menu permission must ALL pass. Listing managers sees only assigned members.
"""
from __future__ import annotations

from typing import Mapping

from sqlalchemy.orm import Session

from app.models.property import Property, PropertyAssignment
from app.models.property_group import PropertyGroup, PropertyGroupMembership
from app.models.user import User
from app.schemas.property_group import PropertyGroupOut, PropertyGroupUpsertIn
from app.services.audit import append_audit_log
from app.services.customer_features import resolve_customer_features
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import ReportDeliveryError, ReportPayload, _int_param


GROUP_FEATURE = "release.properties.groups"
HEADERS = (
    "Group", "Description", "Property", "Address",
    "City", "State", "Postal Code", "Country",
    "Group ID", "Property ID",
)


def _role(user: User) -> str:
    value = user.role.value if hasattr(user.role, "value") else user.role
    return str(value or "").upper()


def require_groups_access(db: Session, *, actor: User, write: bool = False) -> int:
    if (actor.organization_id is None or not actor.is_active
            or actor.deleted_at is not None
            or _role(actor) not in {"ADMIN", "MANAGER"}
            or (write and _role(actor) != "ADMIN")):
        raise ReportDeliveryError("Property group permission required")
    for permission in ("PROPERTIES.ALL", "PROPERTIES.GROUPS"):
        if not permission_allows_user(db, user=actor, menu_key=permission):
            raise ReportDeliveryError("Property group permission required")
    if write and not permission_allows_user(db, user=actor, menu_key="SETTINGS"):
        raise ReportDeliveryError("Property group permission required")
    decision = next((
        item for item in resolve_customer_features(db, user=actor)
        if item.key == GROUP_FEATURE
    ), None)
    if decision is None or not decision.allowed:
        raise ReportDeliveryError("Property groups are not enabled")
    return int(actor.organization_id)


def _visible(db: Session, *, org_id: int, actor: User):
    query = db.query(Property).filter(
        Property.organization_id == org_id,
        Property.is_active.is_(True), Property.deleted_at.is_(None),
    )
    if _role(actor) == "MANAGER":
        assigned = db.query(PropertyAssignment.property_id).filter(
            PropertyAssignment.user_id == actor.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        query = query.filter(Property.id.in_(assigned))
    return query


def _group(db: Session, *, org_id: int, group_id: int) -> PropertyGroup:
    found = db.query(PropertyGroup).filter(
        PropertyGroup.id == group_id,
        PropertyGroup.organization_id == org_id,
    ).first()
    if found is None:
        raise ReportDeliveryError("Property group not found")
    return found


def _members(db: Session, *, org_id: int, actor: User, group_id: int):
    return (
        _visible(db, org_id=org_id, actor=actor)
        .join(PropertyGroupMembership, PropertyGroupMembership.property_id == Property.id)
        .filter(
            PropertyGroupMembership.organization_id == org_id,
            PropertyGroupMembership.group_id == group_id,
        )
        .order_by(Property.name.asc(), Property.id.asc())
        .all()
    )


def _out(group: PropertyGroup, members: list[Property]) -> PropertyGroupOut:
    return PropertyGroupOut(
        id=group.id, name=group.name, description=group.description,
        property_ids=[prop.id for prop in members], updated_at=group.updated_at,
    )


def list_groups(db: Session, *, actor: User) -> list[PropertyGroupOut]:
    org_id = require_groups_access(db, actor=actor)
    groups = db.query(PropertyGroup).filter(
        PropertyGroup.organization_id == org_id,
    ).order_by(PropertyGroup.name.asc(), PropertyGroup.id.asc()).all()
    output = []
    for group in groups:
        visible_members = _members(db, org_id=org_id, actor=actor, group_id=group.id)
        if _role(actor) == "MANAGER" and not visible_members:
            continue
        output.append(_out(group, visible_members))
    return output


def save_group(
    db: Session, *, actor: User, payload: PropertyGroupUpsertIn,
    group_id: int | None = None,
) -> PropertyGroupOut:
    org_id = require_groups_access(db, actor=actor, write=True)
    visible = _visible(db, org_id=org_id, actor=actor)
    if payload.property_ids:
        found = {
            prop.id for prop in visible.filter(
                Property.id.in_(payload.property_ids),
            ).all()
        }
        if found != set(payload.property_ids):
            raise ReportDeliveryError("Property not found")
    clean_name = payload.name.strip()
    key = clean_name.casefold()
    duplicate = db.query(PropertyGroup).filter(
        PropertyGroup.organization_id == org_id,
        PropertyGroup.name_key == key,
    )
    if group_id is not None:
        duplicate = duplicate.filter(PropertyGroup.id != group_id)
    if duplicate.first() is not None:
        raise ReportDeliveryError("Property group name already exists")
    created = group_id is None
    group = (PropertyGroup(
        organization_id=org_id, created_by_id=actor.id,
    ) if created else _group(db, org_id=org_id, group_id=group_id))
    if created:
        db.add(group)
    group.name = clean_name
    group.name_key = key
    group.description = payload.description.strip() if payload.description else None
    group.updated_by_id = actor.id
    db.flush()
    current = db.query(PropertyGroupMembership).filter(
        PropertyGroupMembership.organization_id == org_id,
        PropertyGroupMembership.group_id == group.id,
    ).all()
    current_ids = {member.property_id for member in current}
    updated_ids = set(payload.property_ids)
    for membership in current:
        if membership.property_id not in updated_ids:
            db.delete(membership)
    for prop_id in sorted(updated_ids - current_ids):
        db.add(PropertyGroupMembership(
            organization_id=org_id, group_id=group.id, property_id=prop_id,
        ))
    db.flush()
    append_audit_log(
        db, organization_id=org_id, user_id=actor.id,
        entity_type="property_group", entity_id=group.id,
        action="created" if created else "updated",
        new_value={
            "name": group.name, "property_ids": sorted(updated_ids),
        },
    )
    db.commit()
    db.refresh(group)
    return _out(group, _members(db, org_id=org_id, actor=actor, group_id=group.id))


def delete_group(db: Session, *, actor: User, group_id: int) -> None:
    org_id = require_groups_access(db, actor=actor, write=True)
    group = _group(db, org_id=org_id, group_id=group_id)
    append_audit_log(
        db, organization_id=org_id, user_id=actor.id,
        entity_type="property_group", entity_id=group.id,
        action="deleted", old_value={"name": group.name},
    )
    db.query(PropertyGroupMembership).filter(
        PropertyGroupMembership.organization_id == org_id,
        PropertyGroupMembership.group_id == group.id,
    ).delete(synchronize_session=False)
    db.delete(group)
    db.commit()


def build_property_group_directory(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"group_id"}:
        raise ReportDeliveryError("Unsupported property group report parameter")
    group_id = _int_param(parameters, "group_id")
    org_id = require_groups_access(db, actor=current_user)
    if org_id != organization_id:
        raise ReportDeliveryError("Property group permission required")
    if not permission_allows_user(db, user=current_user, menu_key="REPORTING.ALL"):
        raise ReportDeliveryError("Property group report permission required")
    groups = db.query(PropertyGroup).filter(
        PropertyGroup.organization_id == org_id,
    )
    if group_id is not None:
        _group(db, org_id=org_id, group_id=group_id)
        groups = groups.filter(PropertyGroup.id == group_id)
    rows = []
    for group in groups.order_by(PropertyGroup.name, PropertyGroup.id).all():
        members = _members(db, org_id=org_id, actor=current_user, group_id=group.id)
        # A manager never receives an empty group name without any
        # currently visible/assigned property in that group.
        if not members and _role(current_user) == "MANAGER":
            if group_id is not None:
                raise ReportDeliveryError("Property group not found")
            continue
        if not members:
            rows.append((group.name, group.description or "", "", "", "", "",
                         "", "", group.id, ""))
        for prop in members:
            rows.append((
                group.name, group.description or "", prop.name,
                prop.address_line1, prop.city, prop.state,
                prop.zip_code, prop.country or "", group.id, prop.id,
            ))
    return ReportPayload(
        title="Property Group Directory (recorded memberships, visible properties only)",
        filename="property-group-directory.csv",
        headers=HEADERS, rows=tuple(rows),
    )
