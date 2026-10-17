"""Explicit staff-entered dated inspection entries, append-only workflow."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.unit_inspection import UnitInspectionCreateIn, UnitInspectionOut
from app.services.report_delivery import ReportDeliveryError
from app.services.unit_inspections import list_inspections, record_inspection

router = APIRouter(prefix="/api/unit-inspections", tags=["Unit Inspection Records"])


def _error(exc: ReportDeliveryError) -> HTTPException:
    message = str(exc)
    if "permission" in message:
        return HTTPException(status_code=403, detail=message)
    if "not found" in message:
        return HTTPException(status_code=404, detail=message)
    return HTTPException(status_code=422, detail=message)


@router.get("", response_model=list[UnitInspectionOut])
def get_inspections(
    response: Response,
    property_id: int | None = Query(default=None, ge=1),
    unit_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        return list_inspections(
            db, actor=current_user, property_id=property_id, unit_id=unit_id,
        )
    except ReportDeliveryError as exc:
        raise _error(exc) from exc


@router.post("", response_model=UnitInspectionOut, status_code=201)
def create_inspection(
    payload: UnitInspectionCreateIn,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        return record_inspection(db, actor=current_user, payload=payload)
    except ReportDeliveryError as exc:
        raise _error(exc) from exc
