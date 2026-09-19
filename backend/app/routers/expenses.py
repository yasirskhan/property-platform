# ============================================================
# routers/expenses.py
# ------------------------------------------------------------
#   GET    /properties/{id}/expenses
#   POST   /properties/{id}/expenses
#   PATCH  /properties/{id}/expenses/{expense_id}
#   DELETE /properties/{id}/expenses/{expense_id}
#   GET    /properties/{id}/expenses/summary
# ============================================================

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.database import get_db
from app.models.expense import PropertyExpense, ExpenseCategory
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.routers.properties import check_property_access, require_non_tenant
from app.schemas.expense import (
    PropertyExpenseCreate,
    PropertyExpenseUpdate,
    PropertyExpenseOut,
)


router = APIRouter(tags=["Expenses"])


def _require_manage(current_user: User):
    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER):
        raise HTTPException(status_code=403, detail="Only owners and admins can manage expenses")


@router.get("/properties/{property_id}/expenses", response_model=List[PropertyExpenseOut])
def list_expenses(
    property_id: int,
    category: Optional[ExpenseCategory] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    check_property_access(db, current_user, property_id)

    q = db.query(PropertyExpense).filter(PropertyExpense.property_id == property_id)
    if category:
        q = q.filter(PropertyExpense.category == category)
    return q.order_by(PropertyExpense.expense_date.desc()).all()


@router.get("/properties/{property_id}/expenses/summary", response_model=dict)
def expense_summary(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    check_property_access(db, current_user, property_id)

    rows = (
        db.query(
            PropertyExpense.category,
            func.sum(PropertyExpense.amount).label("total"),
        )
        .filter(PropertyExpense.property_id == property_id)
        .group_by(PropertyExpense.category)
        .all()
    )

    by_category = {r[0].value: float(r[1]) for r in rows}
    total = sum(by_category.values())

    return {"total": total, "by_category": by_category}


@router.post(
    "/properties/{property_id}/expenses",
    response_model=PropertyExpenseOut,
    status_code=status.HTTP_201_CREATED,
)
def create_expense(
    property_id: int,
    payload: PropertyExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    _require_manage(current_user)
    check_property_access(db, current_user, property_id)

    e = PropertyExpense(
        property_id=property_id,
        created_by_id=current_user.id,
        **payload.model_dump(),
    )
    db.add(e)
    db.commit()
    db.refresh(e)

    log_action(db, current_user, entity_type="property_expense", entity_id=e.id, action="created")
    return e


@router.patch("/properties/{property_id}/expenses/{expense_id}", response_model=PropertyExpenseOut)
def update_expense(
    property_id: int,
    expense_id: int,
    payload: PropertyExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    _require_manage(current_user)
    check_property_access(db, current_user, property_id)

    e = db.query(PropertyExpense).filter(
        PropertyExpense.id == expense_id,
        PropertyExpense.property_id == property_id,
    ).first()
    if not e:
        raise HTTPException(status_code=404, detail="Expense not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(e, field, value)
    db.commit()
    db.refresh(e)
    return e


@router.delete("/properties/{property_id}/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    property_id: int,
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    _require_manage(current_user)
    check_property_access(db, current_user, property_id)

    e = db.query(PropertyExpense).filter(
        PropertyExpense.id == expense_id,
        PropertyExpense.property_id == property_id,
    ).first()
    if not e:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(e)
    db.commit()
    return None