"""Read-only comparison of adopted HOA annual budgets to posted, property-tagged GL.

This does not infer that all property-tagged activity belongs to an HOA.
No write, bank transfer or member charge is performed.
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.hoa_annual_budget import HOAAnnualBudget
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_annual_budgets import _staff, _budget

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA budget actuals"])


@router.get("/{association_id}/annual-budgets/{budget_id}/book-actuals")
def annual_budget_actuals(
    association_id: int, budget_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc = _staff(db, actor=current_user,
                        association_id=association_id,
                        property_id=property_id, write=False)
    row = _budget(db, org=org, association_id=assoc.id,
                  property_id=property_id, budget_id=budget_id)
    if row.status != "APPROVED":
        raise HTTPException(status_code=409, detail="Only an adopted budget can be compared to actuals.")
    lines = json.loads(row.lines_json)
    if not lines:
        raise HTTPException(status_code=409, detail="Budget has no GL lines.")
    gl_ids = [int(line["gl_account_id"]) for line in lines]
    start, end = date(row.calendar_year, 1, 1), date(row.calendar_year, 12, 31)
    booked = db.query(
        GLEntry.gl_account_id,
        func.coalesce(func.sum(GLEntry.debit), 0),
        func.coalesce(func.sum(GLEntry.credit), 0),
    ).join(GLTransaction, GLTransaction.id == GLEntry.transaction_id).filter(
        GLEntry.organization_id == org,
        GLTransaction.organization_id == org,
        GLEntry.property_id == property_id,
        GLEntry.gl_account_id.in_(gl_ids),
        GLTransaction.transaction_date >= start,
        GLTransaction.transaction_date <= end,
    ).group_by(GLEntry.gl_account_id).all()
    amounts = {int(gl_id): (Decimal(dr or 0), Decimal(cr or 0))
               for gl_id, dr, cr in booked}
    results = []
    for line in lines:
        gl_id = int(line["gl_account_id"])
        dr, cr = amounts.get(gl_id, (Decimal("0.00"), Decimal("0.00")))
        actual = cr - dr if line["account_type"] == "INCOME" else dr - cr
        target = Decimal(line["annual_amount"])
        results.append({
            "gl_account_id": gl_id,
            "gl_number": line["gl_number"],
            "gl_name": line["gl_name"],
            "account_type": line["account_type"],
            "annual_budget": target,
            "actual_book": actual,
            "variance_actual_minus_budget": actual - target,
        })
    response.headers["Cache-Control"] = "no-store"
    return {
        "budget_id": row.id, "calendar_year": row.calendar_year,
        "property_id": property_id, "budget_status": row.status,
        "lines": results,
        "accounting_basis": "POSTED_GL_PROPERTY_TAGGED",
        "association_allocation_verified": False,
        "other_property_and_untagged_entries_excluded": True,
        "reserve_allocation_only_planned": True,
    }
