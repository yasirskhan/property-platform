"""Phase 4 customer vendor companies, distinct from vendor login users."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.routers.auth import get_current_user
from app.schemas.vendor import VendorCreate, VendorFields, VendorListOut, VendorOut, VendorUpdate
from app.services.audit import append_audit_log
from app.services.menu_resolver import permission_allows_user

router = APIRouter(prefix="/api/vendors", tags=["Vendor Companies"])


def _access(db: Session, user: User, *, write: bool = False) -> int:
    if (
        user.organization_id is None or not user.is_active
        or user.deleted_at is not None
        or user.role not in ({UserRole.ADMIN} if write else {UserRole.ADMIN, UserRole.OWNER})
        or not permission_allows_user(db, user=user, menu_key="PEOPLE.VENDORS")
    ):
        raise HTTPException(status_code=403, detail="Vendor management permission required.")
    return int(user.organization_id)


def _contact(db: Session, *, organization_id: int, user_id: int | None) -> None:
    if user_id is None:
        return
    contact = db.query(User).filter(
        User.id == user_id, User.organization_id == organization_id,
        User.role == UserRole.VENDOR, User.is_active.is_(True),
        User.deleted_at.is_(None),
    ).first()
    if contact is None:
        raise HTTPException(status_code=404, detail="Vendor contact not found.")


def _row(db: Session, *, organization_id: int, vendor_id: int) -> Vendor:
    row = db.query(Vendor).filter(
        Vendor.id == vendor_id, Vendor.organization_id == organization_id,
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Vendor company not found.")
    return row


@router.get("", response_model=VendorListOut)
def list_vendors(
    response: Response,
    search: str | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _access(db, current_user)
    response.headers["Cache-Control"] = "no-store"
    if search is not None and len(search) > 100:
        raise HTTPException(status_code=422, detail="Vendor search is too long.")
    q = db.query(Vendor).filter(Vendor.organization_id == organization_id)
    if not include_inactive:
        q = q.filter(Vendor.is_active.is_(True), Vendor.deleted_at.is_(None))
    if search and search.strip():
        q = q.filter(Vendor.company_name.ilike(f"%{search.strip()}%"))
    rows = q.order_by(Vendor.company_name.asc(), Vendor.id.asc()).limit(1001).all()
    if len(rows) > 1000:
        raise HTTPException(status_code=422, detail="Narrow vendor search before listing.")
    return VendorListOut(
        items=[VendorOut.model_validate(row) for row in rows],
        total=len(rows),
    )


@router.get("/{vendor_id}", response_model=VendorOut)
def get_vendor(
    vendor_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _access(db, current_user)
    response.headers["Cache-Control"] = "no-store"
    return _row(db, organization_id=org_id, vendor_id=vendor_id)


@router.post("", response_model=VendorOut, status_code=201)
def create_vendor(
    payload: VendorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _access(db, current_user, write=True)
    _contact(db, organization_id=org_id, user_id=payload.contact_user_id)
    row = Vendor(
        organization_id=org_id, created_by_id=current_user.id,
        updated_by_id=current_user.id, **payload.model_dump(),
    )
    db.add(row)
    db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=org_id,
        entity_type="vendor", entity_id=row.id, action="created",
        new_value={"company_name": row.company_name},
    )
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{vendor_id}", response_model=VendorOut)
def update_vendor(
    vendor_id: int,
    payload: VendorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _access(db, current_user, write=True)
    row = _row(db, organization_id=org_id, vendor_id=vendor_id)
    if not row.is_active or row.deleted_at is not None:
        raise HTTPException(status_code=409, detail="Restore vendor before editing.")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="No vendor changes supplied.")
    if "company_name" in changes and changes["company_name"] is None:
        raise HTTPException(status_code=422, detail="Vendor company name is required.")
    if "contact_user_id" in changes:
        _contact(db, organization_id=org_id, user_id=changes["contact_user_id"])
    modified = {}
    for key, value in changes.items():
        if getattr(row, key) != value:
            modified[key] = (getattr(row, key), value)
            setattr(row, key, value)
    if not modified:
        return row
    row.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=org_id,
        entity_type="vendor", entity_id=row.id, action="updated",
        field_name=",".join(sorted(modified))[:100],
        new_value={"changed_fields": sorted(modified)},
    )
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{vendor_id}", status_code=204)
def delete_vendor(
    vendor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _access(db, current_user, write=True)
    row = _row(db, organization_id=org_id, vendor_id=vendor_id)
    if row.is_active and row.deleted_at is None:
        row.is_active = False
        row.deleted_at = datetime.utcnow()
        row.updated_by_id = current_user.id
        db.flush()
        append_audit_log(
            db, user_id=current_user.id, organization_id=org_id,
            entity_type="vendor", entity_id=row.id, action="deactivated",
        )
        db.commit()
    return Response(status_code=204)


@router.post("/{vendor_id}/restore", response_model=VendorOut)
def restore_vendor(
    vendor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _access(db, current_user, write=True)
    row = _row(db, organization_id=org_id, vendor_id=vendor_id)
    if not row.is_active or row.deleted_at is not None:
        row.is_active = True
        row.deleted_at = None
        row.updated_by_id = current_user.id
        db.flush()
        append_audit_log(
            db, user_id=current_user.id, organization_id=org_id,
            entity_type="vendor", entity_id=row.id, action="restored",
        )
        db.commit()
    db.refresh(row)
    return row
