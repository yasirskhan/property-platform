"""Admin-only, no-store positive-pay readiness; never bank file generation."""
from __future__ import annotations
from datetime import date
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.services.positive_pay import preflight_positive_pay

router = APIRouter(prefix="/api/accounting/bank-accounts", tags=["Positive-pay readiness"])


@router.get("/{bank_id}/positive-pay/preflight")
def positive_pay_preflight(
    bank_id: int, response: Response,
    date_from: date | None = None, date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = preflight_positive_pay(
        db, bank_id=bank_id, current_user=current_user,
        date_from=date_from, date_to=date_to,
    )
    response.headers["Cache-Control"] = "no-store"
    return result
