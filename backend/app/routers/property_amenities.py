# ============================================================
# property_amenities.py (router)
# ------------------------------------------------------------
#   GET    /api/properties/{property_id}/amenities     list
#   POST   /api/properties/{property_id}/amenities     create
#   PATCH  /api/properties/{property_id}/amenities/{id} update
#   DELETE /api/properties/{property_id}/amenities/{id} soft delete
#
# Scoped by property_id in the URL, and both must belong to
# the caller's org.
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.property import Property
from app.models.property_amenity import PropertyAmenity
from app.schemas.property_amenity import (
    PropertyAmenityCreateIn,
    PropertyAmenityListOut,
    PropertyAmenityOut,
    PropertyAmenityUpdateIn,
)


router = APIRouter(
    prefix="/api/properties/{property_id}/amenities",
    tags=["Property Amenities"],
)


def _require_org(current_user: User) -> int:
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no organization.",
        )
    return current_user.organization_id


def _require_property(
    db: Session, org_id: int, property_id: int
) -> Property:
    prop = (
        db.query(Property)
        .filter(
            Property.id == property_id,
            Property.organization_id == org_id,
        )
        .first()
    )
    if prop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found.",
        )
    return prop


def _to_out(a: PropertyAmenity) -> PropertyAmenityOut:
    return PropertyAmenityOut(
        id=a.id,
        organization_id=a.organization_id,
        property_id=a.property_id,
        name=a.name,
        category=a.category,
        notes=a.notes,
        is_active=a.is_active,
        created_by_id=a.created_by_id,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


# ============================================================
# GET ""
# ============================================================

@router.get("", response_model=PropertyAmenityListOut)
def list_amenities(
    property_id: int,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)
    _require_property(db, org_id, property_id)

    q = (
        db.query(PropertyAmenity)
        .filter(
            PropertyAmenity.organization_id == org_id,
            PropertyAmenity.property_id == property_id,
        )
    )
    if not include_inactive:
        q = q.filter(PropertyAmenity.is_active.is_(True))

    total = q.count()
    rows = q.order_by(PropertyAmenity.name.asc()).all()

    return PropertyAmenityListOut(
        items=[_to_out(a) for a in rows],
        total=total,
    )


# ============================================================
# POST ""
# ============================================================

@router.post(
    "",
    response_model=PropertyAmenityOut,
    status_code=status.HTTP_201_CREATED,
)
def create_amenity(
    property_id: int,
    payload: PropertyAmenityCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)
    _require_property(db, org_id, property_id)

    if payload.property_id != property_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="property_id in body must match URL.",
        )

    try:
        a = PropertyAmenity(
            organization_id=org_id,
            property_id=property_id,
            name=payload.name.strip(),
            category=(payload.category or None),
            notes=payload.notes,
            is_active=True,
            created_by_id=current_user.id if current_user else None,
        )
        db.add(a)
        db.commit()
        db.refresh(a)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create amenity: {e}",
        )
    return _to_out(a)


# ============================================================
# PATCH /{id}
# ============================================================

@router.patch("/{amenity_id}", response_model=PropertyAmenityOut)
def update_amenity(
    property_id: int,
    amenity_id: int,
    payload: PropertyAmenityUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)
    _require_property(db, org_id, property_id)

    a = (
        db.query(PropertyAmenity)
        .filter(
            PropertyAmenity.id == amenity_id,
            PropertyAmenity.organization_id == org_id,
            PropertyAmenity.property_id == property_id,
        )
        .first()
    )
    if a is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Amenity not found.",
        )

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(a, k, v)

    try:
        db.commit()
        db.refresh(a)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update amenity: {e}",
        )
    return _to_out(a)


# ============================================================
# DELETE /{id} — soft delete
# ============================================================

@router.delete(
    "/{amenity_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_amenity(
    property_id: int,
    amenity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)
    _require_property(db, org_id, property_id)

    a = (
        db.query(PropertyAmenity)
        .filter(
            PropertyAmenity.id == amenity_id,
            PropertyAmenity.organization_id == org_id,
            PropertyAmenity.property_id == property_id,
        )
        .first()
    )
    if a is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Amenity not found.",
        )

    a.is_active = False
    db.commit()
    return None