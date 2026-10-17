"""Authorized draft lease templates and ordered addenda.

Documents are ordinary universal entity attachments linked to
lease_templates or lease_template_addenda; no duplicate storage.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.lease_template import LeaseTemplate, LeaseTemplateAddendum
from app.models.property import Property, PropertyAssignment
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.lease_template import TemplateIn, TemplateOut, AddendumIn, AddendumOut
from app.services.audit import append_audit_log
from app.services.letters import validate_letter
from app.services.menu_resolver import permission_allows_user

router = APIRouter(prefix="/api/leasing/templates", tags=["Lease Templates"])


def _access(db: Session, user: User, *, write: bool = False) -> int:
    roles = {UserRole.ADMIN} if write else {UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER}
    if (user.organization_id is None or not user.is_active or user.deleted_at is not None
            or user.role not in roles
            or not permission_allows_user(db, user=user, menu_key="LEASING.TEMPLATES")):
        raise HTTPException(status_code=403, detail="Lease template permission required.")
    return int(user.organization_id)


def _property(db: Session, user: User, org: int, property_id: int | None) -> None:
    if property_id is None:
        return
    target = db.query(Property.id).filter(
        Property.id == property_id, Property.organization_id == org,
        Property.is_active.is_(True), Property.deleted_at.is_(None),
    ).first()
    if target is None:
        raise HTTPException(status_code=404, detail="Property not found.")
    if user.role == UserRole.MANAGER and not db.query(PropertyAssignment.id).filter(
        PropertyAssignment.property_id == property_id,
        PropertyAssignment.user_id == user.id,
        PropertyAssignment.is_active.is_(True),
        PropertyAssignment.deleted_at.is_(None),
    ).first():
        raise HTTPException(status_code=404, detail="Property not found.")


def _visible(db: Session, user: User, org: int):
    query = db.query(LeaseTemplate).filter(
        LeaseTemplate.organization_id == org,
        LeaseTemplate.is_active.is_(True),
    )
    if user.role == UserRole.MANAGER:
        permitted = db.query(PropertyAssignment.property_id).filter(
            PropertyAssignment.user_id == user.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        query = query.filter(or_(
            LeaseTemplate.property_id.is_(None),
            LeaseTemplate.property_id.in_(permitted),
        ))
    return query


def _template(db: Session, user: User, template_id: int, *, write: bool = False):
    org = _access(db, user, write=write)
    row = _visible(db, user, org).filter(LeaseTemplate.id == template_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Lease template not found.")
    return row


def _addendum(db: Session, *, template_id: int, addendum_id: int, org: int):
    row = db.query(LeaseTemplateAddendum).filter(
        LeaseTemplateAddendum.id == addendum_id,
        LeaseTemplateAddendum.template_id == template_id,
        LeaseTemplateAddendum.organization_id == org,
        LeaseTemplateAddendum.is_active.is_(True),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Addendum not found.")
    return row


def _out(db: Session, row: LeaseTemplate):
    addenda = db.query(LeaseTemplateAddendum).filter(
        LeaseTemplateAddendum.template_id == row.id,
        LeaseTemplateAddendum.organization_id == row.organization_id,
        LeaseTemplateAddendum.is_active.is_(True),
    ).order_by(LeaseTemplateAddendum.position, LeaseTemplateAddendum.id).all()
    return TemplateOut(
        id=row.id, organization_id=row.organization_id,
        title=row.title, body=row.body, property_id=row.property_id,
        created_at=row.created_at, updated_at=row.updated_at,
        addenda=[AddendumOut(
            id=a.id, template_id=a.template_id, title=a.title, body=a.body,
            position=a.position, created_at=a.created_at, updated_at=a.updated_at,
        ) for a in addenda],
    )


def _validate(title: str, body: str):
    # Reuse the existing plain-text, allowlisted mail-merge validator.
    # These are drafts and are NOT automatically merged or signed.
    validate_letter(title, body)


@router.get("", response_model=list[TemplateOut])
def list_lease_templates(
    response: Response, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = _access(db, current_user)
    response.headers["Cache-Control"] = "no-store"
    rows = _visible(db, current_user, org).order_by(LeaseTemplate.id).limit(201).all()
    if len(rows) > 200:
        raise HTTPException(status_code=422, detail="Narrow lease template list.")
    return [_out(db, row) for row in rows]


@router.post("", response_model=TemplateOut, status_code=201)
def create_lease_template(
    payload: TemplateIn, response: Response, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = _access(db, current_user, write=True)
    _property(db, current_user, org, payload.property_id)
    _validate(payload.title, payload.body)
    row = LeaseTemplate(
        organization_id=org, property_id=payload.property_id,
        title=payload.title, body=payload.body,
        created_by_id=current_user.id, updated_by_id=current_user.id,
    )
    db.add(row); db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=org,
        entity_type="lease_template", entity_id=row.id, action="created",
        new_value={"property_id": row.property_id},
    )
    db.commit(); db.refresh(row)
    response.headers["Cache-Control"] = "no-store"
    return _out(db, row)


@router.get("/{template_id}", response_model=TemplateOut)
def get_lease_template(
    template_id: int, response: Response, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = _template(db, current_user, template_id)
    response.headers["Cache-Control"] = "no-store"
    return _out(db, row)


@router.put("/{template_id}", response_model=TemplateOut)
def edit_lease_template(
    template_id: int, payload: TemplateIn, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    row = _template(db, current_user, template_id, write=True)
    if payload.property_id != row.property_id:
        raise HTTPException(status_code=409, detail="Template property scope cannot be changed.")
    _validate(payload.title, payload.body)
    row.title, row.body, row.updated_by_id = payload.title, payload.body, current_user.id
    db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=row.organization_id,
        entity_type="lease_template", entity_id=row.id, action="updated",
        new_value={"property_id": row.property_id},
    )
    db.commit(); db.refresh(row)
    response.headers["Cache-Control"] = "no-store"
    return _out(db, row)


@router.delete("/{template_id}", status_code=204)
def deactivate_lease_template(
    template_id: int, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = _template(db, current_user, template_id, write=True)
    row.is_active = False
    append_audit_log(
        db, user_id=current_user.id, organization_id=row.organization_id,
        entity_type="lease_template", entity_id=row.id, action="deactivated",
    )
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.post("/{template_id}/addenda", response_model=AddendumOut, status_code=201)
def create_lease_addendum(
    template_id: int, payload: AddendumIn, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    parent = _template(db, current_user, template_id, write=True)
    _validate(payload.title, payload.body)
    row = LeaseTemplateAddendum(
        template_id=parent.id, organization_id=parent.organization_id,
        property_id=parent.property_id, title=payload.title, body=payload.body,
        position=payload.position, created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )
    db.add(row); db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=parent.organization_id,
        entity_type="lease_template_addendum", entity_id=row.id, action="created",
        new_value={"template_id": parent.id, "position": row.position},
    )
    db.commit(); db.refresh(row)
    response.headers["Cache-Control"] = "no-store"
    return AddendumOut(
        id=row.id, template_id=row.template_id, title=row.title, body=row.body,
        position=row.position, created_at=row.created_at, updated_at=row.updated_at,
    )


@router.put("/{template_id}/addenda/{addendum_id}", response_model=AddendumOut)
def edit_lease_addendum(
    template_id: int, addendum_id: int, payload: AddendumIn, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    parent = _template(db, current_user, template_id, write=True)
    row = _addendum(db, template_id=parent.id, addendum_id=addendum_id,
                    org=parent.organization_id)
    _validate(payload.title, payload.body)
    row.title, row.body, row.position = payload.title, payload.body, payload.position
    row.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=parent.organization_id,
        entity_type="lease_template_addendum", entity_id=row.id, action="updated",
        new_value={"template_id": parent.id, "position": row.position},
    )
    db.commit(); db.refresh(row)
    response.headers["Cache-Control"] = "no-store"
    return AddendumOut(
        id=row.id, template_id=row.template_id, title=row.title, body=row.body,
        position=row.position, created_at=row.created_at, updated_at=row.updated_at,
    )


@router.delete("/{template_id}/addenda/{addendum_id}", status_code=204)
def delete_lease_addendum(
    template_id: int, addendum_id: int,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    parent = _template(db, current_user, template_id, write=True)
    row = _addendum(db, template_id=parent.id, addendum_id=addendum_id,
                    org=parent.organization_id)
    row.is_active = False
    append_audit_log(
        db, user_id=current_user.id, organization_id=parent.organization_id,
        entity_type="lease_template_addendum", entity_id=row.id, action="deactivated",
    )
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
