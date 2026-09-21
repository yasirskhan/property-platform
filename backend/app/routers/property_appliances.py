# ============================================================
# property_appliances.py (router)
# ------------------------------------------------------------
#   GET    /api/properties/{property_id}/appliances         list
#   POST   /api/properties/{property_id}/appliances         create
#   PATCH  /api/properties/{property_id}/appliances/{id}    update
#   DELETE /api/properties/{property_id}/appliances/{id}    soft delete
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.property import Property
from app.models.property_appliance import PropertyAppliance
from app.schemas.property_appliance import (
    PropertyApplianceCreateIn,
    PropertyApplianceListOut,
    PropertyApplianceOut,
    PropertyApplianceUpdateIn,
)


router = APIRouter(
    prefix="/api/properties/{property_id}/appliances",
    tags=["Property Appliances"],
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


def _to_out(a: PropertyAppliance) -> PropertyApplianceOut:
    return PropertyApplianceOut(
        id=a.id,
        organization_id=a.organization_id,
        property_id=a.property_id,
        name=a.name,
        brand=a.brand,
        model_number=a.model_number,
        serial_number=a.serial_number,
        purchase_date=a.purchase_date,
        purchase_price=a.purchase_price,
        warranty_expires=a.warranty_expires,
        condition=a.condition,
        notes=a.notes,
        is_active=a.is_active,
        delete_reason=a.delete_reason,
        created_by_id=a.created_by_id,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


@router.get("", response_model=PropertyApplianceListOut)
def list_appliances(
    property_id: int,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)
    _require_property(db, org_id, property_id)

    q = (
        db.query(PropertyAppliance)
        .filter(
            PropertyAppliance.organization_id == org_id,
            PropertyAppliance.property_id == property_id,
        )
    )
    if not include_inactive:
        q = q.filter(PropertyAppliance.is_active.is_(True))

    total = q.count()
    rows = q.order_by(PropertyAppliance.name.asc()).all()

    return PropertyApplianceListOut(
        items=[_to_out(a) for a in rows],
        total=total,
    )


@router.post(
    "",
    response_model=PropertyApplianceOut,
    status_code=status.HTTP_201_CREATED,
)
def create_appliance(
    property_id: int,
    payload: PropertyApplianceCreateIn,
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
        a = PropertyAppliance(
            organization_id=org_id,
            property_id=property_id,
            name=payload.name.strip(),
            brand=payload.brand or None,
            model_number=payload.model_number or None,
            serial_number=payload.serial_number or None,
            purchase_date=payload.purchase_date,
            purchase_price=payload.purchase_price,
            warranty_expires=payload.warranty_expires,
            condition=payload.condition,
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
            detail=f"Failed to create appliance: {e}",
        )
    return _to_out(a)


@router.patch(
    "/{appliance_id}", response_model=PropertyApplianceOut
)
def update_appliance(
    property_id: int,
    appliance_id: int,
    payload: PropertyApplianceUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)
    _require_property(db, org_id, property_id)

    a = (
        db.query(PropertyAppliance)
        .filter(
            PropertyAppliance.id == appliance_id,
            PropertyAppliance.organization_id == org_id,
            PropertyAppliance.property_id == property_id,
        )
        .first()
    )
    if a is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appliance not found.",
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
            detail=f"Failed to update appliance: {e}",
        )
    return _to_out(a)


@router.delete(
    "/{appliance_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_appliance(
    property_id: int,
    appliance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)
    _require_property(db, org_id, property_id)

    a = (
        db.query(PropertyAppliance)
        .filter(
            PropertyAppliance.id == appliance_id,
            PropertyAppliance.organization_id == org_id,
            PropertyAppliance.property_id == property_id,
        )
        .first()
    )
    if a is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appliance not found.",
        )

    a.is_active = False
    db.commit()
    return None