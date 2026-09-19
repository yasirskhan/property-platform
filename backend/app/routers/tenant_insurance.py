# ============================================================
# routers/tenant_insurance.py
# ------------------------------------------------------------
# Tenant rental insurance — upload, verify, list, compliance.
# ============================================================

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.database import get_db
from app.models.lease import Lease
from app.models.property import Property, Unit, PropertyAssignment
from app.models.tenant_insurance import (
    TenantInsurance,
    TenantInsuranceStatus,
)
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.tenant_insurance import (
    TenantInsuranceCreate,
    TenantInsuranceUpdate,
    TenantInsuranceOut,
    TenantInsuranceVerify,
)


router = APIRouter(prefix="/tenant-insurance", tags=["Tenant Insurance"])


def _check_lease_access(db: Session, user: User, lease: Lease):
    """Same rules as leases — tenant sees own, manager assigned, owner in org."""
    if user.role == UserRole.ADMIN:
        return
    if user.role == UserRole.TENANT:
        if lease.tenant_id != user.id:
            raise HTTPException(status_code=403, detail="Not your lease")
        return

    unit = db.query(Unit).filter(Unit.id == lease.unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    prop = db.query(Property).filter(Property.id == unit.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    if user.role == UserRole.OWNER:
        if prop.organization_id != user.organization_id:
            raise HTTPException(status_code=403, detail="Not in your organization")
        return

    if user.role == UserRole.MANAGER:
        assigned = (
            db.query(PropertyAssignment)
            .filter(
                PropertyAssignment.property_id == prop.id,
                PropertyAssignment.user_id == user.id,
                PropertyAssignment.is_active == True,  # noqa: E712
            )
            .first()
        )
        if not assigned:
            raise HTTPException(status_code=403, detail="Not assigned")
        return

    raise HTTPException(status_code=403, detail="Access denied")


# ------------------------------------------------------------
# LIST BY LEASE
# ------------------------------------------------------------
@router.get("/lease/{lease_id}", response_model=List[TenantInsuranceOut])
def list_by_lease(
    lease_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lease = db.query(Lease).filter(Lease.id == lease_id).first()
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    _check_lease_access(db, current_user, lease)

    return (
        db.query(TenantInsurance)
        .filter(TenantInsurance.lease_id == lease_id)
        .order_by(TenantInsurance.created_at.desc())
        .all()
    )


# ------------------------------------------------------------
# CREATE (tenant or manager)
# ------------------------------------------------------------
@router.post("", response_model=TenantInsuranceOut, status_code=status.HTTP_201_CREATED)
def create_insurance(
    payload: TenantInsuranceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lease = db.query(Lease).filter(Lease.id == payload.lease_id).first()
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    _check_lease_access(db, current_user, lease)

    # Find the property
    unit = db.query(Unit).filter(Unit.id == lease.unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")

    record = TenantInsurance(
        lease_id=lease.id,
        tenant_id=lease.tenant_id,
        property_id=unit.property_id,
        uploaded_by_id=current_user.id,
        **payload.model_dump(exclude={"lease_id"}),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


# ------------------------------------------------------------
# UPDATE
# ------------------------------------------------------------
@router.patch("/{insurance_id}", response_model=TenantInsuranceOut)
def update_insurance(
    insurance_id: int,
    payload: TenantInsuranceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rec = db.query(TenantInsurance).filter(TenantInsurance.id == insurance_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Insurance record not found")

    lease = db.query(Lease).filter(Lease.id == rec.lease_id).first()
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    _check_lease_access(db, current_user, lease)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rec, field, value)
    db.commit()
    db.refresh(rec)
    return rec


# ------------------------------------------------------------
# VERIFY (manager/owner/admin only)
# ------------------------------------------------------------
@router.post("/{insurance_id}/verify", response_model=TenantInsuranceOut)
def verify_insurance(
    insurance_id: int,
    payload: TenantInsuranceVerify,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rec = db.query(TenantInsurance).filter(TenantInsurance.id == insurance_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Insurance record not found")

    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER):
        raise HTTPException(status_code=403, detail="Only staff can verify insurance")

    lease = db.query(Lease).filter(Lease.id == rec.lease_id).first()
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    _check_lease_access(db, current_user, lease)

    if payload.approve:
        rec.status = TenantInsuranceStatus.VERIFIED
        rec.verified_by_id = current_user.id
        rec.verified_at = datetime.utcnow()
        rec.rejection_reason = None
    else:
        rec.status = TenantInsuranceStatus.REJECTED
        rec.rejection_reason = payload.rejection_reason or "Rejected"
        rec.verified_by_id = current_user.id
        rec.verified_at = datetime.utcnow()

    db.commit()
    db.refresh(rec)

    log_action(
        db, current_user,
        entity_type="tenant_insurance",
        entity_id=rec.id,
        action="verified" if payload.approve else "rejected",
    )
    return rec


# ------------------------------------------------------------
# COMPLIANCE (portfolio-wide)
# ------------------------------------------------------------
@router.get("/compliance", response_model=List[dict])
def compliance_view(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Portfolio-wide compliance view — for managers/owners/admins.
    Shows every active lease with its most recent insurance record.
    """
    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER):
        raise HTTPException(status_code=403, detail="Not allowed")

    # Build lease scope
    lease_q = db.query(Lease)

    if current_user.role == UserRole.OWNER:
        lease_q = (
            lease_q.join(Unit, Unit.id == Lease.unit_id)
            .join(Property, Property.id == Unit.property_id)
            .filter(Property.organization_id == current_user.organization_id)
        )
    elif current_user.role == UserRole.MANAGER:
        lease_q = (
            lease_q.join(Unit, Unit.id == Lease.unit_id)
            .join(Property, Property.id == Unit.property_id)
            .join(PropertyAssignment, PropertyAssignment.property_id == Property.id)
            .filter(
                PropertyAssignment.user_id == current_user.id,
                PropertyAssignment.is_active == True,  # noqa: E712
            )
        )

    leases = lease_q.all()

    result = []
    for lease in leases:
        tenant = db.query(User).filter(User.id == lease.tenant_id).first()
        unit = db.query(Unit).filter(Unit.id == lease.unit_id).first()
        prop = db.query(Property).filter(Property.id == unit.property_id).first() if unit else None

        ins = (
            db.query(TenantInsurance)
            .filter(TenantInsurance.lease_id == lease.id)
            .order_by(TenantInsurance.created_at.desc())
            .first()
        )

        result.append({
            "lease_id": lease.id,
            "tenant_id": lease.tenant_id,
            "tenant_name": f"{tenant.first_name} {tenant.last_name}" if tenant else "—",
            "property_name": prop.name if prop else "—",
            "unit_number": unit.unit_number if unit else "—",
            "insurance_id": ins.id if ins else None,
            "status": ins.status.value if ins else "missing",
            "provider": ins.provider if ins else None,
            "expiration_date": ins.expiration_date.isoformat() if ins and ins.expiration_date else None,
            "document_url": ins.document_url if ins else None,
        })

    return result