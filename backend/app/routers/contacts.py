"""Phase 4 organization-owned contacts; separate from login users and Vendor companies."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import or_

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.contact import Contact
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.contact import ContactCreate, ContactListOut, ContactOut, ContactUpdate
from app.services.audit import append_audit_log
from app.services.menu_resolver import permission_allows_user

router = APIRouter(prefix="/api/contacts", tags=["Contacts"])


def _require_access(db: Session, user: User, *, write: bool = False) -> int:
    if (
        user.organization_id is None
        or not user.is_active or user.deleted_at is not None
        or user.role not in ({UserRole.ADMIN} if write else {UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER})
        or not permission_allows_user(db, user=user, menu_key="PEOPLE.CONTACTS")
    ):
        raise HTTPException(status_code=403, detail="Contacts permission required.")
    return int(user.organization_id)


def _contact(db: Session, *, organization_id: int, contact_id: int) -> Contact:
    row = db.query(Contact).filter(
        Contact.id == contact_id, Contact.organization_id == organization_id,
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Contact not found.")
    return row


@router.get("", response_model=ContactListOut)
def list_contacts(
    response: Response,
    search: str | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_access(db, current_user)
    response.headers["Cache-Control"] = "no-store"
    if search is not None and len(search) > 100:
        raise HTTPException(status_code=422, detail="Contact search is too long.")
    q = db.query(Contact).filter(Contact.organization_id == org_id)
    if not include_inactive:
        q = q.filter(Contact.is_active.is_(True), Contact.deleted_at.is_(None))
    if search and search.strip():
        term = f"%{search.strip()}%"
        q = q.filter(or_(
            Contact.display_name.ilike(term),
            Contact.company_name.ilike(term),
            Contact.email.ilike(term),
        ))
    rows = q.order_by(Contact.display_name.asc(), Contact.id.asc()).limit(1001).all()
    if len(rows) > 1000:
        raise HTTPException(status_code=422, detail="Narrow contact search before listing.")
    return ContactListOut(items=rows, total=len(rows))


@router.get("/{contact_id}", response_model=ContactOut)
def get_contact(
    contact_id: int, response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_access(db, current_user)
    response.headers["Cache-Control"] = "no-store"
    return _contact(db, organization_id=org_id, contact_id=contact_id)


@router.post("", response_model=ContactOut, status_code=201)
def create_contact(
    payload: ContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_access(db, current_user, write=True)
    row = Contact(
        organization_id=org_id, created_by_id=current_user.id,
        updated_by_id=current_user.id, **payload.model_dump(),
    )
    db.add(row)
    db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=org_id,
        entity_type="contact", entity_id=row.id, action="created",
        new_value={"contact_type": row.contact_type},
    )
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{contact_id}", response_model=ContactOut)
def update_contact(
    contact_id: int, payload: ContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_access(db, current_user, write=True)
    row = _contact(db, organization_id=org_id, contact_id=contact_id)
    if not row.is_active or row.deleted_at is not None:
        raise HTTPException(status_code=409, detail="Restore contact before editing.")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="No contact changes supplied.")
    if changes.get("display_name", row.display_name) is None or changes.get("contact_type", row.contact_type) is None:
        raise HTTPException(status_code=422, detail="Name and contact type are required.")
    changed = []
    for field, value in changes.items():
        if getattr(row, field) != value:
            setattr(row, field, value)
            changed.append(field)
    if not changed:
        return row
    row.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=org_id,
        entity_type="contact", entity_id=row.id, action="updated",
        field_name=",".join(sorted(changed))[:100],
        new_value={"changed_fields": sorted(changed)},
    )
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{contact_id}", status_code=204)
def deactivate_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_access(db, current_user, write=True)
    row = _contact(db, organization_id=org_id, contact_id=contact_id)
    if row.is_active and row.deleted_at is None:
        row.is_active = False
        row.deleted_at = datetime.utcnow()
        row.updated_by_id = current_user.id
        db.flush()
        append_audit_log(
            db, user_id=current_user.id, organization_id=org_id,
            entity_type="contact", entity_id=row.id, action="deactivated",
        )
        db.commit()
    return Response(status_code=204)


@router.post("/{contact_id}/restore", response_model=ContactOut)
def restore_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_access(db, current_user, write=True)
    row = _contact(db, organization_id=org_id, contact_id=contact_id)
    if not row.is_active or row.deleted_at is not None:
        row.is_active = True
        row.deleted_at = None
        row.updated_by_id = current_user.id
        db.flush()
        append_audit_log(
            db, user_id=current_user.id, organization_id=org_id,
            entity_type="contact", entity_id=row.id, action="restored",
        )
        db.commit()
    db.refresh(row)
    return row
