# ============================================================
# charges.py
# ------------------------------------------------------------
# Standalone tenant charges.
#
#   GET    /api/accounting/charges            list (filters)
#   POST   /api/accounting/charges            create
#   GET    /api/accounting/charges/{id}       detail
#   PATCH  /api/accounting/charges/{id}       edit
#   DELETE /api/accounting/charges/{id}       soft delete
#
# Rules:
#   - ADMIN/OWNER/MANAGER only.
#   - Tenant must belong to the caller's org.
#   - GL account must be an INCOME account in the caller's org.
#   - Paid charges cannot be edited below the amount already paid.
#   - Paid charges cannot be deleted (only reversed elsewhere).
#
# See PROJECT_MASTER.md Section 19 and JSON items
# accounting.charges.enter_charge, accounting.charges.list_view,
# accounting.charges.edit_rules.
# ============================================================

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.charge import Charge
from app.models.gl_account import GLAccount
from app.models.lease import Lease
from app.models.property import Property, Unit
from app.services.menu_resolver import permission_allows_user


router = APIRouter(prefix="/api/accounting/charges", tags=["charges"])

WRITE_ROLES = {"ADMIN", "OWNER", "MANAGER"}


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _role(user: User) -> str:
    return (user.role.value if hasattr(user.role, "value") else str(user.role)).upper()


def _require_org(user: User) -> int:
    if user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no organization.",
        )
    return user.organization_id


def _require_charges_access(db: Session, user: User) -> int:
    org_id = _require_org(user)
    if not permission_allows_user(
        db, user=user, menu_key="ACCOUNTING.CHARGES"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Charges permission required.",
        )
    return org_id


def _require_write(user: User) -> None:
    if _role(user) not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ADMIN, OWNER, or MANAGER can manage charges.",
        )


def _resolve_tenant_unit_property(db: Session, org_id: int, tenant_user_id: int):
    """Given a tenant, return (unit_id, property_id) from their active lease."""
    lease = (
        db.query(Lease)
        .join(Unit, Unit.id == Lease.unit_id)
        .join(Property, Property.id == Unit.property_id)
        .filter(
            Property.organization_id == org_id,
            Lease.tenant_id == tenant_user_id,
        )
        .order_by(Lease.id.desc())
        .first()
    )
    if lease is None:
        return None, None
    unit = db.query(Unit).filter(Unit.id == lease.unit_id).first()
    if unit is None:
        return None, None
    return unit.id, unit.property_id


# ------------------------------------------------------------
# Schemas
# ------------------------------------------------------------
class ChargeOut(BaseModel):
    id: int
    organization_id: int
    tenant_user_id: int
    unit_id: int | None
    property_id: int | None
    gl_account_id: int
    charge_date: date
    description: str
    amount: str
    amount_paid: str
    is_paid: bool
    is_active: bool
    created_at: datetime | None

    class Config:
        from_attributes = True


class ChargeCreateIn(BaseModel):
    tenant_user_id: int
    charge_date: date
    gl_account_id: int
    description: str = Field(..., min_length=1, max_length=500)
    amount: float = Field(..., gt=0)
    # If not provided, unit/property are auto-filled from the tenant's lease.
    unit_id: int | None = None
    property_id: int | None = None


class ChargeUpdateIn(BaseModel):
    charge_date: date | None = None
    description: str | None = Field(None, min_length=1, max_length=500)
    amount: float | None = Field(None, gt=0)
    gl_account_id: int | None = None


# ------------------------------------------------------------
# GET list
# ------------------------------------------------------------
@router.get("", response_model=list[ChargeOut])
def list_charges(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    tenant_user_id: int | None = Query(None),
    property_id: int | None = Query(None),
    is_paid: bool | None = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_charges_access(db, current_user)

    q = db.query(Charge).filter(
        Charge.organization_id == org_id,
        Charge.is_active.is_(True),
    )
    if date_from is not None:
        q = q.filter(Charge.charge_date >= date_from)
    if date_to is not None:
        q = q.filter(Charge.charge_date <= date_to)
    if tenant_user_id is not None:
        q = q.filter(Charge.tenant_user_id == tenant_user_id)
    if property_id is not None:
        q = q.filter(Charge.property_id == property_id)
    if is_paid is not None:
        q = q.filter(Charge.is_paid.is_(is_paid))

    rows = q.order_by(Charge.charge_date.desc(), Charge.id.desc()).limit(limit).all()
    return rows


# ------------------------------------------------------------
# GET detail
# ------------------------------------------------------------
@router.get("/{charge_id}", response_model=ChargeOut)
def get_charge(
    charge_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_charges_access(db, current_user)
    row = (
        db.query(Charge)
        .filter(Charge.id == charge_id, Charge.organization_id == org_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Charge not found.")
    return row


# ------------------------------------------------------------
# POST create
# ------------------------------------------------------------
@router.post("", response_model=ChargeOut, status_code=status.HTTP_201_CREATED)
def create_charge(
    payload: ChargeCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    org_id = _require_charges_access(db, current_user)

    # Tenant must be in this org
    tenant = (
        db.query(User)
        .filter(User.id == payload.tenant_user_id, User.organization_id == org_id)
        .first()
    )
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found in your organization.")

    # GL account must be INCOME and belong to this org
    gl = (
        db.query(GLAccount)
        .filter(GLAccount.id == payload.gl_account_id, GLAccount.organization_id == org_id)
        .first()
    )
    if gl is None:
        raise HTTPException(status_code=404, detail="GL account not found.")
    if (gl.account_type or "").upper() != "INCOME":
        raise HTTPException(
            status_code=422,
            detail="Charge GL account must be an INCOME account.",
        )

    # Auto-fill unit / property from tenant's most recent lease
    unit_id = payload.unit_id
    property_id = payload.property_id
    if unit_id is None or property_id is None:
        auto_unit, auto_prop = _resolve_tenant_unit_property(db, org_id, tenant.id)
        unit_id = unit_id or auto_unit
        property_id = property_id or auto_prop

    # If unit was given, verify it belongs to org via property
    if unit_id is not None:
        unit = (
            db.query(Unit)
            .join(Property, Property.id == Unit.property_id)
            .filter(Unit.id == unit_id, Property.organization_id == org_id)
            .first()
        )
        if unit is None:
            raise HTTPException(status_code=404, detail="Unit not found.")
        property_id = property_id or unit.property_id

    row = Charge(
        organization_id=org_id,
        tenant_user_id=tenant.id,
        unit_id=unit_id,
        property_id=property_id,
        gl_account_id=gl.id,
        charge_date=payload.charge_date,
        description=payload.description,
        amount=payload.amount,
        amount_paid=0,
        is_paid=False,
        created_by_id=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ------------------------------------------------------------
# PATCH update
# ------------------------------------------------------------
@router.patch("/{charge_id}", response_model=ChargeOut)
def update_charge(
    charge_id: int,
    payload: ChargeUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    org_id = _require_charges_access(db, current_user)

    row = (
        db.query(Charge)
        .filter(Charge.id == charge_id, Charge.organization_id == org_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Charge not found.")

    # Paid charge: amount can only go UP (never below what's paid)
    if payload.amount is not None:
        if row.is_paid:
            raise HTTPException(status_code=400, detail="Cannot edit a fully paid charge.")
        paid = float(row.amount_paid or 0)
        if payload.amount < paid:
            raise HTTPException(
                status_code=400,
                detail=f"Amount cannot be lower than the amount already paid ({paid:.2f}).",
            )
        row.amount = payload.amount

    if payload.charge_date is not None:
        row.charge_date = payload.charge_date
    if payload.description is not None:
        row.description = payload.description
    if payload.gl_account_id is not None:
        gl = (
            db.query(GLAccount)
            .filter(GLAccount.id == payload.gl_account_id, GLAccount.organization_id == org_id)
            .first()
        )
        if gl is None:
            raise HTTPException(status_code=404, detail="GL account not found.")
        if (gl.account_type or "").upper() != "INCOME":
            raise HTTPException(status_code=422, detail="GL account must be INCOME.")
        row.gl_account_id = gl.id

    row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ------------------------------------------------------------
# DELETE (soft)
# ------------------------------------------------------------
@router.delete("/{charge_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_charge(
    charge_id: int,
    reason: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    org_id = _require_charges_access(db, current_user)

    row = (
        db.query(Charge)
        .filter(Charge.id == charge_id, Charge.organization_id == org_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Charge not found.")

    if row.is_paid:
        raise HTTPException(status_code=400, detail="Cannot delete a fully paid charge.")

    row.is_active = False
    row.delete_reason = reason or "deleted"
    row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    return None