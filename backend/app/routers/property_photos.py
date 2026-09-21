# ============================================================
# property_photos.py (router)
# ------------------------------------------------------------
#   GET    /api/properties/{property_id}/photos         list
#   POST   /api/properties/{property_id}/photos         create
#   PATCH  /api/properties/{property_id}/photos/{id}    update
#   DELETE /api/properties/{property_id}/photos/{id}    soft delete
#
# Cover enforcement: setting is_cover=true on one photo
# automatically unsets is_cover on every other photo of the
# same property.
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.property import Property
from app.models.property_photo import PropertyPhoto
from app.schemas.property_photo import (
    PropertyPhotoCreateIn,
    PropertyPhotoListOut,
    PropertyPhotoOut,
    PropertyPhotoUpdateIn,
)


router = APIRouter(
    prefix="/api/properties/{property_id}/photos",
    tags=["Property Photos"],
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


def _clear_other_covers(
    db: Session, org_id: int, property_id: int, keep_id: int
) -> None:
    """Unset is_cover on all other photos of the same property."""
    (
        db.query(PropertyPhoto)
        .filter(
            PropertyPhoto.organization_id == org_id,
            PropertyPhoto.property_id == property_id,
            PropertyPhoto.id != keep_id,
            PropertyPhoto.is_cover.is_(True),
        )
        .update({PropertyPhoto.is_cover: False})
    )


def _to_out(p: PropertyPhoto) -> PropertyPhotoOut:
    return PropertyPhotoOut(
        id=p.id,
        organization_id=p.organization_id,
        property_id=p.property_id,
        url=p.url,
        filename=p.filename,
        original_name=p.original_name,
        content_type=p.content_type,
        size_bytes=p.size_bytes,
        caption=p.caption,
        is_marketing=p.is_marketing,
        is_cover=p.is_cover,
        sort_order=p.sort_order,
        is_active=p.is_active,
        delete_reason=p.delete_reason,
        created_by_id=p.created_by_id,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


# ============================================================
# GET ""
# ============================================================

@router.get("", response_model=PropertyPhotoListOut)
def list_photos(
    property_id: int,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)
    _require_property(db, org_id, property_id)

    q = (
        db.query(PropertyPhoto)
        .filter(
            PropertyPhoto.organization_id == org_id,
            PropertyPhoto.property_id == property_id,
        )
    )
    if not include_inactive:
        q = q.filter(PropertyPhoto.is_active.is_(True))

    total = q.count()
    rows = (
        q.order_by(
            PropertyPhoto.is_cover.desc(),
            PropertyPhoto.sort_order.asc(),
            PropertyPhoto.id.asc(),
        )
        .all()
    )

    return PropertyPhotoListOut(
        items=[_to_out(p) for p in rows],
        total=total,
    )


# ============================================================
# POST ""
# ============================================================

@router.post(
    "",
    response_model=PropertyPhotoOut,
    status_code=status.HTTP_201_CREATED,
)
def create_photo(
    property_id: int,
    payload: PropertyPhotoCreateIn,
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
        p = PropertyPhoto(
            organization_id=org_id,
            property_id=property_id,
            url=payload.url,
            filename=payload.filename,
            original_name=payload.original_name,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
            caption=payload.caption,
            is_marketing=payload.is_marketing,
            is_cover=payload.is_cover,
            sort_order=payload.sort_order,
            is_active=True,
            created_by_id=current_user.id if current_user else None,
        )
        db.add(p)
        db.flush()

        # If this is the new cover, unset all other covers
        if p.is_cover:
            _clear_other_covers(db, org_id, property_id, p.id)

        db.commit()
        db.refresh(p)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create photo: {e}",
        )
    return _to_out(p)


# ============================================================
# PATCH /{id}
# ============================================================

@router.patch("/{photo_id}", response_model=PropertyPhotoOut)
def update_photo(
    property_id: int,
    photo_id: int,
    payload: PropertyPhotoUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)
    _require_property(db, org_id, property_id)

    p = (
        db.query(PropertyPhoto)
        .filter(
            PropertyPhoto.id == photo_id,
            PropertyPhoto.organization_id == org_id,
            PropertyPhoto.property_id == property_id,
        )
        .first()
    )
    if p is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found.",
        )

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(p, k, v)

    try:
        db.flush()
        # If this photo is now the cover, unset all others
        if p.is_cover:
            _clear_other_covers(db, org_id, property_id, p.id)
        db.commit()
        db.refresh(p)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update photo: {e}",
        )
    return _to_out(p)


# ============================================================
# DELETE /{id} — soft delete
# ============================================================

@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_photo(
    property_id: int,
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)
    _require_property(db, org_id, property_id)

    p = (
        db.query(PropertyPhoto)
        .filter(
            PropertyPhoto.id == photo_id,
            PropertyPhoto.organization_id == org_id,
            PropertyPhoto.property_id == property_id,
        )
        .first()
    )
    if p is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found.",
        )

    p.is_active = False
    db.commit()
    return None