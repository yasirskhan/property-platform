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

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.services.diagnostics import run_all_diagnostics


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


# ============================================================
# GET /api/accounting/diagnostics
# ============================================================

@router.get("")
def get_diagnostics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)

    report = run_all_diagnostics(db, org_id)

    # Convert Decimal values in details to strings for JSON safety.
    for check in report["checks"]:
        for detail in check["details"]:
            for k, v in list(detail.items()):
                if hasattr(v, "quantize"):  # it's a Decimal
                    detail[k] = str(v)

    return report