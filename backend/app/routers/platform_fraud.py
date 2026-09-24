"""Platform-only fraud review queue endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.fraud import FraudCase, FraudCaseStatus, FraudRiskLevel
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.routers.platform_auth import get_current_platform_user
from app.schemas.fraud import FraudCaseDetailOut, FraudCaseOut, FraudCaseReviewIn
from app.services.audit import append_audit_log


router = APIRouter(prefix="/api/platform/fraud", tags=["Platform Fraud"])

_FRAUD_VIEWERS = {
    PlatformUserRole.PLATFORM_ADMIN,
    PlatformUserRole.PLATFORM_BILLING,
    PlatformUserRole.PLATFORM_SUPPORT,
    PlatformUserRole.PLATFORM_TECH,
}
_FRAUD_REVIEWERS = {
    PlatformUserRole.PLATFORM_ADMIN,
    PlatformUserRole.PLATFORM_BILLING,
    PlatformUserRole.PLATFORM_SUPPORT,
}
_REVIEWABLE_STATUSES = {
    FraudCaseStatus.IN_REVIEW,
    FraudCaseStatus.APPROVED,
    FraudCaseStatus.BLOCKED,
    FraudCaseStatus.DISMISSED,
}
_TERMINAL_STATUSES = {
    FraudCaseStatus.APPROVED,
    FraudCaseStatus.BLOCKED,
    FraudCaseStatus.DISMISSED,
}


def _require_fraud_viewer(user: PlatformUser) -> None:
    if user.role not in _FRAUD_VIEWERS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform fraud-review access required",
        )


def _require_fraud_reviewer(user: PlatformUser) -> None:
    if user.role not in _FRAUD_REVIEWERS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform fraud-reviewer role required",
        )


@router.get("/cases", response_model=list[FraudCaseOut])
def list_fraud_cases(
    case_status: FraudCaseStatus | None = Query(default=None, alias="status"),
    risk_level: FraudRiskLevel | None = Query(default=None),
    organization_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
) -> list[FraudCase]:
    _require_fraud_viewer(current_user)
    query = db.query(FraudCase)
    if case_status is not None:
        query = query.filter(FraudCase.status == case_status)
    if risk_level is not None:
        query = query.filter(FraudCase.risk_level == risk_level)
    if organization_id is not None:
        query = query.filter(FraudCase.organization_id == organization_id)
    return (
        query.order_by(FraudCase.created_at.desc(), FraudCase.id.desc())
        .limit(limit)
        .all()
    )


@router.get("/cases/{case_id}", response_model=FraudCaseDetailOut)
def get_fraud_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
) -> FraudCase:
    _require_fraud_viewer(current_user)
    row = db.get(FraudCase, case_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Fraud case not found")
    return row


@router.patch("/cases/{case_id}", response_model=FraudCaseDetailOut)
def review_fraud_case(
    case_id: int,
    payload: FraudCaseReviewIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
) -> FraudCase:
    _require_fraud_reviewer(current_user)
    if payload.status not in _REVIEWABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fraud case must move to IN_REVIEW or a terminal review status",
        )

    row = db.get(FraudCase, case_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Fraud case not found")

    old_value = {
        "status": row.status.value,
        "resolution_notes": row.resolution_notes,
        "reviewed_by_platform_user_id": row.reviewed_by_platform_user_id,
    }
    row.status = payload.status
    row.reviewed_by_platform_user_id = current_user.id
    row.resolution_notes = payload.resolution_notes
    row.resolved_at = (
        datetime.utcnow() if payload.status in _TERMINAL_STATUSES else None
    )

    append_audit_log(
        db,
        platform_user_id=current_user.id,
        organization_id=row.organization_id,
        entity_type="fraud_case",
        entity_id=row.id,
        action="review",
        old_value=old_value,
        new_value={
            "status": payload.status.value,
            "resolution_notes": payload.resolution_notes,
            "reviewed_by_platform_user_id": current_user.id,
        },
    )
    db.commit()
    db.refresh(row)
    return row
