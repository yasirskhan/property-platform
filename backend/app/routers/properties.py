# ============================================================
# routers/properties.py
# ------------------------------------------------------------
# HTTP routes for properties and units:
#
#   POST   /properties                          create
#   GET    /properties                          list (filtered by role)
#   GET    /properties/{id}                     get one
#   PATCH  /properties/{id}                     update
#   DELETE /properties/{id}                     soft-delete
#
#   POST   /properties/{id}/units               create unit
#   GET    /properties/{id}/units               list units
#   PATCH  /properties/{id}/units/{unit_id}     update unit
#
# PERMISSION RULES (the important part):
#   - Admin sees everything.
#   - Owner sees only properties in their organization.
#   - Manager sees only properties they're assigned to.
#   - Crew: same as manager (for now).
#   - Tenant: blocked from these endpoints entirely.
# ============================================================

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.property import Property, Unit, PropertyAssignment
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
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


def check_property_access(db: Session, user: User, property_id: int) -> Property:
    """
    Return the property if the user is allowed to see it.
    Otherwise raise 403 or 404.
    """
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    # Admin sees everything
    if user.role == UserRole.ADMIN:
        return prop

    # Owner: must be in same organization
    if user.role == UserRole.OWNER:
        if prop.organization_id != user.organization_id:
            raise HTTPException(status_code=403, detail="Not your property")
        return prop

    # Manager / Crew: must be assigned to this property
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
    """
    Return a SQLAlchemy query pre-filtered so the user only sees
    the properties they're allowed to see.
    """
    q = db.query(Property)

    if user.role == UserRole.ADMIN:
        return q  # no filter

    if user.role == UserRole.OWNER:
        return q.filter(Property.organization_id == user.organization_id)

    if user.role in (UserRole.MANAGER, UserRole.CREW):
        return (
            q.join(PropertyAssignment, PropertyAssignment.property_id == Property.id)
            .filter(
                PropertyAssignment.user_id == user.id,
                PropertyAssignment.is_active == True,  # noqa: E712
            )
        )

    # Tenants should never reach here
    return q.filter(Property.id == -1)  # empty result


# ------------------------------------------------------------
# PROPERTY ROUTES
# ------------------------------------------------------------
@router.post("", response_model=PropertyOut, status_code=status.HTTP_201_CREATED)
def create_property(
    payload: PropertyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new property.
    Only Admin and Owner can create properties.
    """
    require_non_tenant(current_user)

    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER):
        raise HTTPException(status_code=403, detail="Only admins and owners can create properties")

    # Owner can only create in their own organization
    if current_user.role == UserRole.OWNER:
        if payload.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Can only create properties in your organization")

    prop = Property(**payload.model_dump())
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return prop


@router.get("", response_model=List[PropertyOut])
def list_properties(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all properties the current user is allowed to see."""
    require_non_tenant(current_user)
    return visible_properties_query(db, current_user).all()


@router.get("/{property_id}", response_model=PropertyWithUnits)
def get_property(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single property with its units."""
    require_non_tenant(current_user)
    return check_property_access(db, current_user, property_id)


@router.patch("/{property_id}", response_model=PropertyOut)
def update_property(
    property_id: int,
    payload: PropertyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a property. Only Admin and Owner."""
    require_non_tenant(current_user)

    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER):
        raise HTTPException(status_code=403, detail="Only admins and owners can update properties")

    prop = check_property_access(db, current_user, property_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(prop, field, value)

    db.commit()
    db.refresh(prop)
    return prop


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a property (set is_active=False). Only Admin and Owner."""
    require_non_tenant(current_user)

    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER):
        raise HTTPException(status_code=403, detail="Only admins and owners can delete properties")

    prop = check_property_access(db, current_user, property_id)
    prop.is_active = False
    db.commit()
    return None


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
    require_non_tenant(current_user)

    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER):
        raise HTTPException(status_code=403, detail="Only admins, owners, and managers can create units")

    prop = check_property_access(db, current_user, property_id)

    # Check unit_number uniqueness within property
    existing = (
        db.query(Unit)
        .filter(Unit.property_id == prop.id, Unit.unit_number == payload.unit_number)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Unit number already exists in this property")

    unit = Unit(property_id=prop.id, **payload.model_dump())
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


@router.get("/{property_id}/units", response_model=List[UnitOut])
def list_units(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all units inside a property."""
    require_non_tenant(current_user)
    prop = check_property_access(db, current_user, property_id)
    return db.query(Unit).filter(Unit.property_id == prop.id).all()


@router.patch("/{property_id}/units/{unit_id}", response_model=UnitOut)
def update_unit(
    property_id: int,
    unit_id: int,
    payload: UnitUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a unit. Admin, Owner, Manager."""
    require_non_tenant(current_user)

    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER):
        raise HTTPException(status_code=403, detail="Only admins, owners, and managers can update units")

    prop = check_property_access(db, current_user, property_id)
    unit = db.query(Unit).filter(Unit.id == unit_id, Unit.property_id == prop.id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(unit, field, value)

    db.commit()
    db.refresh(unit)
    return unit