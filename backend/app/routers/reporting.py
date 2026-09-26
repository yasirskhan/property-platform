"""Customer reporting framework, export, and email delivery."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
import json
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.email import send_email
from app.models.user import User
from app.models.saved_report import SavedReport
from app.services.audit import append_audit_log
from app.services.saved_reports import validate_saved_parameters
from app.routers.auth import get_current_user
from app.schemas.reporting import (
    ReportCatalogOut,
    ReportDefinitionOut,
    ReportEmailIn,
    ReportEmailOut,
    SavedReportIn,
    SavedReportOut,
    SavedReportListOut,
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


def _build_or_422(db: Session, *, organization_id: int, report_key: str, parameters: dict[str, object], current_user: User | None = None):
    try:
        return build_report_payload(
            db,
            organization_id=organization_id,
            report_key=report_key,
            parameters=parameters,
            current_user=current_user,
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




def _saved_row(db: Session, *, organization_id: int, user_id: int, report_id: int) -> SavedReport:
    row = (
        db.query(SavedReport)
        .filter(
            SavedReport.id == report_id,
            SavedReport.organization_id == organization_id,
            SavedReport.user_id == user_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Saved report not found.")
    return row


def _saved_out(row: SavedReport) -> SavedReportOut:
    return SavedReportOut(
        id=row.id, organization_id=row.organization_id, name=row.name,
        report_key=row.report_key, parameters=json.loads(row.parameters_json),
        created_at=row.created_at, updated_at=row.updated_at,
    )


def _validated_saved(db: Session, *, current_user: User, payload: SavedReportIn):
    organization_id = _require_report_access(db, current_user=current_user, report_key=payload.report_key)
    try:
        parameters = validate_saved_parameters(payload.report_key, payload.parameters)
    except ReportDeliveryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return organization_id, parameters


@router.get("/saved", response_model=SavedReportListOut)
def list_saved_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _require_reporting_access(db, current_user)
    rows = (
        db.query(SavedReport)
        .filter(SavedReport.organization_id == organization_id, SavedReport.user_id == current_user.id)
        .order_by(SavedReport.updated_at.desc(), SavedReport.id.desc())
        .all()
    )
    # A saved preset must not disclose a report the user can no longer access.
    permitted = [
        row for row in rows
        if REPORT_PERMISSIONS.get(row.report_key) is not None
        and permission_allows_user(db, user=current_user, menu_key=REPORT_PERMISSIONS[row.report_key])
    ]
    return SavedReportListOut(items=[_saved_out(row) for row in permitted], total=len(permitted))


@router.post("/saved", response_model=SavedReportOut, status_code=201)
def create_saved_report(
    payload: SavedReportIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id, parameters = _validated_saved(db, current_user=current_user, payload=payload)
    row = SavedReport(
        organization_id=organization_id, user_id=current_user.id,
        name=payload.name, report_key=payload.report_key,
        parameters_json=json.dumps(parameters, sort_keys=True),
    )
    db.add(row)
    db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=organization_id,
        entity_type="saved_report", entity_id=row.id, action="created",
        new_value={"name": row.name, "report_key": row.report_key, "parameters": parameters},
    )
    db.commit()
    db.refresh(row)
    return _saved_out(row)


@router.get("/saved/{report_id}", response_model=SavedReportOut)
def get_saved_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _require_reporting_access(db, current_user)
    row = _saved_row(db, organization_id=organization_id, user_id=current_user.id, report_id=report_id)
    _require_report_access(db, current_user=current_user, report_key=row.report_key)
    return _saved_out(row)


@router.put("/saved/{report_id}", response_model=SavedReportOut)
def update_saved_report(
    report_id: int,
    payload: SavedReportIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _require_reporting_access(db, current_user)
    row = _saved_row(db, organization_id=organization_id, user_id=current_user.id, report_id=report_id)
    _require_report_access(db, current_user=current_user, report_key=row.report_key)
    _, parameters = _validated_saved(db, current_user=current_user, payload=payload)
    old = {"name": row.name, "report_key": row.report_key, "parameters": json.loads(row.parameters_json)}
    row.name, row.report_key = payload.name, payload.report_key
    row.parameters_json = json.dumps(parameters, sort_keys=True)
    db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=organization_id,
        entity_type="saved_report", entity_id=row.id, action="updated",
        old_value=old,
        new_value={"name": row.name, "report_key": row.report_key, "parameters": parameters},
    )
    db.commit()
    db.refresh(row)
    return _saved_out(row)


@router.delete("/saved/{report_id}", status_code=204)
def delete_saved_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _require_reporting_access(db, current_user)
    row = _saved_row(db, organization_id=organization_id, user_id=current_user.id, report_id=report_id)
    _require_report_access(db, current_user=current_user, report_key=row.report_key)
    append_audit_log(
        db, user_id=current_user.id, organization_id=organization_id,
        entity_type="saved_report", entity_id=row.id, action="deleted",
        old_value={"name": row.name, "report_key": row.report_key},
    )
    db.delete(row)
    db.commit()
    return Response(status_code=204)


@router.get("/labels/preview")
def preview_labels(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Live, authorized label rows for the printable mail-merge preview."""
    organization_id = _require_report_access(db, current_user=current_user, report_key="mailing.labels")
    _require_export_feature(db, current_user)
    payload = _build_or_422(
        db, organization_id=organization_id, report_key="mailing.labels",
        parameters=dict(request.query_params), current_user=current_user,
    )
    return {
        "title": payload.title,
        "headers": payload.headers,
        "rows": payload.rows,
        "total": len(payload.rows),
    }


@router.get("/delinquency/preview")
def preview_delinquency(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Current, explicitly authorized overdue RENT-invoice balances."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="tenant.delinquency",
    )
    _require_export_feature(db, current_user)
    payload = _build_or_422(
        db, organization_id=org_id, report_key="tenant.delinquency",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"title": payload.title, "headers": payload.headers,
            "rows": payload.rows, "total": len(payload.rows)}


@router.get("/security-deposits/preview")
def preview_security_deposit_funds(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Booked liability detail, not a claimed reconciliation of cash deposits."""
    organization_id = _require_report_access(
        db, current_user=current_user,
        report_key="tenant.security_deposit_funds_detail",
    )
    _require_export_feature(db, current_user)
    payload = _build_or_422(
        db, organization_id=organization_id,
        report_key="tenant.security_deposit_funds_detail",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": payload.title, "headers": payload.headers,
        "rows": payload.rows, "total": len(payload.rows),
    }


@router.get("/tenants/preview")
def preview_tenant_directory(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Org-scoped tenant directory with live property-assignment restrictions."""
    organization_id = _require_report_access(
        db, current_user=current_user, report_key="tenant.directory",
    )
    _require_export_feature(db, current_user)
    payload = _build_or_422(
        db, organization_id=organization_id, report_key="tenant.directory",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": payload.title, "headers": payload.headers,
        "rows": payload.rows, "total": len(payload.rows),
    }


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
        current_user=current_user,
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
        current_user=current_user,
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
