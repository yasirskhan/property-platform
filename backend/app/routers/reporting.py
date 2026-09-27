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


@router.get("/tenant-ledger/preview")
def preview_tenant_ledger(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Current recorded invoice and standalone charge balance rows."""
    organization_id = _require_report_access(
        db, current_user=current_user, report_key="tenant.ledger",
    )
    _require_export_feature(db, current_user)
    payload = _build_or_422(
        db, organization_id=organization_id, report_key="tenant.ledger",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"title": payload.title, "headers": payload.headers,
            "rows": payload.rows, "total": len(payload.rows)}


@router.get("/tickler/preview")
def preview_tenant_tickler(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Current tenant contact visibility with only recorded lease activity."""
    organization_id = _require_report_access(
        db, current_user=current_user, report_key="tenant.tickler",
    )
    _require_export_feature(db, current_user)
    payload = _build_or_422(
        db, organization_id=organization_id, report_key="tenant.tickler",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": payload.title, "headers": payload.headers,
        "rows": payload.rows, "total": len(payload.rows),
    }


@router.get("/unpaid-charges/preview")
def preview_tenant_unpaid_charges(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unpaid standalone tenant charges, current recorded amount_paid snapshot only."""
    organization_id = _require_report_access(
        db, current_user=current_user, report_key="tenant.unpaid_charges",
    )
    _require_export_feature(db, current_user)
    payload = _build_or_422(
        db, organization_id=organization_id, report_key="tenant.unpaid_charges",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": payload.title, "headers": payload.headers,
        "rows": payload.rows, "total": len(payload.rows),
    }


@router.get("/unpaid-charges-summary/preview")
def preview_tenant_unpaid_charges_summary(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate only the detail report's currently authorized positive charge rows."""
    organization_id = _require_report_access(
        db, current_user=current_user, report_key="tenant.summary",
    )
    _require_export_feature(db, current_user)
    payload = _build_or_422(
        db, organization_id=organization_id, report_key="tenant.summary",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": payload.title, "headers": payload.headers,
        "rows": payload.rows, "total": len(payload.rows),
    }


@router.get("/budget-comparison/preview")
def preview_property_budget_comparison(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Current explicit budget versus posted accrual GL, never inferred target."""
    organization_id = _require_report_access(
        db, current_user=current_user, report_key="property.budget_comparison",
    )
    _require_export_feature(db, current_user)
    payload = _build_or_422(
        db, organization_id=organization_id, report_key="property.budget_comparison",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": payload.title, "headers": payload.headers,
        "rows": payload.rows, "total": len(payload.rows),
    }


@router.get("/property-groups/preview")
def preview_property_group_directory(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Only explicitly assigned property memberships, scoped by capability."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="property.group_directory",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="property.group_directory",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": data.title, "headers": data.headers,
        "rows": data.rows, "total": len(data.rows),
    }


@router.get("/vendor-directory/preview")
def preview_vendor_directory(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recorded vendor user contacts, never tax IDs or bill payee guesses."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="vendor.directory",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="vendor.directory",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": data.title, "headers": data.headers,
        "rows": data.rows, "total": len(data.rows),
    }


@router.get("/owner-directory/preview")
def preview_owner_directory(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Visible recorded owner contact fields only; no tax or bank data."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="owner.directory",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="owner.directory",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": data.title, "headers": data.headers,
        "rows": data.rows, "total": len(data.rows),
    }


@router.get("/unit-vacancy-detail/preview")
def preview_unit_vacancy_detail(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Only missing eligible current recorded leases; no physical-vacancy assertion."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="property.unit_vacancy_detail",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="property.unit_vacancy_detail",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": data.title, "headers": data.headers,
        "rows": data.rows, "total": len(data.rows),
    }


@router.get("/unit-inspections/preview")
def preview_unit_inspections(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recorded inspection entries only; no guessed inspection outcome."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="property.unit_inspection",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="property.unit_inspection",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": data.title, "headers": data.headers,
        "rows": data.rows, "total": len(data.rows),
    }


@router.get("/unit-directory/preview")
def preview_unit_directory(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Only authorized active unit inventory, not inferred physical vacancy."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="property.unit_directory",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="property.unit_directory",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": data.title, "headers": data.headers,
        "rows": data.rows, "total": len(data.rows),
    }


@router.get("/rent-roll/preview")
def preview_rent_roll(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Current recorded lease associations; not historical occupancy or collections."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="property.rent_roll",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="property.rent_roll",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": data.title, "headers": data.headers,
        "rows": data.rows, "total": len(data.rows),
    }


@router.get("/property-performance/preview")
def preview_property_performance(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Posted property-tagged income and expense movements, not cash receipts."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="property.performance",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="property.performance",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": data.title, "headers": data.headers,
        "rows": data.rows, "total": len(data.rows),
    }


@router.get("/property-directory/preview")
def preview_property_directory(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Live active properties and configured active units, not inferred occupancy."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="property.directory",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="property.directory",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": data.title, "headers": data.headers,
        "rows": data.rows, "total": len(data.rows),
    }


@router.get("/lease-expirations/preview")
def preview_lease_expirations(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Only recorded contract end dates, not confirmed tenant departures."""
    report_key = request.query_params.get("report_key", "property.lease_expiration_detail")
    if report_key not in {"property.lease_expiration_detail", "property.lease_expiration_summary"}:
        raise HTTPException(status_code=404, detail="Report not found.")
    org_id = _require_report_access(db, current_user=current_user, report_key=report_key)
    _require_export_feature(db, current_user)
    parameters = {key: value for key, value in request.query_params.items() if key != "report_key"}
    data = _build_or_422(
        db, organization_id=org_id, report_key=report_key,
        parameters=parameters, current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": data.title, "headers": data.headers,
        "rows": data.rows, "total": len(data.rows),
    }


@router.get("/gross-potential-rent/preview")
def preview_gross_potential_rent(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Current market/lease rent projection; posted journals are distinct markers."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="property.gross_potential_rent",
    )
    _require_export_feature(db, current_user)
    result = _build_or_422(
        db, organization_id=org_id, report_key="property.gross_potential_rent",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": result.title, "headers": result.headers,
        "rows": result.rows, "total": len(result.rows),
    }


@router.get("/budget-detail/preview")
def preview_property_budget_detail(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Only recorded budget targets, with missing periods visibly blank."""
    organization_id = _require_report_access(
        db, current_user=current_user, report_key="property.budget_detail",
    )
    _require_export_feature(db, current_user)
    payload = _build_or_422(
        db, organization_id=organization_id, report_key="property.budget_detail",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": payload.title, "headers": payload.headers,
        "rows": payload.rows, "total": len(payload.rows),
    }


@router.get("/vendor-ledger/preview")
def preview_vendor_ledger(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Read-only linked vendor payable-bill snapshot; never infer payee identity."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="vendor.ledger",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="vendor.ledger",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": data.title, "headers": data.headers,
        "rows": data.rows, "total": len(data.rows),
    }


@router.get("/work-orders/preview")
def preview_work_order_report(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Staff-visible work order inventory without private entry instructions."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="maintenance.work_order",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="maintenance.work_order",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": data.title, "headers": data.headers,
        "rows": data.rows, "total": len(data.rows),
    }


@router.get("/account-totals/preview")
def preview_account_totals(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Posted accrual GL aggregates only, no inferred bank balance."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="accounting.account_totals",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="accounting.account_totals",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": data.title, "headers": data.headers,
        "rows": data.rows, "total": len(data.rows),
    }


@router.get("/balance-sheet/preview")
def preview_balance_sheet(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Verified equation of posted accrual account balances, not estimates."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="accounting.balance_sheet",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="accounting.balance_sheet",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": data.title, "headers": data.headers,
        "rows": data.rows, "total": len(data.rows),
    }


@router.get("/bank-activity/preview")
def preview_bank_account_activity(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Scoped, posted cash-account GL movements (not imported bank-feed items)."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="accounting.bank_activity",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="accounting.bank_activity",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": data.title, "headers": data.headers,
        "rows": data.rows, "total": len(data.rows),
    }


@router.get("/bank-association/preview")
def preview_bank_account_association(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recorded same-organization bank-to-GL mapping, never bank credentials."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="accounting.bank_association",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="accounting.bank_association",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "title": data.title, "headers": data.headers,
        "rows": data.rows, "total": len(data.rows),
    }


@router.get("/cash-flow/preview")
def preview_cash_flow(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Configured bank-mapped, posted GL book cash movement only."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="accounting.cash_flow",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="accounting.cash_flow",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"title": data.title, "headers": data.headers,
            "rows": data.rows, "total": len(data.rows)}


@router.get("/cash-flow-12-month/preview")
def preview_cash_flow_12_month(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Server-rendered, authorized 12-month posted bank-book report."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="accounting.cash_flow_12_month",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="accounting.cash_flow_12_month",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"title": data.title, "headers": data.headers,
            "rows": data.rows, "total": len(data.rows)}


@router.get("/expense-register/preview")
def preview_expense_register(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Org-scoped posted expense GL entry lines; no cash-spend inference."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="transaction.expense_register",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="transaction.expense_register",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"title": data.title, "headers": data.headers,
            "rows": data.rows, "total": len(data.rows)}


@router.get("/deposit-register/preview")
def preview_deposit_register(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recorded deposit grouping of original receipts, not new GL posting."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="transaction.deposit_register",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="transaction.deposit_register",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"title": data.title, "headers": data.headers,
            "rows": data.rows, "total": len(data.rows)}


@router.get("/check-register-detail/preview")
def preview_check_register_detail(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Verified issue/void headers and same-org recorded bill allocations."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="transaction.check_register_detail",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="transaction.check_register_detail",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"title": data.title, "headers": data.headers,
            "rows": data.rows, "total": len(data.rows)}


@router.get("/check-register/preview")
def preview_check_register(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recorded checks with verified GL issue/void status; no banking secrets."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="transaction.check_register",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="transaction.check_register",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"title": data.title, "headers": data.headers,
            "rows": data.rows, "total": len(data.rows)}


@router.get("/charge-detail/preview")
def preview_charge_detail(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recorded standalone Charge details; not posted AR or historic payments."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="transaction.charge_detail",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="transaction.charge_detail",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"title": data.title, "headers": data.headers,
            "rows": data.rows, "total": len(data.rows)}


@router.get("/bill-detail/preview")
def preview_bill_detail(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Authorized posted bill/line detail with no payment-history inference."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="transaction.bill_detail",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="transaction.bill_detail",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"title": data.title, "headers": data.headers,
            "rows": data.rows, "total": len(data.rows)}


@router.get("/aged-receivables/preview")
def preview_aged_receivables(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Live current rent invoice aging, not a historical/posted GL AR ledger."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="transaction.aged_receivables",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="transaction.aged_receivables",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"title": data.title, "headers": data.headers,
            "rows": data.rows, "total": len(data.rows)}


@router.get("/aged-payables/preview")
def preview_aged_payables(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Current recorded unpaid bill aging, not reconstructed historical payables."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="transaction.aged_payables",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="transaction.aged_payables",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"title": data.title, "headers": data.headers,
            "rows": data.rows, "total": len(data.rows)}


@router.get("/trust-account-detail/preview")
def preview_trust_account_detail(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Authenticated, posted trust book entry detail and verified tag references."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="accounting.trust_account_detail",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="accounting.trust_account_detail",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"title": data.title, "headers": data.headers,
            "rows": data.rows, "total": len(data.rows)}


@router.get("/trust-account-balance/preview")
def preview_trust_account_balance(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Scoped posted trust bank GL book balances, never bank statement cash."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="accounting.trust_account_balance",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="accounting.trust_account_balance",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"title": data.title, "headers": data.headers,
            "rows": data.rows, "total": len(data.rows)}


@router.get("/income-statement/preview")
def preview_income_statement(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dated, posted accrual income and expense GL: not bank cash or audited P&L."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="accounting.income_statement",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="accounting.income_statement",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"title": data.title, "headers": data.headers,
            "rows": data.rows, "total": len(data.rows)}


@router.get("/expense-distribution/preview")
def preview_expense_distribution(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dated posted accrual expense distribution; never cash-basis inferred."""
    org_id = _require_report_access(
        db, current_user=current_user, report_key="accounting.expense_distribution",
    )
    _require_export_feature(db, current_user)
    data = _build_or_422(
        db, organization_id=org_id, report_key="accounting.expense_distribution",
        parameters=dict(request.query_params), current_user=current_user,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"title": data.title, "headers": data.headers,
            "rows": data.rows, "total": len(data.rows)}


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
