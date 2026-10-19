"""Explicit staff-entered dated inspection entries, append-only workflow."""
from __future__ import annotations

from typing import Annotated, Literal
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.property import Property, Unit
from app.models.work_order import WorkOrder
from app.schemas.work_order import WorkOrderOut
from app.routers.auth import get_current_user
from app.schemas.unit_inspection import UnitInspectionCreateIn, UnitInspectionOut
from app.services.report_delivery import ReportDeliveryError
from app.services.unit_inspections import get_inspection, list_inspections, record_inspection

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
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    recorded_condition: Literal["SATISFACTORY", "ATTENTION_NEEDED", "NOT_ASSESSED"] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from cannot be after date_to")
    try:
        return list_inspections(
            db, actor=current_user, property_id=property_id, unit_id=unit_id,
            limit=limit, offset=offset,
            recorded_condition=recorded_condition,
            date_from=date_from, date_to=date_to,
        )
    except ReportDeliveryError as exc:
        raise _error(exc) from exc



@router.get("/{inspection_id}", response_model=UnitInspectionOut)
def get_inspection_detail(
    inspection_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    if inspection_id < 1:
        raise HTTPException(status_code=422, detail="Invalid inspection record ID")
    try:
        return get_inspection(db, actor=current_user, inspection_id=inspection_id)
    except ReportDeliveryError as exc:
        raise _error(exc) from exc



@router.get("/{inspection_id}/work-orders", response_model=list[WorkOrderOut])
def get_inspection_work_orders(
    inspection_id: int,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Read linked follow-ups only after authorizing the exact inspection."""
    response.headers["Cache-Control"] = "no-store"
    if inspection_id < 1:
        raise HTTPException(status_code=422, detail="Invalid inspection record ID")
    try:
        inspection = get_inspection(
            db, actor=current_user, inspection_id=inspection_id,
        )
    except ReportDeliveryError as exc:
        raise _error(exc) from exc
    # Defensive parent reconciliation also covers manually corrupted links.
    return db.query(WorkOrder).join(
        Unit, Unit.id == WorkOrder.unit_id,
    ).join(
        Property, Property.id == Unit.property_id,
    ).filter(
        WorkOrder.source_inspection_id == inspection.id,
        WorkOrder.unit_id == inspection.unit_id,
        WorkOrder.property_id == inspection.property_id,
        Property.id == inspection.property_id,
        Property.organization_id == current_user.organization_id,
    ).order_by(WorkOrder.id.desc()).offset(offset).limit(limit).all()


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
