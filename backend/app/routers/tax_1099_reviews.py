"""Admin-only manual 1099 review workflow. There is deliberately no filing endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.tax_1099_review import (
    Tax1099ApprovalIn, Tax1099PrepareIn, Tax1099ReviewOut, Tax1099UpdateIn,
)
from app.services.tax_1099_reviews import (
    approve_review, list_reviews, mark_reviewed, prepare_review, update_prepared,
)

router = APIRouter(prefix="/api/reporting/tax-1099-reviews", tags=["1099 preparation review"])
NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


@router.get("", response_model=list[Tax1099ReviewOut])
def read_reviews(
    response: Response, tax_year: int | None = Query(default=None),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    response.headers.update(NO_STORE)
    return list_reviews(db, current_user=current_user, tax_year=tax_year)


@router.post("", response_model=Tax1099ReviewOut, status_code=201)
def create_review(
    payload: Tax1099PrepareIn, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    response.headers.update(NO_STORE)
    return prepare_review(db, current_user=current_user, payload=payload)


@router.put("/{record_id}", response_model=Tax1099ReviewOut)
def edit_review(
    record_id: int, payload: Tax1099UpdateIn, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    response.headers.update(NO_STORE)
    return update_prepared(db, current_user=current_user, record_id=record_id, payload=payload)


@router.post("/{record_id}/review", response_model=Tax1099ReviewOut)
def review_record(
    record_id: int, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    response.headers.update(NO_STORE)
    return mark_reviewed(db, current_user=current_user, record_id=record_id)


@router.post("/{record_id}/approve", response_model=Tax1099ReviewOut)
def approve_record(
    record_id: int, payload: Tax1099ApprovalIn, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    response.headers.update(NO_STORE)
    return approve_review(db, current_user=current_user, record_id=record_id, payload=payload)
