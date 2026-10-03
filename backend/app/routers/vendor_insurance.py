"""Vendor-policy expiry tracking; no premium posting or settlement inference."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.vendor_insurance import VendorInsurance
from app.routers.auth import get_current_user
from app.routers.vendors import _access, _row
from app.schemas.vendor_insurance import (
    VendorInsuranceCreate, VendorInsuranceListOut,
    VendorInsuranceOut, VendorInsuranceUpdate,
)
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/vendors", tags=["Vendor Insurance"])


def _vendor(db: Session, user: User, vendor_id: int, *, write: bool = False):
    org_id = _access(db, user, write=write)
    vendor = _row(db, organization_id=org_id, vendor_id=vendor_id)
    if write and (not vendor.is_active or vendor.deleted_at is not None):
        raise HTTPException(status_code=409, detail="Restore vendor company before updating insurance.")
    return org_id, vendor


def _policy(db: Session, org_id: int, vendor_id: int, policy_id: int) -> VendorInsurance:
    row = db.query(VendorInsurance).filter(
        VendorInsurance.id == policy_id,
        VendorInsurance.vendor_id == vendor_id,
        VendorInsurance.organization_id == org_id,
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Vendor insurance not found.")
    return row


def _status(row: VendorInsurance, as_of: date) -> str:
    if not row.is_active or row.deleted_at is not None:
        return "INACTIVE"
    if row.effective_date and row.effective_date > as_of:
        return "UPCOMING"
    if row.expiration_date < as_of:
        return "EXPIRED"
    if row.expiration_date <= as_of + timedelta(days=min(30, (date.max - as_of).days)):
        return "EXPIRING_30_DAYS"
    return "CURRENT"


def _out(row: VendorInsurance, as_of: date) -> VendorInsuranceOut:
    payload = VendorInsuranceOut.model_validate(
        {**{key: getattr(row, key) for key in (
            "id", "vendor_id", "carrier", "coverage_type",
            "policy_number", "coverage_amount", "effective_date",
            "expiration_date", "is_active", "created_at", "updated_at",
        )}, "status": _status(row, as_of)}
    )
    return payload


@router.get("/{vendor_id}/insurance", response_model=VendorInsuranceListOut)
def list_vendor_insurance(
    vendor_id: int,
    response: Response,
    as_of: date | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id, _ = _vendor(db, current_user, vendor_id)
    response.headers["Cache-Control"] = "no-store"
    q = db.query(VendorInsurance).filter(
        VendorInsurance.organization_id == org_id,
        VendorInsurance.vendor_id == vendor_id,
    )
    if not include_inactive:
        q = q.filter(VendorInsurance.is_active.is_(True), VendorInsurance.deleted_at.is_(None))
    rows = q.order_by(VendorInsurance.expiration_date.asc(), VendorInsurance.id.asc()).limit(1001).all()
    if len(rows) > 1000:
        raise HTTPException(status_code=422, detail="Too many vendor insurance records.")
    reference = as_of or date.today()
    return VendorInsuranceListOut(
        items=[_out(row, reference) for row in rows],
        total=len(rows), as_of=reference,
    )


@router.post("/{vendor_id}/insurance", response_model=VendorInsuranceOut, status_code=201)
def create_vendor_insurance(
    vendor_id: int,
    payload: VendorInsuranceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id, _ = _vendor(db, current_user, vendor_id, write=True)
    row = VendorInsurance(
        organization_id=org_id, vendor_id=vendor_id,
        created_by_id=current_user.id, updated_by_id=current_user.id,
        **payload.model_dump(),
    )
    db.add(row)
    db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=org_id,
        entity_type="vendor_insurance", entity_id=row.id,
        action="created",
        new_value={"vendor_id": vendor_id, "expiration_date": row.expiration_date.isoformat()},
    )
    db.commit()
    db.refresh(row)
    return _out(row, date.today())


@router.patch("/{vendor_id}/insurance/{policy_id}", response_model=VendorInsuranceOut)
def update_vendor_insurance(
    vendor_id: int,
    policy_id: int,
    payload: VendorInsuranceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id, _ = _vendor(db, current_user, vendor_id, write=True)
    row = _policy(db, org_id, vendor_id, policy_id)
    if not row.is_active or row.deleted_at is not None:
        raise HTTPException(status_code=409, detail="Restore insurance policy before updating.")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="No insurance changes supplied.")
    for required in ("carrier", "coverage_type", "expiration_date"):
        if required in changes and changes[required] is None:
            raise HTTPException(status_code=422, detail="Carrier, coverage and expiry are required.")
    effective = changes.get("effective_date", row.effective_date)
    expiry = changes.get("expiration_date", row.expiration_date)
    if effective and effective > expiry:
        raise HTTPException(status_code=422, detail="Effective date cannot exceed expiration date.")
    modified = []
    for key, value in changes.items():
        if getattr(row, key) != value:
            modified.append(key)
            setattr(row, key, value)
    if not modified:
        return _out(row, date.today())
    row.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=org_id,
        entity_type="vendor_insurance", entity_id=row.id,
        action="updated", new_value={"changed_fields": sorted(modified)},
    )
    db.commit()
    db.refresh(row)
    return _out(row, date.today())


@router.delete("/{vendor_id}/insurance/{policy_id}", status_code=204)
def delete_vendor_insurance(
    vendor_id: int,
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id, _ = _vendor(db, current_user, vendor_id, write=True)
    row = _policy(db, org_id, vendor_id, policy_id)
    if row.is_active and row.deleted_at is None:
        row.is_active = False
        row.deleted_at = datetime.utcnow()
        row.updated_by_id = current_user.id
        db.flush()
        append_audit_log(
            db, user_id=current_user.id, organization_id=org_id,
            entity_type="vendor_insurance", entity_id=row.id, action="deactivated",
        )
        db.commit()
    return Response(status_code=204)


@router.post("/{vendor_id}/insurance/{policy_id}/restore", response_model=VendorInsuranceOut)
def restore_vendor_insurance(
    vendor_id: int,
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id, _ = _vendor(db, current_user, vendor_id, write=True)
    row = _policy(db, org_id, vendor_id, policy_id)
    if not row.is_active or row.deleted_at is not None:
        row.is_active = True
        row.deleted_at = None
        row.updated_by_id = current_user.id
        db.flush()
        append_audit_log(
            db, user_id=current_user.id, organization_id=org_id,
            entity_type="vendor_insurance", entity_id=row.id, action="restored",
        )
        db.commit()
    db.refresh(row)
    return _out(row, date.today())
