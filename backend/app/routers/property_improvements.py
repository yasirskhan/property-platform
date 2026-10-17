# ============================================================
# property_improvements.py (router)
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.property import Property
from app.models.property_improvement import PropertyImprovement
from app.schemas.property_improvement import (
    PropertyImprovementCreateIn,
    PropertyImprovementListOut,
    PropertyImprovementOut,
    PropertyImprovementUpdateIn,
)


router = APIRouter(
    prefix="/api/properties/{property_id}/improvements",
    tags=["Property Improvements"],
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


def _to_out(i: PropertyImprovement) -> PropertyImprovementOut:
    return PropertyImprovementOut(
        id=i.id,
        organization_id=i.organization_id,
        property_id=i.property_id,
        improvement_date=i.improvement_date,
        description=i.description,
        cost=i.cost,
        contractor=i.contractor,
        category=i.category,
        warranty_expires=i.warranty_expires,
        notes=i.notes,
        is_active=i.is_active,
        delete_reason=i.delete_reason,
        created_by_id=i.created_by_id,
        created_at=i.created_at,
        updated_at=i.updated_at,
    )


@router.get("", response_model=PropertyImprovementListOut)
def list_improvements(
    property_id: int,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)
    _require_property(db, org_id, property_id)

    q = (
        db.query(PropertyImprovement)
        .filter(
            PropertyImprovement.organization_id == org_id,
            PropertyImprovement.property_id == property_id,
        )
    )
    if not include_inactive:
        q = q.filter(PropertyImprovement.is_active.is_(True))

    total = q.count()
    rows = (
        q.order_by(PropertyImprovement.improvement_date.desc()).all()
    )

    return PropertyImprovementListOut(
        items=[_to_out(i) for i in rows],
        total=total,
    )


@router.post(
    "",
    response_model=PropertyImprovementOut,
    status_code=status.HTTP_201_CREATED,
)
def create_improvement(
    property_id: int,
    payload: PropertyImprovementCreateIn,
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
        imp = PropertyImprovement(
            organization_id=org_id,
            property_id=property_id,
            improvement_date=payload.improvement_date,
            description=payload.description.strip(),
            cost=payload.cost,
            contractor=(payload.contractor or None),
            category=(payload.category or None),
            warranty_expires=payload.warranty_expires,
            notes=payload.notes,
            is_active=True,
            created_by_id=current_user.id if current_user else None,
        )
        db.add(imp)
        db.commit()
        db.refresh(imp)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create improvement: {e}",
        )
    return _to_out(imp)


@router.patch(
    "/{improvement_id}", response_model=PropertyImprovementOut
)
def update_improvement(
    property_id: int,
    improvement_id: int,
    payload: PropertyImprovementUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)
    _require_property(db, org_id, property_id)

    imp = (
        db.query(PropertyImprovement)
        .filter(
            PropertyImprovement.id == improvement_id,
            PropertyImprovement.organization_id == org_id,
            PropertyImprovement.property_id == property_id,
        )
        .first()
    )
    if imp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Improvement not found.",
        )

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(imp, k, v)

    try:
        db.commit()
        db.refresh(imp)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update improvement: {e}",
        )
    return _to_out(imp)


@router.delete(
    "/{improvement_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_improvement(
    property_id: int,
    improvement_id: int,
    reason: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)
    _require_property(db, org_id, property_id)

    imp = (
        db.query(PropertyImprovement)
        .filter(
            PropertyImprovement.id == improvement_id,
            PropertyImprovement.organization_id == org_id,
            PropertyImprovement.property_id == property_id,
        )
        .first()
    )
    if imp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Improvement not found.",
        )

    imp.is_active = False
    imp.delete_reason = reason.strip() if reason else None
    db.commit()
    return None