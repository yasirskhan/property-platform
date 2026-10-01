"""Phase 4.12 short-term-rental channel reference registry.

Staff-entered listing references only. No provider credentials, reservation
sync, calendar sync, payout sync, or live pricing integration is represented.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.property import Property, PropertyAssignment, Unit
from app.models.short_term_rental import ShortTermRentalChannel, ShortTermRentalNightlyPrice
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.short_term_rental import (
    ShortTermRentalChannelIn,
    ShortTermRentalChannelOut,
    ShortTermRentalNightlyPriceIn,
    ShortTermRentalNightlyPriceOut,
)
from app.services.audit import append_audit_log
from app.services.customer_features import resolve_customer_features
from app.services.menu_resolver import permission_allows_user


router = APIRouter(prefix="/api/properties", tags=["Short-term rentals"])
FEATURE_KEY = "release.properties.short_term_rentals"
MAX_CHANNELS = 100
MAX_NIGHTLY_PRICES = 2000


def _property(db: Session, *, property_id: int, actor: User, write: bool) -> Property:
    if (
        actor.organization_id is None
        or not actor.is_active
        or actor.deleted_at is not None
        or actor.role not in {UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER}
        or (write and actor.role not in {UserRole.ADMIN, UserRole.OWNER})
        or not permission_allows_user(db, user=actor, menu_key="PROPERTIES.ALL")
    ):
        raise HTTPException(status_code=403, detail="Short-term rental property access required.")

    decision = next(
        (item for item in resolve_customer_features(db, user=actor) if item.key == FEATURE_KEY),
        None,
    )
    if decision is None or not decision.allowed:
        raise HTTPException(status_code=404, detail="Short-term rentals are not available.")

    prop = db.query(Property).filter(
        Property.id == property_id,
        Property.organization_id == actor.organization_id,
        Property.is_active.is_(True),
        Property.deleted_at.is_(None),
    ).first()
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found.")

    if actor.role == UserRole.MANAGER and not db.query(PropertyAssignment.id).filter(
        PropertyAssignment.property_id == prop.id,
        PropertyAssignment.user_id == actor.id,
        PropertyAssignment.is_active.is_(True),
        PropertyAssignment.deleted_at.is_(None),
    ).first():
        raise HTTPException(status_code=404, detail="Property not found.")

    return prop


def _active_unit(db: Session, *, property_id: int, unit_id: int) -> Unit:
    unit = db.query(Unit).filter(
        Unit.id == unit_id,
        Unit.property_id == property_id,
        Unit.is_active.is_(True),
        Unit.deleted_at.is_(None),
    ).first()
    if unit is None:
        raise HTTPException(status_code=404, detail="Unit not found.")
    return unit


def _item(
    db: Session,
    *,
    org_id: int,
    property_id: int,
    item_id: int,
) -> ShortTermRentalChannel:
    item = db.query(ShortTermRentalChannel).filter(
        ShortTermRentalChannel.id == item_id,
        ShortTermRentalChannel.organization_id == org_id,
        ShortTermRentalChannel.property_id == property_id,
        ShortTermRentalChannel.is_active.is_(True),
    ).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Recorded channel reference not found.")
    return item


def _unique(
    db: Session,
    *,
    org_id: int,
    property_id: int,
    provider: str,
    label: str,
    exclude_id: int | None = None,
) -> None:
    query = db.query(ShortTermRentalChannel.id).filter(
        ShortTermRentalChannel.organization_id == org_id,
        ShortTermRentalChannel.property_id == property_id,
        ShortTermRentalChannel.provider == provider,
        ShortTermRentalChannel.label == label,
    )
    if exclude_id is not None:
        query = query.filter(ShortTermRentalChannel.id != exclude_id)
    if query.first():
        raise HTTPException(status_code=409, detail="Channel label already exists for this provider on this property.")


def _price_item(
    db: Session,
    *,
    org_id: int,
    property_id: int,
    item_id: int,
) -> ShortTermRentalNightlyPrice:
    item = db.query(ShortTermRentalNightlyPrice).filter(
        ShortTermRentalNightlyPrice.id == item_id,
        ShortTermRentalNightlyPrice.organization_id == org_id,
        ShortTermRentalNightlyPrice.property_id == property_id,
        ShortTermRentalNightlyPrice.is_active.is_(True),
    ).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Recorded nightly price not found.")
    return item


def _price_unique(
    db: Session,
    *,
    org_id: int,
    property_id: int,
    unit_id: int,
    night_date,
    exclude_id: int | None = None,
) -> None:
    query = db.query(ShortTermRentalNightlyPrice.id).filter(
        ShortTermRentalNightlyPrice.organization_id == org_id,
        ShortTermRentalNightlyPrice.property_id == property_id,
        ShortTermRentalNightlyPrice.unit_id == unit_id,
        ShortTermRentalNightlyPrice.night_date == night_date,
    )
    if exclude_id is not None:
        query = query.filter(ShortTermRentalNightlyPrice.id != exclude_id)
    if query.first():
        raise HTTPException(status_code=409, detail="A nightly price already exists for this unit and date.")


@router.get(
    "/{property_id}/short-term-rentals/channels",
    response_model=list[ShortTermRentalChannelOut],
)
def list_channels(
    property_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id=property_id, actor=current_user, write=False)
    rows = db.query(ShortTermRentalChannel).filter(
        ShortTermRentalChannel.organization_id == prop.organization_id,
        ShortTermRentalChannel.property_id == prop.id,
        ShortTermRentalChannel.is_active.is_(True),
    ).order_by(
        ShortTermRentalChannel.provider.asc(),
        ShortTermRentalChannel.label.asc(),
        ShortTermRentalChannel.id.asc(),
    ).limit(MAX_CHANNELS + 1).all()
    if len(rows) > MAX_CHANNELS:
        raise HTTPException(status_code=422, detail="Too many recorded short-term rental channels.")
    response.headers["Cache-Control"] = "no-store"
    return rows


@router.post(
    "/{property_id}/short-term-rentals/channels",
    response_model=ShortTermRentalChannelOut,
    status_code=201,
)
def create_channel(
    property_id: int,
    payload: ShortTermRentalChannelIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id=property_id, actor=current_user, write=True)
    _unique(
        db,
        org_id=prop.organization_id,
        property_id=prop.id,
        provider=payload.provider,
        label=payload.label,
    )
    item = ShortTermRentalChannel(
        organization_id=prop.organization_id,
        property_id=prop.id,
        **payload.model_dump(),
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )
    db.add(item)
    try:
        db.flush()
        append_audit_log(
            db,
            organization_id=prop.organization_id,
            user_id=current_user.id,
            entity_type="short_term_rental_channel",
            entity_id=item.id,
            action="created",
            new_value={
                "property_id": prop.id,
                "provider": item.provider,
                "external_listing_id": item.external_listing_id,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Channel reference already exists on this property.") from exc
    db.refresh(item)
    return item


@router.put(
    "/{property_id}/short-term-rentals/channels/{item_id}",
    response_model=ShortTermRentalChannelOut,
)
def update_channel(
    property_id: int,
    item_id: int,
    payload: ShortTermRentalChannelIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id=property_id, actor=current_user, write=True)
    item = _item(
        db,
        org_id=prop.organization_id,
        property_id=prop.id,
        item_id=item_id,
    )
    _unique(
        db,
        org_id=prop.organization_id,
        property_id=prop.id,
        provider=payload.provider,
        label=payload.label,
        exclude_id=item.id,
    )
    old = {
        "provider": item.provider,
        "external_listing_id": item.external_listing_id,
    }
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    item.updated_by_id = current_user.id
    try:
        db.flush()
        append_audit_log(
            db,
            organization_id=prop.organization_id,
            user_id=current_user.id,
            entity_type="short_term_rental_channel",
            entity_id=item.id,
            action="updated",
            old_value=old,
            new_value={
                "provider": item.provider,
                "external_listing_id": item.external_listing_id,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Channel reference already exists on this property.") from exc
    db.refresh(item)
    return item


@router.delete(
    "/{property_id}/short-term-rentals/channels/{item_id}",
    status_code=204,
)
def archive_channel(
    property_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id=property_id, actor=current_user, write=True)
    item = _item(
        db,
        org_id=prop.organization_id,
        property_id=prop.id,
        item_id=item_id,
    )
    item.is_active = False
    item.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db,
        organization_id=prop.organization_id,
        user_id=current_user.id,
        entity_type="short_term_rental_channel",
        entity_id=item.id,
        action="archived",
        new_value={"property_id": prop.id, "provider": item.provider},
    )
    db.commit()
    return Response(status_code=204)


@router.get(
    "/{property_id}/short-term-rentals/nightly-prices",
    response_model=list[ShortTermRentalNightlyPriceOut],
)
def list_nightly_prices(
    property_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id=property_id, actor=current_user, write=False)
    rows = db.query(ShortTermRentalNightlyPrice).filter(
        ShortTermRentalNightlyPrice.organization_id == prop.organization_id,
        ShortTermRentalNightlyPrice.property_id == prop.id,
        ShortTermRentalNightlyPrice.is_active.is_(True),
    ).order_by(
        ShortTermRentalNightlyPrice.night_date.asc(),
        ShortTermRentalNightlyPrice.unit_id.asc(),
        ShortTermRentalNightlyPrice.id.asc(),
    ).limit(MAX_NIGHTLY_PRICES + 1).all()
    if len(rows) > MAX_NIGHTLY_PRICES:
        raise HTTPException(status_code=422, detail="Too many recorded nightly prices.")
    response.headers["Cache-Control"] = "no-store"
    return rows


@router.post(
    "/{property_id}/short-term-rentals/nightly-prices",
    response_model=ShortTermRentalNightlyPriceOut,
    status_code=201,
)
def create_nightly_price(
    property_id: int,
    payload: ShortTermRentalNightlyPriceIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id=property_id, actor=current_user, write=True)
    _active_unit(db, property_id=prop.id, unit_id=payload.unit_id)
    _price_unique(
        db,
        org_id=prop.organization_id,
        property_id=prop.id,
        unit_id=payload.unit_id,
        night_date=payload.night_date,
    )
    item = ShortTermRentalNightlyPrice(
        organization_id=prop.organization_id,
        property_id=prop.id,
        **payload.model_dump(),
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )
    db.add(item)
    try:
        db.flush()
        append_audit_log(
            db,
            organization_id=prop.organization_id,
            user_id=current_user.id,
            entity_type="short_term_rental_nightly_price",
            entity_id=item.id,
            action="created",
            new_value={
                "property_id": prop.id,
                "unit_id": item.unit_id,
                "night_date": str(item.night_date),
                "nightly_rate": str(item.nightly_rate),
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Nightly price already exists for this unit and date.") from exc
    db.refresh(item)
    return item


@router.put(
    "/{property_id}/short-term-rentals/nightly-prices/{item_id}",
    response_model=ShortTermRentalNightlyPriceOut,
)
def update_nightly_price(
    property_id: int,
    item_id: int,
    payload: ShortTermRentalNightlyPriceIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id=property_id, actor=current_user, write=True)
    item = _price_item(
        db,
        org_id=prop.organization_id,
        property_id=prop.id,
        item_id=item_id,
    )
    _active_unit(db, property_id=prop.id, unit_id=payload.unit_id)
    _price_unique(
        db,
        org_id=prop.organization_id,
        property_id=prop.id,
        unit_id=payload.unit_id,
        night_date=payload.night_date,
        exclude_id=item.id,
    )
    old = {
        "unit_id": item.unit_id,
        "night_date": str(item.night_date),
        "nightly_rate": str(item.nightly_rate),
    }
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    item.updated_by_id = current_user.id
    try:
        db.flush()
        append_audit_log(
            db,
            organization_id=prop.organization_id,
            user_id=current_user.id,
            entity_type="short_term_rental_nightly_price",
            entity_id=item.id,
            action="updated",
            old_value=old,
            new_value={
                "unit_id": item.unit_id,
                "night_date": str(item.night_date),
                "nightly_rate": str(item.nightly_rate),
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Nightly price already exists for this unit and date.") from exc
    db.refresh(item)
    return item


@router.delete(
    "/{property_id}/short-term-rentals/nightly-prices/{item_id}",
    status_code=204,
)
def archive_nightly_price(
    property_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id=property_id, actor=current_user, write=True)
    item = _price_item(
        db,
        org_id=prop.organization_id,
        property_id=prop.id,
        item_id=item_id,
    )
    item.is_active = False
    item.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db,
        organization_id=prop.organization_id,
        user_id=current_user.id,
        entity_type="short_term_rental_nightly_price",
        entity_id=item.id,
        action="archived",
        new_value={
            "property_id": prop.id,
            "unit_id": item.unit_id,
            "night_date": str(item.night_date),
        },
    )
    db.commit()
    return Response(status_code=204)
