# ============================================================
# routers/properties.py
# ------------------------------------------------------------
#   POST   /properties                          create
#   GET    /properties                          list
#   GET    /properties/{id}                     get one
#   PATCH  /properties/{id}                     update
#   DELETE /properties/{id}                     soft-delete
#   POST   /properties/{id}/restore             restore
#   GET    /properties/{id}/history             audit log
#
#   POST   /properties/{id}/units               create unit
#   GET    /properties/{id}/units               list units
#   PATCH  /properties/{id}/units/{unit_id}     update unit
#
# PERMISSION RULES:
#   - Admin sees everything.
#   - Owner sees only properties in their organization.
#   - Manager sees only properties they're assigned to.
#   - Crew: same as manager (for now).
#   - Tenant: blocked from these endpoints entirely.
# ============================================================

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.models.property import Property, Unit, PropertyAssignment
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.services.plan_limits import PlanUnitLimitExceeded, require_unit_capacity
from app.services.menu_resolver import permission_allows_user
from app.schemas.property import (
    PropertyCreate,
    PropertyOut,
    PropertyUpdate,
    PropertyWithUnits,
    UnitCreate,
    UnitOut,
    UnitUpdate,
)


router = APIRouter(prefix="/properties", tags=["Properties"])


# ------------------------------------------------------------
# PERMISSION HELPERS
# ------------------------------------------------------------
def require_non_tenant(current_user: User):
    """Tenants cannot access property management routes."""
    if current_user.role == UserRole.TENANT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenants cannot access this resource",
        )


def _require_property_permission(
    db: Session,
    current_user: User,
    menu_key: str,
) -> int:
    require_non_tenant(current_user)
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no organization.",
        )
    if not permission_allows_user(
        db,
        user=current_user,
        menu_key=menu_key,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Property permission required.",
        )
    return current_user.organization_id


def check_property_access(db: Session, user: User, property_id: int) -> Property:
    """
    Return the property if the user is allowed to see it.
    Otherwise raise 403 or 404.
    """
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    if user.role in (UserRole.ADMIN, UserRole.OWNER):
        if prop.organization_id != user.organization_id:
            raise HTTPException(status_code=403, detail="Not your property")
        return prop

    if user.role in (UserRole.MANAGER, UserRole.CREW):
        assigned = (
            db.query(PropertyAssignment)
            .filter(
                PropertyAssignment.property_id == prop.id,
                PropertyAssignment.user_id == user.id,
                PropertyAssignment.is_active == True,  # noqa: E712
            )
            .first()
        )
        if not assigned:
            raise HTTPException(status_code=403, detail="Not assigned to this property")
        return prop

    raise HTTPException(status_code=403, detail="Access denied")


def visible_properties_query(db: Session, user: User):
    """Return a SQLAlchemy query pre-filtered by role."""
    q = db.query(Property)

    if user.role in (UserRole.ADMIN, UserRole.OWNER):
        return q.filter(Property.organization_id == user.organization_id)

    if user.role in (UserRole.MANAGER, UserRole.CREW):
        return (
            q.join(PropertyAssignment, PropertyAssignment.property_id == Property.id)
            .filter(
                PropertyAssignment.user_id == user.id,
                PropertyAssignment.is_active == True,  # noqa: E712
            )
        )

    return q.filter(Property.id == -1)


# ------------------------------------------------------------
# CREATE
# ------------------------------------------------------------
@router.post("", response_model=PropertyOut, status_code=status.HTTP_201_CREATED)
def create_property(
    payload: PropertyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new property. Admin and Owner only."""
    _require_property_permission(db, current_user, "PROPERTIES.ADD")

    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER):
        raise HTTPException(status_code=403, detail="Only admins and owners can create properties")

    if payload.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=403,
            detail="Can only create properties in your organization",
        )

    prop = Property(**payload.model_dump())
    db.add(prop)
    db.commit()
    db.refresh(prop)

    log_action(
        db, current_user,
        entity_type="property",
        entity_id=prop.id,
        action="created",
        new_value={
            "name": prop.name,
            "address": f"{prop.address_line1}, {prop.city}, {prop.state}",
        },
    )

    return prop


# ------------------------------------------------------------
# LIST
# ------------------------------------------------------------
@router.get("", response_model=List[PropertyOut])
def list_properties(
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List properties. By default excludes soft-deleted ones."""
    _require_property_permission(db, current_user, "PROPERTIES.ALL")
    q = visible_properties_query(db, current_user)
    if not include_deleted:
        q = q.filter(Property.is_active == True)  # noqa: E712
    return q.all()


# ------------------------------------------------------------
# GET ONE
# ------------------------------------------------------------
@router.get("/{property_id}", response_model=PropertyWithUnits)
def get_property(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_property_permission(db, current_user, "PROPERTIES.ALL")
    return check_property_access(db, current_user, property_id)


# ------------------------------------------------------------
# UPDATE
# ------------------------------------------------------------
@router.patch("/{property_id}", response_model=PropertyOut)
def update_property(
    property_id: int,
    payload: PropertyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a property. Admin and Owner only."""
    _require_property_permission(db, current_user, "PROPERTIES.ALL")

    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER):
        raise HTTPException(status_code=403, detail="Only admins and owners can update properties")

    prop = check_property_access(db, current_user, property_id)

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        old = getattr(prop, field)
        if old != value:
            setattr(prop, field, value)
            log_action(
                db, current_user,
                entity_type="property",
                entity_id=prop.id,
                action="updated",
                field_name=field,
                old_value=old,
                new_value=value,
            )

    db.commit()
    db.refresh(prop)
    return prop


# ------------------------------------------------------------
# SOFT DELETE
# ------------------------------------------------------------
@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property(
    property_id: int,
    reason: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a property. Set is_active=False, record who/why."""
    _require_property_permission(db, current_user, "PROPERTIES.ALL")

    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER):
        raise HTTPException(status_code=403, detail="Only admins and owners can delete properties")

    prop = check_property_access(db, current_user, property_id)

    old_active = prop.is_active
    prop.is_active = False
    prop.deleted_at = datetime.utcnow()
    prop.deleted_by_id = current_user.id
    prop.delete_reason = reason
    db.commit()

    log_action(
        db, current_user,
        entity_type="property",
        entity_id=prop.id,
        action="deleted",
        field_name="is_active",
        old_value=old_active,
        new_value=False,
    )

    return None


# ------------------------------------------------------------
# RESTORE
# ------------------------------------------------------------
@router.post("/{property_id}/restore", response_model=PropertyOut)
def restore_property(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Restore a soft-deleted property."""
    _require_property_permission(db, current_user, "PROPERTIES.ALL")

    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER):
        raise HTTPException(status_code=403, detail="Only admins and owners can restore")

    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    if prop.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not your property")

    prop.is_active = True
    prop.deleted_at = None
    prop.deleted_by_id = None
    prop.delete_reason = None
    db.commit()

    log_action(
        db, current_user,
        entity_type="property",
        entity_id=prop.id,
        action="restored",
    )

    db.refresh(prop)
    return prop


# ------------------------------------------------------------
# HISTORY
# ------------------------------------------------------------
@router.get("/{property_id}/history", response_model=List[dict])
def get_property_history(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the audit log for a property."""
    _require_property_permission(db, current_user, "PROPERTIES.ALL")
    check_property_access(db, current_user, property_id)

    logs = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == "property", AuditLog.entity_id == property_id)
        .order_by(AuditLog.created_at.desc())
        .all()
    )

    result = []
    for log in logs:
        u = None
        if log.user_id:
            u = db.query(User).filter(User.id == log.user_id).first()
        result.append({
            "id": log.id,
            "action": log.action,
            "field_name": log.field_name,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "created_at": log.created_at.isoformat(),
            "user_name": f"{u.first_name} {u.last_name}" if u else "System",
            "user_id": log.user_id,
        })
    return result


# ------------------------------------------------------------
# UNIT ROUTES
# ------------------------------------------------------------
@router.post("/{property_id}/units", response_model=UnitOut, status_code=status.HTTP_201_CREATED)
def create_unit(
    property_id: int,
    payload: UnitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a unit inside a property. Admin, Owner, Manager."""
    _require_property_permission(db, current_user, "PROPERTIES.UNITS")

    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER):
        raise HTTPException(status_code=403, detail="Only admins, owners, and managers can create units")

    prop = check_property_access(db, current_user, property_id)

    existing = (
        db.query(Unit)
        .filter(Unit.property_id == prop.id, Unit.unit_number == payload.unit_number)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Unit number already exists in this property")

    try:
        require_unit_capacity(
            db,
            organization_id=prop.organization_id,
        )
    except PlanUnitLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"PLAN_UNIT_LIMIT_REACHED: {exc}",
        ) from exc

    unit = Unit(property_id=prop.id, **payload.model_dump())
    db.add(unit)
    db.commit()
    db.refresh(unit)

    log_action(
        db, current_user,
        entity_type="unit",
        entity_id=unit.id,
        action="created",
        new_value={"unit_number": unit.unit_number, "property_id": prop.id},
    )

    return unit


@router.get("/{property_id}/units", response_model=List[UnitOut])
def list_units(
    property_id: int,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all units inside a property. Excludes soft-deleted by default."""
    _require_property_permission(db, current_user, "PROPERTIES.UNITS")
    prop = check_property_access(db, current_user, property_id)
    q = db.query(Unit).filter(Unit.property_id == prop.id)
    if not include_deleted:
        q = q.filter(Unit.is_active == True)  # noqa: E712
    return q.all()


@router.patch("/{property_id}/units/{unit_id}", response_model=UnitOut)
def update_unit(
    property_id: int,
    unit_id: int,
    payload: UnitUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a unit. Admin, Owner, Manager."""
    _require_property_permission(db, current_user, "PROPERTIES.UNITS")

    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER):
        raise HTTPException(status_code=403, detail="Only admins, owners, and managers can update units")

    prop = check_property_access(db, current_user, property_id)
    unit = db.query(Unit).filter(Unit.id == unit_id, Unit.property_id == prop.id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        old = getattr(unit, field)
        if old != value:
            setattr(unit, field, value)
            log_action(
                db, current_user,
                entity_type="unit",
                entity_id=unit.id,
                action="updated",
                field_name=field,
                old_value=old,
                new_value=value,
            )

    db.commit()
    db.refresh(unit)
    return unit

   
   

# ------------------------------------------------------------
# GET ONE UNIT
# ------------------------------------------------------------
@router.get("/{property_id}/units/{unit_id}", response_model=UnitOut)
def get_unit(
    property_id: int,
    unit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single unit."""
    _require_property_permission(db, current_user, "PROPERTIES.UNITS")
    prop = check_property_access(db, current_user, property_id)
    unit = db.query(Unit).filter(Unit.id == unit_id, Unit.property_id == prop.id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    return unit


# ------------------------------------------------------------
# DELETE UNIT (soft delete)
# ------------------------------------------------------------
@router.delete("/{property_id}/units/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_unit(
    property_id: int,
    unit_id: int,
    reason: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a unit."""
    _require_property_permission(db, current_user, "PROPERTIES.UNITS")

    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER):
        raise HTTPException(status_code=403, detail="Not allowed")

    prop = check_property_access(db, current_user, property_id)
    unit = db.query(Unit).filter(Unit.id == unit_id, Unit.property_id == prop.id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")

    unit.is_active = False
    unit.deleted_at = datetime.utcnow()
    unit.deleted_by_id = current_user.id
    unit.delete_reason = reason
    db.commit()

    log_action(
        db, current_user,
        entity_type="unit",
        entity_id=unit.id,
        action="deleted",
        field_name="is_active",
        old_value=True,
        new_value=False,
    )

    return None


# ------------------------------------------------------------
# RESTORE UNIT
# ------------------------------------------------------------
@router.post("/{property_id}/units/{unit_id}/restore", response_model=UnitOut)
def restore_unit(
    property_id: int,
    unit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Restore a soft-deleted unit."""
    _require_property_permission(db, current_user, "PROPERTIES.UNITS")

    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER):
        raise HTTPException(status_code=403, detail="Only admins and owners can restore")

    prop = check_property_access(db, current_user, property_id)
    unit = db.query(Unit).filter(Unit.id == unit_id, Unit.property_id == prop.id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")

    if not unit.is_active:
        try:
            require_unit_capacity(
                db,
                organization_id=prop.organization_id,
            )
        except PlanUnitLimitExceeded as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"PLAN_UNIT_LIMIT_REACHED: {exc}",
            ) from exc

    unit.is_active = True
    unit.deleted_at = None
    unit.deleted_by_id = None
    unit.delete_reason = None
    db.commit()

    log_action(
        db, current_user,
        entity_type="unit",
        entity_id=unit.id,
        action="restored",
    )

    db.refresh(unit)
    return unit