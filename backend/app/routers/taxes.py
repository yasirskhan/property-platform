# ============================================================
# routers/taxes.py
# ------------------------------------------------------------
#   GET    /properties/{id}/taxes                       list
#   POST   /properties/{id}/taxes                       create
#   GET    /properties/{id}/taxes/{tax_id}              get one
#   PATCH  /properties/{id}/taxes/{tax_id}              update
#   DELETE /properties/{id}/taxes/{tax_id}              delete
#   POST   /properties/{id}/taxes/{tax_id}/payments     record payment
#   GET    /properties/{id}/taxes/{tax_id}/payments     list payments
# ============================================================

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.database import get_db
from app.models.property import Property
from app.models.tax import PropertyTax, PropertyTaxPayment
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.routers.properties import check_property_access, require_non_tenant
from app.schemas.tax import (
    PropertyTaxCreate,
    PropertyTaxUpdate,
    PropertyTaxOut,
    PropertyTaxWithPayments,
    TaxPaymentCreate,
    TaxPaymentOut,
)


router = APIRouter(tags=["Property Taxes"])


def _require_manage(current_user: User):
    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER):
        raise HTTPException(status_code=403, detail="Only admins and owners can manage taxes")


# ------------------------------------------------------------
# LIST
# ------------------------------------------------------------
@router.get("/properties/{property_id}/taxes", response_model=List[PropertyTaxOut])
def list_taxes(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    check_property_access(db, current_user, property_id)
    return db.query(PropertyTax).filter(PropertyTax.property_id == property_id).all()


# ------------------------------------------------------------
# CREATE
# ------------------------------------------------------------
@router.post("/properties/{property_id}/taxes", response_model=PropertyTaxOut, status_code=status.HTTP_201_CREATED)
def create_tax(
    property_id: int,
    payload: PropertyTaxCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    _require_manage(current_user)
    check_property_access(db, current_user, property_id)

    tax = PropertyTax(property_id=property_id, **payload.model_dump())
    db.add(tax)
    db.commit()
    db.refresh(tax)

    log_action(db, current_user, entity_type="property_tax", entity_id=tax.id, action="created",
               new_value={"authority": tax.tax_authority, "type": tax.tax_type.value})

    return tax


# ------------------------------------------------------------
# GET ONE
# ------------------------------------------------------------
@router.get("/properties/{property_id}/taxes/{tax_id}", response_model=PropertyTaxWithPayments)
def get_tax(
    property_id: int,
    tax_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    check_property_access(db, current_user, property_id)
    tax = db.query(PropertyTax).filter(PropertyTax.id == tax_id, PropertyTax.property_id == property_id).first()
    if not tax:
        raise HTTPException(status_code=404, detail="Tax record not found")
    return tax


# ------------------------------------------------------------
# UPDATE
# ------------------------------------------------------------
@router.patch("/properties/{property_id}/taxes/{tax_id}", response_model=PropertyTaxOut)
def update_tax(
    property_id: int,
    tax_id: int,
    payload: PropertyTaxUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    _require_manage(current_user)
    check_property_access(db, current_user, property_id)

    tax = db.query(PropertyTax).filter(PropertyTax.id == tax_id, PropertyTax.property_id == property_id).first()
    if not tax:
        raise HTTPException(status_code=404, detail="Tax record not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tax, field, value)

    db.commit()
    db.refresh(tax)
    return tax


# ------------------------------------------------------------
# DELETE
# ------------------------------------------------------------
@router.delete("/properties/{property_id}/taxes/{tax_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tax(
    property_id: int,
    tax_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    _require_manage(current_user)
    check_property_access(db, current_user, property_id)

    tax = db.query(PropertyTax).filter(PropertyTax.id == tax_id, PropertyTax.property_id == property_id).first()
    if not tax:
        raise HTTPException(status_code=404, detail="Tax record not found")

    db.delete(tax)
    db.commit()

    log_action(db, current_user, entity_type="property_tax", entity_id=tax_id, action="deleted")
    return None


# ------------------------------------------------------------
# PAYMENTS
# ------------------------------------------------------------
@router.post("/properties/{property_id}/taxes/{tax_id}/payments", response_model=TaxPaymentOut, status_code=status.HTTP_201_CREATED)
def create_tax_payment(
    property_id: int,
    tax_id: int,
    payload: TaxPaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    _require_manage(current_user)
    check_property_access(db, current_user, property_id)

    tax = db.query(PropertyTax).filter(PropertyTax.id == tax_id, PropertyTax.property_id == property_id).first()
    if not tax:
        raise HTTPException(status_code=404, detail="Tax record not found")

    payment = PropertyTaxPayment(tax_id=tax_id, created_by_id=current_user.id, **payload.model_dump())
    db.add(payment)
    db.commit()
    db.refresh(payment)

    log_action(db, current_user, entity_type="property_tax_payment", entity_id=payment.id, action="created",
               new_value={"amount": float(payment.amount), "period": payment.period})

    return payment


@router.get("/properties/{property_id}/taxes/{tax_id}/payments", response_model=List[TaxPaymentOut])
def list_tax_payments(
    property_id: int,
    tax_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    check_property_access(db, current_user, property_id)
    tax = (
        db.query(PropertyTax)
        .filter(
            PropertyTax.id == tax_id,
            PropertyTax.property_id == property_id,
        )
        .first()
    )
    if not tax:
        raise HTTPException(status_code=404, detail="Tax record not found")
    return (
        db.query(PropertyTaxPayment)
        .filter(PropertyTaxPayment.tax_id == tax.id)
        .order_by(PropertyTaxPayment.paid_at.desc())
        .all()
    )