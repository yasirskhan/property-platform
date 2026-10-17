"""Bounded affordable-program registry; NOT HUD eligibility, AMI or HAP billing."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.affordable_program import AffordableProgram
from app.models.property import Property, PropertyAssignment
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.affordable_program import AffordableProgramIn, AffordableProgramOut
from app.services.audit import append_audit_log
from app.services.customer_features import resolve_customer_features
from app.services.menu_resolver import permission_allows_user

router = APIRouter(prefix="/api/properties", tags=["Affordable program inventory"])
FEATURE_KEY = "release.properties.compliance"


def _property(db: Session, *, property_id: int, actor: User, write: bool) -> Property:
    if (
        actor.organization_id is None or not actor.is_active
        or actor.deleted_at is not None
        or actor.role not in {UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER}
        or (write and actor.role not in {UserRole.ADMIN, UserRole.OWNER})
        or not permission_allows_user(db, user=actor, menu_key="PROPERTIES.ALL")
    ):
        raise HTTPException(status_code=403, detail="Property compliance access required.")
    decision = next(
        (item for item in resolve_customer_features(db, user=actor) if item.key == FEATURE_KEY),
        None,
    )
    if decision is None or not decision.allowed:
        raise HTTPException(status_code=404, detail="Property compliance is unavailable.")
    prop = db.query(Property).filter(
        Property.id == property_id, Property.organization_id == actor.organization_id,
        Property.is_active.is_(True), Property.deleted_at.is_(None),
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


def _item(db: Session, *, org_id: int, prop_id: int, item_id: int) -> AffordableProgram:
    item = db.query(AffordableProgram).filter(
        AffordableProgram.id == item_id, AffordableProgram.organization_id == org_id,
        AffordableProgram.property_id == prop_id, AffordableProgram.is_active.is_(True),
    ).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Recorded program not found.")
    return item


def _unique(db: Session, *, org_id: int, prop_id: int, label: str, exclude_id: int | None = None) -> None:
    query = db.query(AffordableProgram.id).filter(
        AffordableProgram.organization_id == org_id, AffordableProgram.property_id == prop_id,
        AffordableProgram.label == label,
    )
    if exclude_id is not None:
        query = query.filter(AffordableProgram.id != exclude_id)
    if query.first():
        raise HTTPException(status_code=409, detail="Program label already exists on this property.")


@router.get("/{property_id}/affordable-programs", response_model=list[AffordableProgramOut])
def list_programs(
    property_id: int, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id=property_id, actor=current_user, write=False)
    response.headers["Cache-Control"] = "no-store"
    return db.query(AffordableProgram).filter(
        AffordableProgram.organization_id == prop.organization_id,
        AffordableProgram.property_id == prop.id, AffordableProgram.is_active.is_(True),
    ).order_by(AffordableProgram.label, AffordableProgram.id).limit(101).all()


@router.post("/{property_id}/affordable-programs", response_model=AffordableProgramOut, status_code=201)
def create_program(
    property_id: int, payload: AffordableProgramIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id=property_id, actor=current_user, write=True)
    _unique(db, org_id=prop.organization_id, prop_id=prop.id, label=payload.label)
    item = AffordableProgram(
        organization_id=prop.organization_id, property_id=prop.id,
        **payload.model_dump(), created_by_id=current_user.id, updated_by_id=current_user.id,
    )
    db.add(item)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=prop.organization_id, user_id=current_user.id,
            entity_type="affordable_program", entity_id=item.id, action="created",
            new_value={"property_id": prop.id, "program_type": item.program_type},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Program label already exists on this property.") from exc
    db.refresh(item)
    return item


@router.put("/{property_id}/affordable-programs/{item_id}", response_model=AffordableProgramOut)
def update_program(
    property_id: int, item_id: int, payload: AffordableProgramIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id=property_id, actor=current_user, write=True)
    item = _item(db, org_id=prop.organization_id, prop_id=prop.id, item_id=item_id)
    _unique(db, org_id=prop.organization_id, prop_id=prop.id, label=payload.label, exclude_id=item.id)
    old_type = item.program_type
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    item.updated_by_id = current_user.id
    try:
        db.flush()
        append_audit_log(
            db, organization_id=prop.organization_id, user_id=current_user.id,
            entity_type="affordable_program", entity_id=item.id, action="updated",
            old_value={"program_type": old_type},
            new_value={"program_type": item.program_type},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Program label already exists on this property.") from exc
    db.refresh(item)
    return item


@router.delete("/{property_id}/affordable-programs/{item_id}", status_code=204)
def archive_program(
    property_id: int, item_id: int,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id=property_id, actor=current_user, write=True)
    item = _item(db, org_id=prop.organization_id, prop_id=prop.id, item_id=item_id)
    item.is_active = False
    item.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db, organization_id=prop.organization_id, user_id=current_user.id,
        entity_type="affordable_program", entity_id=item.id, action="archived",
        new_value={"property_id": prop.id, "program_type": item.program_type},
    )
    db.commit()
    return Response(status_code=204)
