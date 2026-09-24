# ============================================================
# routers/leases.py
# ------------------------------------------------------------
# HTTP routes for leases:
#
#   POST   /leases                      create a lease
#   GET    /leases                      list (role-scoped)
#   GET    /leases/{id}                 get one
#   PATCH  /leases/{id}                 update
#
#   POST   /leases/{id}/send            send for signature
#   POST   /leases/{id}/sign            tenant signs
#   POST   /leases/{id}/activate        activate (generate invoices)
#   POST   /leases/{id}/terminate       end early
#
# WHO CAN DO WHAT:
#   - Admin: everything.
#   - Owner: leases in their org's properties.
#   - Manager: leases for properties they're assigned to.
#   - Crew: no access.
#   - Tenant: view their OWN leases only.
# ============================================================

from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core import auth as auth_logic
from app.core.database import get_db
from app.models.lease import (
    Lease,
    LeaseStatus,
    RentInvoice,
    InvoiceStatus,
)
from app.models.property import Property, Unit, PropertyAssignment
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.routers.properties import check_property_access
from app.schemas.lease import (
    LeaseCreate,
    LeaseOut,
    LeaseUpdate,
    LeaseWithInvoices,
    RentInvoiceOut,
)


router = APIRouter(prefix="/leases", tags=["Leases"])


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------
def _require_role(current_user: User, *allowed: UserRole):
    if current_user.role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires one of: {[r.value for r in allowed]}",
        )


def _get_unit_and_property(db: Session, unit_id: int):
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    prop = db.query(Property).filter(Property.id == unit.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return unit, prop


def _check_property_access(db: Session, user: User, prop: Property):
    """Use the canonical customer-side property scope rules."""
    check_property_access(db, user, prop.id)


def _check_lease_access(db: Session, user: User, lease: Lease) -> Lease:
    """Return the lease if the user can see it."""
    if user.role == UserRole.TENANT:
        if lease.tenant_id != user.id:
            raise HTTPException(status_code=403, detail="Not your lease")
        return lease

    unit, prop = _get_unit_and_property(db, lease.unit_id)
    _check_property_access(db, user, prop)
    return lease


def _generate_invoices_for_lease(db: Session, lease: Lease) -> List[RentInvoice]:
    """
    Generate monthly invoices for the lease from start_date to end_date.
    Only generates ones that don't already exist.
    """
    existing_periods = {
        inv.period_start for inv in
        db.query(RentInvoice).filter(RentInvoice.lease_id == lease.id).all()
    }

    invoices = []
    current = lease.start_date.replace(day=1)
    while current <= lease.end_date:
        # period start = first of month
        period_start = current
        # period end = last day of the same month
        next_month = (period_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        period_end = next_month - timedelta(days=1)

        if period_start not in existing_periods:
            # Due date is the lease.due_day within this month
            try:
                due_date = period_start.replace(day=lease.due_day)
            except ValueError:
                due_date = period_start

            inv = RentInvoice(
                lease_id=lease.id,
                period_start=period_start,
                period_end=period_end,
                due_date=due_date,
                amount_due=lease.monthly_rent,
                amount_paid=0,
                status=InvoiceStatus.PENDING,
            )
            db.add(inv)
            invoices.append(inv)

        # advance to next month
        current = next_month

    return invoices


# ------------------------------------------------------------
# CREATE LEASE
# ------------------------------------------------------------
@router.post("", response_model=LeaseOut, status_code=status.HTTP_201_CREATED)
def create_lease(
    payload: LeaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a lease.
    - Admin / Owner / Manager: allowed (within their scope).
    - Tenant / Crew: not allowed.
    """
    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)

    # Validate the unit exists and the user has access to its property
    unit, prop = _get_unit_and_property(db, payload.unit_id)
    _check_property_access(db, current_user, prop)

    # Validate the tenant exists and is role=tenant
    tenant = auth_logic.get_user_by_id(db, payload.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if tenant.role != UserRole.TENANT:
        raise HTTPException(status_code=400, detail="The specified user is not a tenant")
    if tenant.organization_id != prop.organization_id:
        raise HTTPException(status_code=403, detail="Tenant is not in this organization")

    # Validate dates
    if payload.end_date <= payload.start_date:
        raise HTTPException(status_code=400, detail="end_date must be after start_date")

    # Check the unit isn't already actively leased
    existing = (
        db.query(Lease)
        .filter(
            Lease.unit_id == unit.id,
            Lease.status.in_([LeaseStatus.ACTIVE, LeaseStatus.PENDING_SIGNATURE]),
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Unit already has an active or pending lease")

    lease = Lease(**payload.model_dump())
    db.add(lease)
    db.commit()
    db.refresh(lease)
    return lease


# ------------------------------------------------------------
# LIST LEASES
# ------------------------------------------------------------
@router.get("", response_model=List[LeaseOut])
def list_leases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List leases visible to the current user.
    - Tenant: sees only their own leases.
    - Everyone else: leases for properties they can access.
    """
    if current_user.role == UserRole.TENANT:
        return db.query(Lease).filter(Lease.tenant_id == current_user.id).all()

    if current_user.role == UserRole.CREW:
        raise HTTPException(status_code=403, detail="Crew members cannot list leases")

    # Customer Admin / Owner: leases for properties in their org
    if current_user.role in (UserRole.ADMIN, UserRole.OWNER):
        return (
            db.query(Lease)
            .join(Unit, Unit.id == Lease.unit_id)
            .join(Property, Property.id == Unit.property_id)
            .filter(Property.organization_id == current_user.organization_id)
            .all()
        )

    # Manager: leases for properties they're assigned to
    if current_user.role == UserRole.MANAGER:
        return (
            db.query(Lease)
            .join(Unit, Unit.id == Lease.unit_id)
            .join(Property, Property.id == Unit.property_id)
            .join(PropertyAssignment, PropertyAssignment.property_id == Property.id)
            .filter(
                PropertyAssignment.user_id == current_user.id,
                PropertyAssignment.is_active == True,  # noqa: E712
            )
            .all()
        )

    return []


# ------------------------------------------------------------
# GET ONE LEASE
# ------------------------------------------------------------
@router.get("/{lease_id}", response_model=LeaseWithInvoices)
def get_lease(
    lease_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lease = db.query(Lease).filter(Lease.id == lease_id).first()
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    return _check_lease_access(db, current_user, lease)


# ------------------------------------------------------------
# UPDATE LEASE
# ------------------------------------------------------------
@router.patch("/{lease_id}", response_model=LeaseOut)
def update_lease(
    lease_id: int,
    payload: LeaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)

    lease = db.query(Lease).filter(Lease.id == lease_id).first()
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")

    _check_lease_access(db, current_user, lease)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(lease, field, value)

    db.commit()
    db.refresh(lease)
    return lease


# ------------------------------------------------------------
# SEND FOR SIGNATURE
# ------------------------------------------------------------
@router.post("/{lease_id}/send", response_model=LeaseOut)
def send_lease(
    lease_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Move lease from draft to pending_signature."""
    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)

    lease = db.query(Lease).filter(Lease.id == lease_id).first()
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    _check_lease_access(db, current_user, lease)

    if lease.status != LeaseStatus.DRAFT:
        raise HTTPException(status_code=400, detail=f"Cannot send a lease with status '{lease.status.value}'")

    lease.status = LeaseStatus.PENDING_SIGNATURE
    lease.signed_by_manager = True  # manager sending = countersigning
    db.commit()
    db.refresh(lease)
    return lease


# ------------------------------------------------------------
# TENANT SIGNS
# ------------------------------------------------------------
@router.post("/{lease_id}/sign", response_model=LeaseOut)
def sign_lease(
    lease_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Tenant signs the lease.
    Only the tenant on the lease can sign it.
    """
    lease = db.query(Lease).filter(Lease.id == lease_id).first()
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")

    if current_user.role != UserRole.TENANT or lease.tenant_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the tenant on this lease can sign it")

    if lease.status != LeaseStatus.PENDING_SIGNATURE:
        raise HTTPException(status_code=400, detail="Lease is not pending signature")

    lease.signed_by_tenant = True
    lease.signed_at = datetime.utcnow()
    db.commit()
    db.refresh(lease)
    return lease


# ------------------------------------------------------------
# ACTIVATE LEASE (generate invoices)
# ------------------------------------------------------------
@router.post("/{lease_id}/activate", response_model=LeaseOut)
def activate_lease(
    lease_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Activate the lease and generate monthly rent invoices.
    Requires both parties signed.
    """
    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)

    lease = db.query(Lease).filter(Lease.id == lease_id).first()
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    _check_lease_access(db, current_user, lease)

    if not (lease.signed_by_tenant and lease.signed_by_manager):
        raise HTTPException(status_code=400, detail="Both parties must sign before activation")

    if lease.status == LeaseStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Lease is already active")

    lease.status = LeaseStatus.ACTIVE
    _generate_invoices_for_lease(db, lease)
    db.commit()
    db.refresh(lease)
    return lease


# ------------------------------------------------------------
# TERMINATE LEASE
# ------------------------------------------------------------
@router.post("/{lease_id}/terminate", response_model=LeaseOut)
def terminate_lease(
    lease_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """End the lease early. Admin / Owner / Manager."""
    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)

    lease = db.query(Lease).filter(Lease.id == lease_id).first()
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    _check_lease_access(db, current_user, lease)

    lease.status = LeaseStatus.TERMINATED
    db.commit()
    db.refresh(lease)
    return lease


# ------------------------------------------------------------
# LIST INVOICES FOR A LEASE
# ------------------------------------------------------------
@router.get("/{lease_id}/invoices", response_model=List[RentInvoiceOut])
def list_invoices(
    lease_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lease = db.query(Lease).filter(Lease.id == lease_id).first()
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    _check_lease_access(db, current_user, lease)

    return (
        db.query(RentInvoice)
        .filter(RentInvoice.lease_id == lease_id)
        .order_by(RentInvoice.period_start)
        .all()
    )
