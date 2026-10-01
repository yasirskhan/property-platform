"""Phase 4.11 Senior Housing age-restriction registry.

Staff-recorded facts only: no resident eligibility inference, Fair Housing/HOPA
certification, HUD program determination, charge creation, or GL posting.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.property import Property, PropertyAssignment
from app.models.senior_housing import SeniorAgeRestriction, SeniorCareResource
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.senior_housing import (
    SeniorAgeRestrictionIn,
    SeniorAgeRestrictionOut,
    SeniorCareResourceIn,
    SeniorCareResourceOut,
)
from app.services.audit import append_audit_log
from app.services.customer_features import resolve_customer_features
from app.services.menu_resolver import permission_allows_user


router = APIRouter(prefix="/api/properties", tags=["Senior housing"])
FEATURE_KEY = "release.properties.senior_housing"
MAX_RESTRICTIONS = 100
MAX_CARE_RESOURCES = 200


def _property(db: Session, *, property_id: int, actor: User, write: bool) -> Property:
    if (
        actor.organization_id is None
        or not actor.is_active
        or actor.deleted_at is not None
        or actor.role not in {UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER}
        or (write and actor.role not in {UserRole.ADMIN, UserRole.OWNER})
        or not permission_allows_user(db, user=actor, menu_key="PROPERTIES.ALL")
    ):
        raise HTTPException(status_code=403, detail="Senior housing property access required.")
    decision = next(
        (item for item in resolve_customer_features(db, user=actor) if item.key == FEATURE_KEY),
        None,
    )
    if decision is None or not decision.allowed:
        raise HTTPException(status_code=404, detail="Senior housing is not available.")
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


def _item(db: Session, *, org_id: int, property_id: int, item_id: int) -> SeniorAgeRestriction:
    item = db.query(SeniorAgeRestriction).filter(
        SeniorAgeRestriction.id == item_id,
        SeniorAgeRestriction.organization_id == org_id,
        SeniorAgeRestriction.property_id == property_id,
        SeniorAgeRestriction.is_active.is_(True),
    ).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Recorded age restriction not found.")
    return item


def _unique(db: Session, *, org_id: int, property_id: int, label: str, exclude_id: int | None = None) -> None:
    query = db.query(SeniorAgeRestriction.id).filter(
        SeniorAgeRestriction.organization_id == org_id,
        SeniorAgeRestriction.property_id == property_id,
        SeniorAgeRestriction.label == label,
    )
    if exclude_id is not None:
        query = query.filter(SeniorAgeRestriction.id != exclude_id)
    if query.first():
        raise HTTPException(status_code=409, detail="Restriction label already exists on this property.")


@router.get("/{property_id}/senior-housing/age-restrictions", response_model=list[SeniorAgeRestrictionOut])
def list_age_restrictions(
    property_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id=property_id, actor=current_user, write=False)
    rows = db.query(SeniorAgeRestriction).filter(
        SeniorAgeRestriction.organization_id == prop.organization_id,
        SeniorAgeRestriction.property_id == prop.id,
        SeniorAgeRestriction.is_active.is_(True),
    ).order_by(SeniorAgeRestriction.label.asc(), SeniorAgeRestriction.id.asc()).limit(MAX_RESTRICTIONS + 1).all()
    if len(rows) > MAX_RESTRICTIONS:
        raise HTTPException(status_code=422, detail="Too many recorded age restrictions.")
    response.headers["Cache-Control"] = "no-store"
    return rows


@router.post("/{property_id}/senior-housing/age-restrictions", response_model=SeniorAgeRestrictionOut, status_code=201)
def create_age_restriction(
    property_id: int,
    payload: SeniorAgeRestrictionIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id=property_id, actor=current_user, write=True)
    _unique(db, org_id=prop.organization_id, property_id=prop.id, label=payload.label)
    item = SeniorAgeRestriction(
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
            entity_type="senior_age_restriction",
            entity_id=item.id,
            action="created",
            new_value={"property_id": prop.id, "restriction_type": item.restriction_type, "minimum_age": item.minimum_age},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Restriction label already exists on this property.") from exc
    db.refresh(item)
    return item


@router.put("/{property_id}/senior-housing/age-restrictions/{item_id}", response_model=SeniorAgeRestrictionOut)
def update_age_restriction(
    property_id: int,
    item_id: int,
    payload: SeniorAgeRestrictionIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id=property_id, actor=current_user, write=True)
    item = _item(db, org_id=prop.organization_id, property_id=prop.id, item_id=item_id)
    _unique(db, org_id=prop.organization_id, property_id=prop.id, label=payload.label, exclude_id=item.id)
    old = {"restriction_type": item.restriction_type, "minimum_age": item.minimum_age}
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    item.updated_by_id = current_user.id
    try:
        db.flush()
        append_audit_log(
            db,
            organization_id=prop.organization_id,
            user_id=current_user.id,
            entity_type="senior_age_restriction",
            entity_id=item.id,
            action="updated",
            old_value=old,
            new_value={"restriction_type": item.restriction_type, "minimum_age": item.minimum_age},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Restriction label already exists on this property.") from exc
    db.refresh(item)
    return item


@router.delete("/{property_id}/senior-housing/age-restrictions/{item_id}", status_code=204)
def archive_age_restriction(
    property_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id=property_id, actor=current_user, write=True)
    item = _item(db, org_id=prop.organization_id, property_id=prop.id, item_id=item_id)
    item.is_active = False
    item.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db,
        organization_id=prop.organization_id,
        user_id=current_user.id,
        entity_type="senior_age_restriction",
        entity_id=item.id,
        action="archived",
        new_value={"property_id": prop.id, "restriction_type": item.restriction_type},
    )
    db.commit()
    return Response(status_code=204)



def _care_item(db: Session, *, org_id: int, property_id: int, item_id: int) -> SeniorCareResource:
    item = db.query(SeniorCareResource).filter(
        SeniorCareResource.id == item_id,
        SeniorCareResource.organization_id == org_id,
        SeniorCareResource.property_id == property_id,
        SeniorCareResource.is_active.is_(True),
    ).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Recorded care resource not found.")
    return item


def _care_unique(
    db: Session,
    *,
    org_id: int,
    property_id: int,
    resource_type: str,
    provider_name: str,
    exclude_id: int | None = None,
) -> None:
    query = db.query(SeniorCareResource.id).filter(
        SeniorCareResource.organization_id == org_id,
        SeniorCareResource.property_id == property_id,
        SeniorCareResource.resource_type == resource_type,
        SeniorCareResource.provider_name == provider_name,
    )
    if exclude_id is not None:
        query = query.filter(SeniorCareResource.id != exclude_id)
    if query.first():
        raise HTTPException(status_code=409, detail="Care resource is already recorded for this property.")


@router.get(
    "/{property_id}/senior-housing/care-resources",
    response_model=list[SeniorCareResourceOut],
)
def list_care_resources(
    property_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id=property_id, actor=current_user, write=False)
    rows = db.query(SeniorCareResource).filter(
        SeniorCareResource.organization_id == prop.organization_id,
        SeniorCareResource.property_id == prop.id,
        SeniorCareResource.is_active.is_(True),
    ).order_by(
        SeniorCareResource.resource_type.asc(),
        SeniorCareResource.provider_name.asc(),
        SeniorCareResource.id.asc(),
    ).limit(MAX_CARE_RESOURCES + 1).all()
    if len(rows) > MAX_CARE_RESOURCES:
        raise HTTPException(status_code=422, detail="Too many recorded care resources.")
    response.headers["Cache-Control"] = "no-store"
    return rows


@router.post(
    "/{property_id}/senior-housing/care-resources",
    response_model=SeniorCareResourceOut,
    status_code=201,
)
def create_care_resource(
    property_id: int,
    payload: SeniorCareResourceIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id=property_id, actor=current_user, write=True)
    _care_unique(
        db,
        org_id=prop.organization_id,
        property_id=prop.id,
        resource_type=payload.resource_type,
        provider_name=payload.provider_name,
    )
    item = SeniorCareResource(
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
            entity_type="senior_care_resource",
            entity_id=item.id,
            action="created",
            new_value={
                "property_id": prop.id,
                "resource_type": item.resource_type,
                "provider_name": item.provider_name,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Care resource is already recorded for this property.") from exc
    db.refresh(item)
    return item


@router.put(
    "/{property_id}/senior-housing/care-resources/{item_id}",
    response_model=SeniorCareResourceOut,
)
def update_care_resource(
    property_id: int,
    item_id: int,
    payload: SeniorCareResourceIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id=property_id, actor=current_user, write=True)
    item = _care_item(
        db,
        org_id=prop.organization_id,
        property_id=prop.id,
        item_id=item_id,
    )
    _care_unique(
        db,
        org_id=prop.organization_id,
        property_id=prop.id,
        resource_type=payload.resource_type,
        provider_name=payload.provider_name,
        exclude_id=item.id,
    )
    old = {"resource_type": item.resource_type, "provider_name": item.provider_name}
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    item.updated_by_id = current_user.id
    try:
        db.flush()
        append_audit_log(
            db,
            organization_id=prop.organization_id,
            user_id=current_user.id,
            entity_type="senior_care_resource",
            entity_id=item.id,
            action="updated",
            old_value=old,
            new_value={
                "resource_type": item.resource_type,
                "provider_name": item.provider_name,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Care resource is already recorded for this property.") from exc
    db.refresh(item)
    return item


@router.delete(
    "/{property_id}/senior-housing/care-resources/{item_id}",
    status_code=204,
)
def archive_care_resource(
    property_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id=property_id, actor=current_user, write=True)
    item = _care_item(
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
        entity_type="senior_care_resource",
        entity_id=item.id,
        action="archived",
        new_value={
            "property_id": prop.id,
            "resource_type": item.resource_type,
            "provider_name": item.provider_name,
        },
    )
    db.commit()
    return Response(status_code=204)
