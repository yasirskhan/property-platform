# ============================================================
# diagnostics.py (router)
# ------------------------------------------------------------
# One endpoint:
#   GET /api/accounting/diagnostics
#     Runs the six financial health checks and returns the
#     full report. Read-only. Never posts anything.
#
# If we ever add an auto-fix (e.g. "Refund Negative Diagnostic"),
# it will live here as a separate POST endpoint.
# ============================================================

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.services.diagnostics import run_all_diagnostics, refund_negative_fee_account
from app.services.customer_features import resolve_customer_features
from app.services.gl_posting import PostingError
from app.services.menu_resolver import permission_allows_user


REFUND_NEGATIVE_FEATURE = "release.accounting.diagnostics.refund_negative"
WRITE_ROLES = {"ADMIN", "OWNER", "MANAGER"}


class RefundNegativeIn(BaseModel):
    gl_account_id: int
    transaction_date: date


class RefundNegativeOut(BaseModel):
    transaction_id: int
    gl_account_id: int
    gl_number: str
    offset_gl_account_id: int
    offset_gl_number: str
    amount: str


router = APIRouter(
    prefix="/api/accounting/diagnostics",
    tags=["Diagnostics"],
)


def _require_org(current_user: User) -> int:
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no organization.",
        )
    return current_user.organization_id


def _require_diagnostics_access(db: Session, current_user: User) -> int:
    org_id = _require_org(current_user)
    if not permission_allows_user(
        db, user=current_user, menu_key="ACCOUNTING.DIAGNOSTICS"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Diagnostics permission required.",
        )
    return org_id


def _require_refund_negative_feature(db: Session, current_user: User) -> int:
    org_id = _require_diagnostics_access(db, current_user)
    decision = next(
        (
            row
            for row in resolve_customer_features(db, user=current_user)
            if row.key == REFUND_NEGATIVE_FEATURE
        ),
        None,
    )
    if decision is None or not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Refund Negative Diagnostic is not available.",
        )
    role = str(getattr(current_user.role, "value", current_user.role) or "").upper()
    if role not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accounting write role required.",
        )
    return org_id


# ============================================================
# GET /api/accounting/diagnostics
# ============================================================

@router.get("")
def get_diagnostics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_diagnostics_access(db, current_user)

    report = run_all_diagnostics(db, org_id)

    # Convert Decimal values in details to strings for JSON safety.
    for check in report["checks"]:
        for detail in check["details"]:
            for k, v in list(detail.items()):
                if hasattr(v, "quantize"):  # it's a Decimal
                    detail[k] = str(v)

    return report

# ============================================================
# POST /api/accounting/diagnostics/refund-negative
# ============================================================

@router.post("/refund-negative", response_model=RefundNegativeOut)
def refund_negative_diagnostic(
    payload: RefundNegativeIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_refund_negative_feature(db, current_user)
    try:
        result = refund_negative_fee_account(
            db,
            organization_id=org_id,
            gl_account_id=payload.gl_account_id,
            transaction_date=payload.transaction_date,
            created_by=current_user,
        )
    except PostingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return RefundNegativeOut(
        **result,
        amount=str(result["amount"]),
    )
