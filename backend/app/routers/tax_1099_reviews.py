"""Admin-only manual 1099 review workflow. There is deliberately no filing endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.routers.reporting import _require_export_feature
from app.services.report_delivery import report_csv_bytes
from app.services.audit import append_audit_log
from app.routers.auth import get_current_user
from app.schemas.tax_1099_review import (
    Tax1099ApprovalIn, Tax1099PrepareIn, Tax1099ReviewOut, Tax1099UpdateIn,
)
from app.services.tax_1099_reviews import (
    approve_review, internal_register, list_reviews, mark_reviewed, prepare_review, update_prepared,
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


@router.get("/register.csv")
def export_internal_register(
    tax_year: int = Query(..., ge=2020, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin-only INTERNAL redacted register. Never an IRIS/provider format."""
    from app.services.tax_profiles import require_tax_admin

    organization_id = require_tax_admin(db, current_user)
    _require_export_feature(db, current_user)
    payload = internal_register(db, current_user=current_user, tax_year=tax_year)
    csv_bytes = report_csv_bytes(payload)
    append_audit_log(
        db, user_id=current_user.id, organization_id=organization_id,
        entity_type="tax_1099_register", entity_id=organization_id,
        action="exported_internal",
        new_value={"tax_year": tax_year, "records": len(payload.rows),
                   "irs_submission": False},
    )
    db.commit()
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={
            **NO_STORE,
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'attachment; filename="{payload.filename}"',
        },
    )
