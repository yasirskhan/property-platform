"""Customer reporting framework and catalog."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.reporting import ReportCatalogOut, ReportDefinitionOut
from app.services.menu_resolver import permission_allows_user
from app.services.report_catalog import report_catalog
from app.services.reporting_basis import get_accounting_basis


router = APIRouter(prefix="/api/reporting", tags=["Reporting"])
MENU_KEY = "REPORTING.ALL"


def _require_reporting_access(db: Session, current_user: User) -> int:
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization.")
    if not permission_allows_user(db, user=current_user, menu_key=MENU_KEY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reporting permission required.",
        )
    return int(current_user.organization_id)


@router.get("/catalog", response_model=ReportCatalogOut)
def get_report_catalog(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _require_reporting_access(db, current_user)
    standard, enhanced = report_catalog()
    return ReportCatalogOut(
        accounting_basis=get_accounting_basis(db, organization_id=organization_id),
        standard=[ReportDefinitionOut(**item.__dict__) for item in standard],
        enhanced=[ReportDefinitionOut(**item.__dict__) for item in enhanced],
    )
