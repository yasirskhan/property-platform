"""Bounded, explicitly entered property budget targets; no GL writes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.property_budget import PropertyBudgetOut, PropertyBudgetUpsertIn
from app.services.property_budgets import (
    list_property_budget, upsert_property_budget,
)
from app.services.report_delivery import ReportDeliveryError

router = APIRouter(prefix="/api/reporting/property-budgets", tags=["Property Budgets"])


def _status(exc: ReportDeliveryError) -> int:
    value = str(exc)
    if "permission" in value or "administrators" in value:
        return 403
    if "not found" in value:
        return 404
    return 422


@router.get("", response_model=list[PropertyBudgetOut])
def list_budget_lines(
    response: Response,
    property_id: int = Query(ge=1),
    calendar_year: int = Query(ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        return list_property_budget(
            db, current_user=current_user,
            property_id=property_id, calendar_year=calendar_year,
        )
    except ReportDeliveryError as exc:
        raise HTTPException(status_code=_status(exc), detail=str(exc)) from exc


@router.put("", response_model=PropertyBudgetOut)
def save_budget_line(
    payload: PropertyBudgetUpsertIn,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        return upsert_property_budget(db, current_user=current_user, payload=payload)
    except ReportDeliveryError as exc:
        raise HTTPException(status_code=_status(exc), detail=str(exc)) from exc
