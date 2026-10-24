"""Explicit named property group settings and organization-scoped membership."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.property_group import PropertyGroupOut, PropertyGroupUpsertIn
from app.services.property_groups import (
    delete_group, list_groups, save_group,
)
from app.services.report_delivery import ReportDeliveryError

router = APIRouter(prefix="/api/property-groups", tags=["Property Groups"])


def _error(exc: ReportDeliveryError) -> HTTPException:
    detail = str(exc)
    if "not enabled" in detail:
        return HTTPException(status_code=404, detail=detail)
    if "permission" in detail:
        return HTTPException(status_code=403, detail=detail)
    if "not found" in detail:
        return HTTPException(status_code=404, detail=detail)
    return HTTPException(status_code=422, detail=detail)


@router.get("", response_model=list[PropertyGroupOut])
def get_groups(
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        return list_groups(db, actor=current_user)
    except ReportDeliveryError as exc:
        raise _error(exc) from exc


@router.post("", response_model=PropertyGroupOut, status_code=201)
def create_group(
    payload: PropertyGroupUpsertIn,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        return save_group(db, actor=current_user, payload=payload)
    except ReportDeliveryError as exc:
        raise _error(exc) from exc


@router.put("/{group_id}", response_model=PropertyGroupOut)
def update_group(
    group_id: int,
    payload: PropertyGroupUpsertIn,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        return save_group(db, actor=current_user, payload=payload, group_id=group_id)
    except ReportDeliveryError as exc:
        raise _error(exc) from exc


@router.delete("/{group_id}", status_code=204)
def remove_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        delete_group(db, actor=current_user, group_id=group_id)
    except ReportDeliveryError as exc:
        raise _error(exc) from exc
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
