"""Customer reporting framework, export, and email delivery."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.email import send_email
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.reporting import (
    ReportCatalogOut,
    ReportDefinitionOut,
    ReportEmailIn,
    ReportEmailOut,
)
from app.services.customer_features import resolve_customer_features
from app.services.menu_resolver import permission_allows_user
from app.services.report_catalog import report_catalog
from app.services.report_delivery import (
    REPORT_PERMISSIONS,
    ReportDeliveryError,
    build_report_payload,
    report_csv_bytes,
)
from app.services.reporting_basis import get_accounting_basis


router = APIRouter(prefix="/api/reporting", tags=["Reporting"])
MENU_KEY = "REPORTING.ALL"
EXPORT_FEATURE_KEY = "release.reporting.export"


def _require_reporting_access(db: Session, current_user: User) -> int:
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization.")
    if not permission_allows_user(db, user=current_user, menu_key=MENU_KEY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reporting permission required.",
        )
    return int(current_user.organization_id)


def _require_report_access(db: Session, *, current_user: User, report_key: str) -> int:
    organization_id = _require_reporting_access(db, current_user)
    permission_key = REPORT_PERMISSIONS.get(report_key)
    if permission_key is None:
        raise HTTPException(status_code=404, detail="Report is not available for delivery.")
    if not permission_allows_user(db, user=current_user, menu_key=permission_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Report permission required.")
    return organization_id


def _require_export_feature(db: Session, current_user: User) -> None:
    decision = next(
        (item for item in resolve_customer_features(db, user=current_user) if item.key == EXPORT_FEATURE_KEY),
        None,
    )
    if decision is None or not decision.allowed:
        raise HTTPException(status_code=404, detail="Report delivery is not available.")


def _build_or_422(db: Session, *, organization_id: int, report_key: str, parameters: dict[str, object]):
    try:
        return build_report_payload(
            db,
            organization_id=organization_id,
            report_key=report_key,
            parameters=parameters,
        )
    except ReportDeliveryError as exc:
        detail = str(exc)
        status_code = 404 if detail.endswith("not found") else 422
        raise HTTPException(status_code=status_code, detail=detail) from exc


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


@router.get("/{report_key}/export.csv")
def export_report_csv(
    report_key: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _require_report_access(db, current_user=current_user, report_key=report_key)
    _require_export_feature(db, current_user)
    parameters = {key: value for key, value in request.query_params.items()}
    payload = _build_or_422(
        db,
        organization_id=organization_id,
        report_key=report_key,
        parameters=parameters,
    )
    return Response(
        content=report_csv_bytes(payload),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{payload.filename}"'},
    )


@router.post("/{report_key}/email", response_model=ReportEmailOut)
def email_report(
    report_key: str,
    payload: ReportEmailIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _require_report_access(db, current_user=current_user, report_key=report_key)
    _require_export_feature(db, current_user)
    report = _build_or_422(
        db,
        organization_id=organization_id,
        report_key=report_key,
        parameters=payload.parameters,
    )
    csv_bytes = report_csv_bytes(report)
    send_email(
        to=str(payload.recipient),
        subject=report.title,
        body=f"Attached is the requested {report.title} report.",
        organization_id=organization_id,
        db=db,
        attachments=[(report.filename, csv_bytes, "text/csv")],
    )
    return ReportEmailOut(sent=True, filename=report.filename)
