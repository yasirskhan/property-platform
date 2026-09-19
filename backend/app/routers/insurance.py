# ============================================================
# routers/insurance.py
# ------------------------------------------------------------
# Property insurance CRUD. Owner / Admin only.
# Tenants are BLOCKED from all insurance routes.
#
# When a premium is set on a policy, an expense row is
# automatically created/updated in property_expenses.
# ============================================================

from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.database import get_db
from app.models.expense import PropertyExpense, ExpenseCategory, ExpenseSource
from app.models.insurance import PropertyInsurance
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.routers.properties import check_property_access, require_non_tenant
from app.schemas.insurance import (
    PropertyInsuranceCreate,
    PropertyInsuranceUpdate,
    PropertyInsuranceOut,
)


router = APIRouter(tags=["Property Insurance"])


def _require_owner_or_admin(current_user: User):
    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER):
        raise HTTPException(
            status_code=403,
            detail="Only owners and admins can manage insurance",
        )


def _sync_insurance_expense(db: Session, insurance: PropertyInsurance, user: User):
    """
    Create or update the property_expense row linked to this insurance premium.
    Called whenever a policy is created or updated.
    """
    # If no premium, there's nothing to sync
    if not insurance.premium_amount or insurance.premium_amount <= 0:
        return

    existing = (
        db.query(PropertyExpense)
        .filter(
            PropertyExpense.source == ExpenseSource.INSURANCE,
            PropertyExpense.source_id == insurance.id,
        )
        .first()
    )

    description = (
        f"{insurance.provider} — {insurance.policy_type.value} premium"
    )
    expense_date = insurance.start_date or date.today()

    if existing:
        existing.amount = insurance.premium_amount
        existing.description = description
        existing.expense_date = expense_date
    else:
        e = PropertyExpense(
            property_id=insurance.property_id,
            category=ExpenseCategory.INSURANCE,
            amount=insurance.premium_amount,
            description=description,
            expense_date=expense_date,
            source=ExpenseSource.INSURANCE,
            source_id=insurance.id,
            created_by_id=user.id,
        )
        db.add(e)

    db.commit()


def _remove_insurance_expense(db: Session, insurance_id: int):
    """Delete the linked expense if the insurance is deleted."""
    db.query(PropertyExpense).filter(
        PropertyExpense.source == ExpenseSource.INSURANCE,
        PropertyExpense.source_id == insurance_id,
    ).delete()
    db.commit()


# ------------------------------------------------------------
# LIST
# ------------------------------------------------------------
@router.get(
    "/properties/{property_id}/insurance",
    response_model=List[PropertyInsuranceOut],
)
def list_insurance(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    check_property_access(db, current_user, property_id)
    return (
        db.query(PropertyInsurance)
        .filter(PropertyInsurance.property_id == property_id)
        .all()
    )


# ------------------------------------------------------------
# CREATE
# ------------------------------------------------------------
@router.post(
    "/properties/{property_id}/insurance",
    response_model=PropertyInsuranceOut,
    status_code=status.HTTP_201_CREATED,
)
def create_insurance(
    property_id: int,
    payload: PropertyInsuranceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    _require_owner_or_admin(current_user)
    check_property_access(db, current_user, property_id)

    i = PropertyInsurance(property_id=property_id, **payload.model_dump())
    db.add(i)
    db.commit()
    db.refresh(i)

    # Auto-create the linked expense if premium is set
    _sync_insurance_expense(db, i, current_user)

    log_action(
        db, current_user,
        entity_type="property_insurance",
        entity_id=i.id,
        action="created",
        new_value={"provider": i.provider, "type": i.policy_type.value},
    )
    return i


# ------------------------------------------------------------
# GET ONE
# ------------------------------------------------------------
@router.get(
    "/properties/{property_id}/insurance/{policy_id}",
    response_model=PropertyInsuranceOut,
)
def get_insurance(
    property_id: int,
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    check_property_access(db, current_user, property_id)
    i = (
        db.query(PropertyInsurance)
        .filter(
            PropertyInsurance.id == policy_id,
            PropertyInsurance.property_id == property_id,
        )
        .first()
    )
    if not i:
        raise HTTPException(status_code=404, detail="Policy not found")
    return i


# ------------------------------------------------------------
# UPDATE
# ------------------------------------------------------------
@router.patch(
    "/properties/{property_id}/insurance/{policy_id}",
    response_model=PropertyInsuranceOut,
)
def update_insurance(
    property_id: int,
    policy_id: int,
    payload: PropertyInsuranceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    _require_owner_or_admin(current_user)
    check_property_access(db, current_user, property_id)

    i = (
        db.query(PropertyInsurance)
        .filter(
            PropertyInsurance.id == policy_id,
            PropertyInsurance.property_id == property_id,
        )
        .first()
    )
    if not i:
        raise HTTPException(status_code=404, detail="Policy not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(i, field, value)
    db.commit()
    db.refresh(i)

    # Re-sync the linked expense
    _sync_insurance_expense(db, i, current_user)

    return i


# ------------------------------------------------------------
# DELETE
# ------------------------------------------------------------
@router.delete(
    "/properties/{property_id}/insurance/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_insurance(
    property_id: int,
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    _require_owner_or_admin(current_user)
    check_property_access(db, current_user, property_id)

    i = (
        db.query(PropertyInsurance)
        .filter(
            PropertyInsurance.id == policy_id,
            PropertyInsurance.property_id == property_id,
        )
        .first()
    )
    if not i:
        raise HTTPException(status_code=404, detail="Policy not found")

    # Remove the linked expense first
    _remove_insurance_expense(db, policy_id)

    db.delete(i)
    db.commit()
    log_action(
        db, current_user,
        entity_type="property_insurance",
        entity_id=policy_id,
        action="deleted",
    )
    return None