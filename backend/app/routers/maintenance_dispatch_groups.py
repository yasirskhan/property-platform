"""Owner/Admin maintenance grouping and dispatch configuration.

Rules are configuration records only. No calls, texts, emails, promises,
vendor contact, or financial obligations are created by these endpoints.
"""
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User, UserRole, Organization
from app.models.property import Property
from app.models.maintenance_dispatch import (
    MaintenanceDispatchGroup, MaintenanceDispatchProperty, MaintenanceDispatchRule,
)
from app.schemas.maintenance_dispatch import (
    MaintenanceGroupInput, MaintenanceGroupOut, MaintenanceRuleInput,
    MaintenanceRuleOut, MaintenanceDispatchContactChoice, MaintenanceDispatchPropertyChoice,
)
from app.services.audit import append_audit_log
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/maintenance/dispatch-groups", tags=["Maintenance Dispatch Groups"])
URGENCIES = ("emergency", "normal", "low")
DAYPARTS = ("business_hours", "after_hours")


def _require_owner(db: Session, actor: User, *, lock: bool = False) -> Organization:
    if (not actor.is_active or actor.deleted_at is not None or actor.organization_id is None
            or actor.role not in (UserRole.ADMIN, UserRole.OWNER)):
        raise HTTPException(status_code=403, detail="Owner/Admin maintenance settings access required")
    query = db.query(Organization).filter(
        Organization.id == actor.organization_id,
        Organization.is_active.is_(True), Organization.deleted_at.is_(None),
    )
    org = query.with_for_update().first() if lock else query.first()
    if org is None:
        raise HTTPException(status_code=403, detail="Active organization required")
    return org


def _default_group(db: Session, actor: User):
    org = _require_owner(db, actor, lock=True)
    default = db.query(MaintenanceDispatchGroup).filter(
        MaintenanceDispatchGroup.organization_id == org.id,
        MaintenanceDispatchGroup.name_key == "default",
    ).first()
    if default is None:
        default = MaintenanceDispatchGroup(
            organization_id=org.id, name="DEFAULT", name_key="default",
            timezone_name="UTC", business_start_hour=9, business_end_hour=17,
            updated_by_user_id=actor.id,
        )
        db.add(default)
        db.flush()
        append_audit_log(
            db, user_id=actor.id, organization_id=org.id,
            entity_type="maintenance_dispatch_group", entity_id=default.id,
            action="default_initialized",
            new_value={"name": "DEFAULT", "auto_dispatch_enabled": False},
        )
        db.commit()
    return default


def _group(db: Session, actor: User, group_id: int) -> MaintenanceDispatchGroup:
    group = db.query(MaintenanceDispatchGroup).filter(
        MaintenanceDispatchGroup.id == group_id,
        MaintenanceDispatchGroup.organization_id == actor.organization_id,
    ).first()
    if group is None:
        raise HTTPException(status_code=404, detail="Maintenance dispatch group not found")
    return group


def _choices(db: Session, actor: User) -> list[Property]:
    props = db.query(Property).filter(
        Property.organization_id == actor.organization_id,
        Property.is_active.is_(True), Property.deleted_at.is_(None),
    ).order_by(Property.name.asc(), Property.id.asc()).limit(501).all()
    if len(props) > 500:
        raise HTTPException(status_code=422, detail="Too many properties for dispatch group settings")
    return props


def _rules(db: Session, group: MaintenanceDispatchGroup) -> list[MaintenanceRuleOut]:
    existing = db.query(MaintenanceDispatchRule).filter(
        MaintenanceDispatchRule.organization_id == group.organization_id,
        MaintenanceDispatchRule.group_id == group.id,
    ).all()
    by_key = {(row.urgency, row.daypart): row for row in existing}
    return [
        MaintenanceRuleOut(
            urgency=urgency, daypart=daypart, configured=(urgency, daypart) in by_key,
            first_target=row.first_target if row else "crew",
            backup_target=row.backup_target if row else "vendor",
            timeout_minutes=row.timeout_minutes if row else 15,
            escalate=row.escalate if row else False,
            primary_contact_user_id=row.primary_contact_user_id if row else None,
            backup_contact_user_id=row.backup_contact_user_id if row else None,
        )
        for urgency in URGENCIES for daypart in DAYPARTS
        for row in [by_key.get((urgency, daypart))]
    ]


def _snapshots(db: Session, actor: User) -> list[MaintenanceGroupOut]:
    properties = _choices(db, actor)
    property_ids = {p.id for p in properties}
    groups = db.query(MaintenanceDispatchGroup).filter(
        MaintenanceDispatchGroup.organization_id == actor.organization_id,
    ).order_by(MaintenanceDispatchGroup.name_key.asc(), MaintenanceDispatchGroup.id.asc()).all()
    # The join to the actual property and group protects against corrupted
    # stored organization IDs, even though FKs constrain each ID separately.
    assigned = db.query(MaintenanceDispatchProperty, Property, MaintenanceDispatchGroup).join(
        Property, Property.id == MaintenanceDispatchProperty.property_id
    ).join(MaintenanceDispatchGroup, MaintenanceDispatchGroup.id == MaintenanceDispatchProperty.group_id).filter(
        MaintenanceDispatchProperty.organization_id == actor.organization_id,
        Property.organization_id == actor.organization_id,
        MaintenanceDispatchGroup.organization_id == actor.organization_id,
        Property.id.in_(property_ids),
    ).all() if property_ids else []
    by_group: dict[int, list[int]] = {}
    explicitly_bound: set[int] = set()
    for binding, prop, group in assigned:
        if group.name_key == "default":
            # DEFAULT is inherited, never materialized as an override.
            raise HTTPException(status_code=409, detail="Malformed DEFAULT dispatch membership")
        by_group.setdefault(group.id, []).append(prop.id)
        explicitly_bound.add(prop.id)
    output = []
    for group in groups:
        members = (sorted(property_ids - explicitly_bound) if group.name_key == "default"
                   else sorted(by_group.get(group.id, [])))
        output.append(MaintenanceGroupOut(
            id=group.id, name=group.name, is_default=(group.name_key == "default"),
            timezone_name=group.timezone_name,
            business_start_hour=group.business_start_hour,
            business_end_hour=group.business_end_hour,
            property_ids=members, automation_requested=bool(group.automation_requested), rules=_rules(db, group),
        ))
    return output


def _validate_settings(payload: MaintenanceGroupInput) -> tuple[str, str]:
    if payload.business_start_hour >= payload.business_end_hour:
        raise HTTPException(status_code=422, detail="Business hours must have a positive interval")
    try:
        ZoneInfo(payload.timezone_name)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        raise HTTPException(status_code=422, detail="A valid IANA timezone is required")
    name = payload.name.strip()
    return name, name.casefold()


def _update_bindings(db: Session, actor: User, group: MaintenanceDispatchGroup, wanted: set[int]) -> None:
    properties = {p.id for p in _choices(db, actor)}
    if not wanted <= properties:
        raise HTTPException(status_code=404, detail="One or more properties are not active in your organization")
    old = db.query(MaintenanceDispatchProperty).filter(
        MaintenanceDispatchProperty.organization_id == actor.organization_id,
        MaintenanceDispatchProperty.group_id == group.id,
    ).all()
    for record in old:
        if record.property_id in properties and record.property_id not in wanted:
            db.delete(record)  # Back to inherited DEFAULT, historic retired binding retained.
            append_audit_log(
                db, user_id=actor.id, organization_id=actor.organization_id,
                entity_type="maintenance_dispatch_property", entity_id=record.property_id,
                action="group_changed",
                old_value={"group_id": group.id}, new_value={"group_id": None, "inherits_default": True},
            )
    for prop_id in sorted(wanted):
        existing = db.query(MaintenanceDispatchProperty).filter(
            MaintenanceDispatchProperty.property_id == prop_id,
        ).first()
        if existing and existing.organization_id != actor.organization_id:
            raise HTTPException(status_code=409, detail="Conflicting organization binding")
        old_group = existing.group_id if existing else None
        if old_group == group.id:
            continue
        if existing:
            existing.group_id = group.id
        else:
            db.add(MaintenanceDispatchProperty(
                organization_id=actor.organization_id, property_id=prop_id, group_id=group.id,
            ))
        append_audit_log(
            db, user_id=actor.id, organization_id=actor.organization_id,
            entity_type="maintenance_dispatch_property", entity_id=prop_id,
            action="group_changed",
            old_value={"group_id": old_group},
            new_value={"group_id": group.id},
        )


@router.get("", response_model=list[MaintenanceGroupOut])
def list_dispatch_groups(
    response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    _default_group(db, current_user)
    return _snapshots(db, current_user)


@router.get("/properties", response_model=list[MaintenanceDispatchPropertyChoice])
def dispatch_group_properties(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    _require_owner(db, current_user)
    return [MaintenanceDispatchPropertyChoice(id=p.id, name=p.name) for p in _choices(db, current_user)]


@router.get("/contacts", response_model=list[MaintenanceDispatchContactChoice])
def dispatch_group_contacts(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    _require_owner(db, current_user)
    contacts = db.query(User).filter(
        User.organization_id == current_user.organization_id,
        User.role.in_([UserRole.ADMIN, UserRole.OWNER]),
        User.is_active.is_(True), User.deleted_at.is_(None),
    ).order_by(User.first_name.asc(), User.id.asc()).limit(101).all()
    if len(contacts) > 100:
        raise HTTPException(status_code=422, detail="Too many dispatch escalation contacts")
    return [MaintenanceDispatchContactChoice(
        id=u.id, name=(u.first_name + " " + u.last_name).strip(),
    ) for u in contacts]


@router.post("", response_model=MaintenanceGroupOut, status_code=201)
def create_dispatch_group(
    payload: MaintenanceGroupInput,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    _default_group(db, current_user)
    _require_owner(db, current_user, lock=True)
    name, key = _validate_settings(payload)
    if key == "default":
        raise HTTPException(status_code=409, detail="DEFAULT group is reserved and cannot be duplicated")
    if db.query(MaintenanceDispatchGroup.id).filter(
        MaintenanceDispatchGroup.organization_id == current_user.organization_id,
        MaintenanceDispatchGroup.name_key == key,
    ).first():
        raise HTTPException(status_code=409, detail="Maintenance group name is already in use")
    if not set(payload.property_ids) <= {p.id for p in _choices(db, current_user)}:
        raise HTTPException(status_code=404, detail="One or more properties not available")
    group = MaintenanceDispatchGroup(
        organization_id=current_user.organization_id, name=name, name_key=key,
        timezone_name=payload.timezone_name, business_start_hour=payload.business_start_hour,
        business_end_hour=payload.business_end_hour,
        automation_requested=payload.automation_requested,
        updated_by_user_id=current_user.id,
    )
    db.add(group); db.flush()
    _update_bindings(db, current_user, group, set(payload.property_ids))
    append_audit_log(
        db, user_id=current_user.id, organization_id=current_user.organization_id,
        entity_type="maintenance_dispatch_group", entity_id=group.id,
        action="created",
        new_value={"name": name, "property_ids": sorted(payload.property_ids), "timezone": payload.timezone_name,
                   "business_start_hour": payload.business_start_hour,
                   "business_end_hour": payload.business_end_hour,
                   "automation_requested": payload.automation_requested,
                   "automation_executor_enabled": False},
    )
    db.commit()
    return next(g for g in _snapshots(db, current_user) if g.id == group.id)


@router.put("/{group_id}", response_model=MaintenanceGroupOut)
def edit_dispatch_group(
    group_id: int, payload: MaintenanceGroupInput,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    _require_owner(db, current_user, lock=True)
    group = _group(db, current_user, group_id)
    name, key = _validate_settings(payload)
    default = group.name_key == "default"
    if default and (key != "default" or payload.property_ids):
        raise HTTPException(status_code=409, detail="DEFAULT cannot be renamed or explicitly assigned")
    if not default and key == "default":
        raise HTTPException(status_code=409, detail="DEFAULT name is reserved")
    if db.query(MaintenanceDispatchGroup.id).filter(
        MaintenanceDispatchGroup.organization_id == current_user.organization_id,
        MaintenanceDispatchGroup.name_key == key,
        MaintenanceDispatchGroup.id != group.id,
    ).first():
        raise HTTPException(status_code=409, detail="Duplicate maintenance group name")
    before = next(g for g in _snapshots(db, current_user) if g.id == group.id)
    after_settings = {
        "name": "DEFAULT" if default else name,
        "timezone_name": payload.timezone_name,
        "business_start_hour": payload.business_start_hour,
        "business_end_hour": payload.business_end_hour,
        "property_ids": before.property_ids if default else sorted(payload.property_ids),
        "automation_requested": payload.automation_requested,
    }
    previous = {
        "name": before.name, "timezone_name": before.timezone_name,
        "business_start_hour": before.business_start_hour,
        "business_end_hour": before.business_end_hour,
        "property_ids": before.property_ids,
        "automation_requested": before.automation_requested,
    }
    if previous == after_settings:
        return before
    group.name = after_settings["name"]
    group.name_key = key
    group.timezone_name = payload.timezone_name
    group.business_start_hour = payload.business_start_hour
    group.business_end_hour = payload.business_end_hour
    group.automation_requested = payload.automation_requested
    group.updated_by_user_id = current_user.id
    if not default:
        _update_bindings(db, current_user, group, set(payload.property_ids))
    group.updated_at = datetime.utcnow()
    append_audit_log(
        db, user_id=current_user.id, organization_id=current_user.organization_id,
        entity_type="maintenance_dispatch_group", entity_id=group.id,
        action="updated", old_value=previous, new_value=after_settings,
    )
    db.commit()
    return next(g for g in _snapshots(db, current_user) if g.id == group.id)


@router.put("/{group_id}/rules/{urgency}/{daypart}", response_model=MaintenanceRuleOut)
def save_dispatch_rule(
    group_id: int, urgency: str, daypart: str, payload: MaintenanceRuleInput,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    _require_owner(db, current_user, lock=True)
    group = _group(db, current_user, group_id)
    if urgency not in URGENCIES or daypart not in DAYPARTS:
        raise HTTPException(status_code=422, detail="Unsupported urgency or daypart")
    ids = [n for n in (payload.primary_contact_user_id, payload.backup_contact_user_id) if n is not None]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=422, detail="Primary and backup contacts must be different")
    if ids:
        active = {u.id for u in db.query(User).filter(
            User.id.in_(ids), User.organization_id == current_user.organization_id,
            User.is_active.is_(True), User.deleted_at.is_(None),
            User.role.in_([UserRole.ADMIN, UserRole.OWNER]),
        ).all()}
        if active != set(ids):
            raise HTTPException(status_code=404, detail="An escalation contact is unavailable")
    rule = db.query(MaintenanceDispatchRule).filter(
        MaintenanceDispatchRule.organization_id == current_user.organization_id,
        MaintenanceDispatchRule.group_id == group.id,
        MaintenanceDispatchRule.urgency == urgency,
        MaintenanceDispatchRule.daypart == daypart,
    ).first()
    changed = payload.model_dump()
    prior = None if rule is None else {k: getattr(rule,k) for k in changed}
    if rule is not None and prior == changed:
        return next(row for row in _rules(db, group) if row.urgency == urgency and row.daypart == daypart)
    if rule is None:
        rule = MaintenanceDispatchRule(
            organization_id=current_user.organization_id, group_id=group.id,
            urgency=urgency, daypart=daypart,
        )
        db.add(rule)
    for key,value in changed.items():
        setattr(rule,key,value)
    rule.updated_by_user_id = current_user.id
    rule.updated_at = datetime.utcnow()
    db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=current_user.organization_id,
        entity_type="maintenance_dispatch_rule", entity_id=rule.id,
        action="created" if prior is None else "updated",
        old_value=prior, new_value={**changed, "group_id": group.id, "urgency": urgency, "daypart": daypart},
    )
    db.commit()
    return next(row for row in _rules(db, group) if row.urgency == urgency and row.daypart == daypart)
