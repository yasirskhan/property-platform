"""Platform-run AppFolio migration foundation.

This phase intentionally has no outbound AppFolio transport yet. The public
AppFolio API surface is known, but customer-specific credentials/provider
authorization are not stored or guessed here. Platform staff can establish a
target run and dry-run Property records supplied by a future verified adapter.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.gl_account import GLAccount
from app.models.platform_migration import (
    PlatformMigrationCorrectionRule,
    PlatformMigrationItem,
    PlatformMigrationRun,
    PlatformMigrationStagedRow,
    PlatformMigrationUpload,
)
from app.models.property import Property, Unit
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.user import Organization, User, UserRole
from app.models.vendor import Vendor
from app.routers.platform_auth import get_current_platform_user
from app.schemas.platform_migration import (
    AppFolioMigrationRunCreateIn,
    AppFolioMigrationItemOut,
    AppFolioMigrationRunOut,
    AppFolioMigrationStagedRowOut,
    AppFolioMigrationUploadOut,
    AppFolioMigrationCoverageOut,
    AppFolioMigrationReviewSummaryOut,
    AppFolioMigrationCorrectionRuleCreateIn,
    AppFolioMigrationCorrectionRuleUpdateIn,
    AppFolioMigrationCorrectionRuleOut,
    AppFolioStagedRowCorrectionIn,
    AppFolioStagedPropertyCommitIn,
    AppFolioStagedRowResolutionIn,
    AppFolioPropertyCommitIn,
    AppFolioPropertyCommitOut,
    AppFolioPropertyDryRunIn,
    AppFolioPropertyDryRunOut,
    AppFolioStagedUnitCommitIn,
    AppFolioStagedUnitResolutionIn,
    AppFolioStagedOwnerResolutionIn,
    AppFolioStagedOwnerCommitIn,
    AppFolioOwnerCommitOut,
    AppFolioOwnerDryRunOut,
    AppFolioStagedVendorResolutionIn,
    AppFolioStagedTenantResolutionIn,
    AppFolioStagedLeaseOccupancyResolutionIn,
    AppFolioStagedGLAccountResolutionIn,
    AppFolioStagedGeneralLedgerResolutionIn,
    AppFolioStagedBillResolutionIn,
    AppFolioStagedChargeResolutionIn,
    AppFolioStagedWorkOrderResolutionIn,
    AppFolioStagedGLAccountCommitIn,
    AppFolioGLAccountCommitOut,
    AppFolioGLAccountDryRunOut,
    AppFolioGeneralLedgerDryRunOut,
    AppFolioBillDryRunOut,
    AppFolioWorkOrderDryRunOut,
    AppFolioChargeDryRunOut,
    AppFolioGeneralLedgerCommitReadinessOut,
    AppFolioStagedTenantCommitIn,
    AppFolioTenantCommitOut,
    AppFolioTenantDryRunOut,
    AppFolioUnitCommitOut,
    AppFolioUnitDryRunOut,
    AppFolioStagedVendorCommitIn,
    AppFolioVendorCommitOut,
    AppFolioVendorDryRunOut,
)
from app.services.appfolio_migration import (
    AppFolioMigrationError,
    commit_properties,
    commit_units,
    commit_owners,
    commit_tenants,
    commit_vendors,
    commit_gl_accounts,
    dry_run_properties,
    dry_run_units,
    dry_run_owners,
    dry_run_tenants,
    dry_run_vendors,
    dry_run_gl_accounts,
)
from app.services.appfolio_file_ingestion import (
    MAX_FILE_BYTES,
    AppFolioFileIngestionError,
    stage_appfolio_file,
)
from app.services.audit import append_audit_log


router = APIRouter(
    prefix="/api/platform/migrations/appfolio",
    tags=["Platform AppFolio Migration"],
)

_VIEW_ROLES = {
    PlatformUserRole.PLATFORM_ADMIN,
    PlatformUserRole.PLATFORM_TECH,
    PlatformUserRole.PLATFORM_SUPPORT,
    PlatformUserRole.PLATFORM_DEV,
}
_WRITE_ROLES = {
    PlatformUserRole.PLATFORM_ADMIN,
    PlatformUserRole.PLATFORM_TECH,
    PlatformUserRole.PLATFORM_DEV,
}


_MIGRATION_COVERAGE_RESOURCES: tuple[tuple[str, str], ...] = (
    ("PROPERTIES", "Properties"),
    ("UNITS", "Units"),
    ("OWNERS", "Owners"),
    ("VENDORS", "Vendors"),
    ("TENANTS", "Tenants"),
    ("LEASE_OCCUPANCY", "Lease / occupancy"),
    ("GL_ACCOUNTS", "GL Accounts"),
    ("GENERAL_LEDGER", "General Ledger"),
    ("BILLS", "Bills / payables"),
    ("CHARGES", "Charges / receivables"),
    ("SECURITY_DEPOSITS", "Security Deposits"),
    ("WORK_ORDERS", "Work Orders"),
    ("DOCUMENTS", "Attachments / Documents"),
)

_MIGRATION_PARTIAL_BLOCKERS: dict[str, str] = {
    "LEASE_OCCUPANCY": (
        "Lease/occupancy controlled commit is not yet verified from the current "
        "staged relationship contract."
    ),
    "GENERAL_LEDGER": (
        "Historical General Ledger controlled commit is not yet verified; "
        "staging/dry-run/readiness are not equivalent to booked accounting history."
    ),
    "BILLS": (
        "Bills controlled commit is blocked on verified source line-item GL "
        "allocations and deterministic business-date/posting semantics."
    ),
    "CHARGES": (
        "Charges controlled commit is blocked on verified Occupancy/tenant identity "
        "and original-charge/payment semantics."
    ),
    "WORK_ORDERS": (
        "Work Orders controlled commit is blocked because target WorkOrder requires "
        "a verified Unit and tenant/requester identity that the current source "
        "contract does not provide safely."
    ),
}

_MIGRATION_SOURCE_SCHEMA_BLOCKERS: dict[str, str] = {
    "SECURITY_DEPOSITS": (
        "No authoritative Security Deposit report CSV/XLSX field contract is "
        "verified; automatic ingestion must remain disabled."
    ),
    "DOCUMENTS": (
        "No authoritative Attachments/Documents CSV/XLSX or API field contract "
        "is verified for automatic migration mapping."
    ),
}

_ACCOUNTING_COVERAGE_RESOURCES = {
    "GL_ACCOUNTS",
    "GENERAL_LEDGER",
    "BILLS",
    "CHARGES",
    "SECURITY_DEPOSITS",
}

# Generic corrections are deliberately limited to descriptive staging fields.
# Source identity, relationship IDs, amounts, dates, statuses and accounting
# classifications stay under their resource-specific review contracts.
_MIGRATION_CORRECTABLE_FIELDS: dict[str, set[str]] = {
    "PROPERTIES": {"name", "address_line1", "address_line2", "city", "state", "zip_code"},
    "UNITS": {"unit_number", "address_line1", "address_line2", "city", "state", "zip_code"},
    "OWNERS": {"name", "email", "phone"},
    "VENDORS": {"name", "email", "phone"},
    "TENANTS": {"tenant_name", "email", "phone"},
    "LEASE_OCCUPANCY": {"tenant_name"},
    "GL_ACCOUNTS": {"account_name"},
    "GENERAL_LEDGER": {"description", "reference", "remarks"},
    "BILLS": {"description"},
    "CHARGES": {"description"},
    "WORK_ORDERS": {"job_description", "vendor_trade", "permission_to_enter"},
}


def _require_role(
    user: PlatformUser,
    allowed: set[PlatformUserRole],
    detail: str,
) -> None:
    if user.role not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _target_org(db: Session, organization_id: int) -> Organization:
    row = (
        db.query(Organization)
        .filter(
            Organization.id == organization_id,
            Organization.is_active.is_(True),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Target organization not found.")
    return row


def _run(
    db: Session,
    *,
    run_id: int,
    current_user: PlatformUser,
    write: bool,
) -> PlatformMigrationRun:
    _require_role(
        current_user,
        _WRITE_ROLES if write else _VIEW_ROLES,
        "Platform migration access required.",
    )
    row = (
        db.query(PlatformMigrationRun)
        .filter(
            PlatformMigrationRun.id == run_id,
            PlatformMigrationRun.provider == "APPFOLIO",
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="AppFolio migration run not found.")
    _target_org(db, row.organization_id)
    return row


@router.get("/runs", response_model=list[AppFolioMigrationRunOut])
def list_runs(
    response: Response,
    organization_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    _require_role(current_user, _VIEW_ROLES, "Platform migration access required.")
    query = db.query(PlatformMigrationRun).filter(
        PlatformMigrationRun.provider == "APPFOLIO"
    )
    if organization_id is not None:
        _target_org(db, organization_id)
        query = query.filter(PlatformMigrationRun.organization_id == organization_id)
    rows = (
        query.order_by(
            PlatformMigrationRun.created_at.desc(),
            PlatformMigrationRun.id.desc(),
        )
        .limit(limit)
        .all()
    )
    response.headers["Cache-Control"] = "no-store"
    return rows


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/rows/{staged_row_id}/correction",
    response_model=AppFolioMigrationStagedRowOut,
)
def correct_appfolio_staged_row(
    run_id: int,
    upload_id: int,
    staged_row_id: int,
    payload: AppFolioStagedRowCorrectionIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    row = _staged_row(
        db,
        run=run,
        upload=upload,
        staged_row_id=staged_row_id,
    )
    if row.disposition == "INVALID" or row.errors:
        raise HTTPException(
            status_code=409,
            detail="Invalid staged rows cannot be made commit-safe by generic corrections.",
        )

    allowed = _MIGRATION_CORRECTABLE_FIELDS.get(row.resource, set())
    if payload.field_name not in allowed:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Field {payload.field_name!r} is not an approved descriptive "
                f"correction field for {row.resource}."
            ),
        )

    data = dict(row.normalized_data or {})
    if payload.field_name not in data:
        raise HTTPException(
            status_code=409,
            detail="Correction field is not present in the staged normalized source row.",
        )

    corrected = payload.corrected_value.strip()
    if not corrected:
        raise HTTPException(
            status_code=422,
            detail="Corrected value must contain non-whitespace text.",
        )
    previous = data.get(payload.field_name)
    if previous == corrected:
        return row

    corrected_at = datetime.utcnow()
    data[payload.field_name] = corrected
    evidence = list(row.correction_evidence or [])
    evidence.append(
        {
            "kind": "ROW_CORRECTION",
            "field_name": payload.field_name,
            "source_value": previous,
            "corrected_value": corrected,
            "platform_user_id": current_user.id,
            "corrected_at": corrected_at.isoformat(),
        }
    )
    row.normalized_data = data
    row.correction_evidence = evidence
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    run.status = "STAGED"

    append_audit_log(
        db,
        platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_staged_row",
        entity_id=row.id,
        action="appfolio_staged_value_corrected",
        old_value={
            "upload_id": upload.id,
            "resource": row.resource,
            "source_id": row.source_id,
            "field_name": payload.field_name,
            "value": previous,
        },
        new_value={
            "upload_id": upload.id,
            "resource": row.resource,
            "source_id": row.source_id,
            "field_name": payload.field_name,
            "value": corrected,
            "source_file_rewritten": False,
            "customer_target_mutation": False,
            "accounting_mutation": False,
            "dry_run_invalidated": True,
        },
    )
    db.commit()
    db.refresh(row)
    return row


@router.get("/runs/{run_id}", response_model=AppFolioMigrationRunOut)
def get_run(
    run_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=False)
    response.headers["Cache-Control"] = "no-store"
    return row


@router.post(
    "/runs",
    response_model=AppFolioMigrationRunOut,
    status_code=status.HTTP_201_CREATED,
)
def create_run(
    payload: AppFolioMigrationRunCreateIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    _require_role(
        current_user,
        _WRITE_ROLES,
        "Platform admin, tech, or dev role required for migrations.",
    )
    org = _target_org(db, payload.organization_id)
    row = PlatformMigrationRun(
        organization_id=org.id,
        provider="APPFOLIO",
        source_account_ref=payload.source_account_ref,
        status="DRAFT",
        created_by_platform_user_id=current_user.id,
    )
    db.add(row)
    db.flush()
    append_audit_log(
        db,
        platform_user_id=current_user.id,
        organization_id=org.id,
        entity_type="platform_migration_run",
        entity_id=row.id,
        action="created",
        new_value={
            "provider": "APPFOLIO",
            "source_account_ref": row.source_account_ref,
            "status": row.status,
            "credentials_stored": False,
        },
    )
    db.commit()
    db.refresh(row)
    return row


@router.post(
    "/runs/{run_id}/properties/dry-run",
    response_model=AppFolioPropertyDryRunOut,
)
def dry_run_appfolio_properties(
    run_id: int,
    payload: AppFolioPropertyDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    result = dry_run_properties(
        db,
        run=row,
        include_hidden=payload.include_hidden,
        records=payload.records,
    )
    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=row.organization_id,
            entity_type="platform_migration_run",
            entity_id=row.id,
            action="appfolio_properties_dry_run",
            new_value={
                "fingerprint": result.fingerprint,
                **result.summary,
                "raw_payload_stored": False,
                "target_mutation": False,
            },
        )
        db.commit()
        db.refresh(row)

    return AppFolioPropertyDryRunOut(
        run_id=row.id,
        organization_id=row.organization_id,
        provider=row.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        total=result.total,
        importable=result.importable,
        skipped_hidden=result.skipped_hidden,
        invalid=result.invalid,
        warning_count=result.warning_count,
        rows=result.rows,
    )



@router.post(
    "/runs/{run_id}/properties/commit",
    response_model=AppFolioPropertyCommitOut,
)
def commit_appfolio_properties(
    run_id: int,
    payload: AppFolioPropertyCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = commit_properties(
            db,
            run=row,
            include_hidden=payload.include_hidden,
            records=payload.records,
            expected_fingerprint=payload.fingerprint,
            platform_user_id=current_user.id,
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=row.organization_id,
                entity_type="platform_migration_run",
                entity_id=row.id,
                action="appfolio_properties_committed",
                new_value={
                    "fingerprint": result.fingerprint,
                    "committed": result.committed,
                    "skipped_hidden": result.skipped_hidden,
                    "warning_count": result.warning_count,
                    "target_property_ids": [
                        item["target_property_id"] for item in result.rows
                    ],
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
            db.commit()
            db.refresh(row)
    except AppFolioMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Property commit conflicted with an existing migration mapping.",
        ) from exc

    return AppFolioPropertyCommitOut(
        run_id=row.id,
        organization_id=row.organization_id,
        provider=row.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        committed=result.committed,
        matched_existing=result.matched_existing,
        skipped_hidden=result.skipped_hidden,
        warning_count=result.warning_count,
        rows=result.rows,
    )



@router.get(
    "/runs/{run_id}/items",
    response_model=list[AppFolioMigrationItemOut],
)
def list_appfolio_migration_items(
    run_id: int,
    response: Response,
    resource: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Read durable source-to-target mappings without exposing raw provider payloads."""
    row = _run(db, run_id=run_id, current_user=current_user, write=False)

    # Durable mappings are bound to the run's original organization/provider
    # scope. If that relationship is ever inconsistent, fail closed instead of
    # returning an empty list that could hide or appear to rebind mappings.
    inconsistent_mapping = (
        db.query(PlatformMigrationItem.id)
        .filter(
            PlatformMigrationItem.run_id == row.id,
            (
                (PlatformMigrationItem.organization_id != row.organization_id)
                | (PlatformMigrationItem.provider != "APPFOLIO")
            ),
        )
        .first()
    )
    if inconsistent_mapping is not None:
        raise HTTPException(status_code=404, detail="AppFolio migration run not found.")

    query = db.query(PlatformMigrationItem).filter(
        PlatformMigrationItem.run_id == row.id,
        PlatformMigrationItem.organization_id == row.organization_id,
        PlatformMigrationItem.provider == "APPFOLIO",
    )
    if resource is not None:
        normalized_resource = resource.strip().upper()
        if not normalized_resource:
            raise HTTPException(status_code=422, detail="resource cannot be blank.")
        query = query.filter(PlatformMigrationItem.resource == normalized_resource)

    items = (
        query.order_by(
            PlatformMigrationItem.resource.asc(),
            PlatformMigrationItem.source_id.asc(),
            PlatformMigrationItem.id.asc(),
        )
        .limit(limit)
        .all()
    )

    result = []
    for item in items:
        target_exists = False
        target_label = None
        if item.target_entity == "PROPERTY":
            target = (
                db.query(Property)
                .filter(
                    Property.id == item.target_id,
                    Property.organization_id == row.organization_id,
                )
                .first()
            )
            if target is not None:
                target_exists = True
                target_label = target.name
        result.append(
            AppFolioMigrationItemOut(
                id=item.id,
                run_id=item.run_id,
                organization_id=item.organization_id,
                provider=item.provider,
                resource=item.resource,
                source_id=item.source_id,
                target_entity=item.target_entity,
                target_id=item.target_id,
                target_exists=target_exists,
                target_label=target_label,
                source_fingerprint=item.source_fingerprint,
                created_by_platform_user_id=item.created_by_platform_user_id,
                created_at=item.created_at,
            )
        )
    response.headers["Cache-Control"] = "no-store"
    return result



def _upload(
    db: Session,
    *,
    run: PlatformMigrationRun,
    upload_id: int,
) -> PlatformMigrationUpload:
    row = (
        db.query(PlatformMigrationUpload)
        .filter(
            PlatformMigrationUpload.id == upload_id,
            PlatformMigrationUpload.run_id == run.id,
            PlatformMigrationUpload.organization_id == run.organization_id,
            PlatformMigrationUpload.provider == "APPFOLIO",
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="AppFolio staged upload not found.")
    return row


def _upload_out(row: PlatformMigrationUpload, *, replayed: bool) -> AppFolioMigrationUploadOut:
    return AppFolioMigrationUploadOut(
        id=row.id,
        run_id=row.run_id,
        organization_id=row.organization_id,
        provider=row.provider,
        filename=row.filename,
        file_format=row.file_format,
        file_sha256=row.file_sha256,
        normalized_fingerprint=row.normalized_fingerprint,
        detected_resource=row.detected_resource,
        sheet_name=row.sheet_name,
        headers=list(row.headers or []),
        column_mapping=dict(row.column_mapping or {}),
        validation_summary=dict(row.validation_summary or {}),
        status=row.status,
        row_count=row.row_count,
        created_by_platform_user_id=row.created_by_platform_user_id,
        created_at=row.created_at,
        replayed=replayed,
    )


def _staged_row(
    db: Session,
    *,
    run: PlatformMigrationRun,
    upload: PlatformMigrationUpload,
    staged_row_id: int,
) -> PlatformMigrationStagedRow:
    row = (
        db.query(PlatformMigrationStagedRow)
        .filter(
            PlatformMigrationStagedRow.id == staged_row_id,
            PlatformMigrationStagedRow.upload_id == upload.id,
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.organization_id == run.organization_id,
            PlatformMigrationStagedRow.provider == "APPFOLIO",
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="AppFolio staged row not found.")
    return row


def _staged_review_fingerprint(
    upload: PlatformMigrationUpload,
    rows: list[PlatformMigrationStagedRow],
) -> str:
    upload_run = getattr(upload, "run", None)
    active_rules = sorted(
        (
            rule
            for rule in (getattr(upload_run, "correction_rules", None) or [])
            if rule.provider == "APPFOLIO"
            and rule.resource == upload.detected_resource
        ),
        key=lambda rule: (
            rule.resource,
            rule.field_name,
            rule.source_value,
            rule.id or 0,
        ),
    )
    canonical = {
        "upload_normalized_fingerprint": upload.normalized_fingerprint,
        "correction_rules": [
            {
                "resource": rule.resource,
                "field_name": rule.field_name,
                "source_value": rule.source_value,
                "corrected_value": rule.corrected_value,
            }
            for rule in active_rules
        ],
        "rows": [
            {
                "id": row.id,
                "row_number": row.row_number,
                "source_id": row.source_id,
                "row_fingerprint": row.row_fingerprint,
                "normalized_data": row.normalized_data,
                "correction_evidence": row.correction_evidence,
                "disposition": row.disposition,
                "resolution_action": row.resolution_action,
                "resolution_target_id": row.resolution_target_id,
                "resolution_target_unit_id": row.resolution_target_unit_id,
                "resolution_target_owner_user_id": row.resolution_target_owner_user_id,
                "resolution_target_vendor_id": row.resolution_target_vendor_id,
                "resolution_target_tenant_user_id": row.resolution_target_tenant_user_id,
                "resolution_target_gl_account_id": row.resolution_target_gl_account_id,
            }
            for row in rows
        ],
    }
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _staged_property_state(
    db: Session,
    *,
    run: PlatformMigrationRun,
    upload: PlatformMigrationUpload,
) -> tuple[list[dict[str, object]], dict[str, int], set[str], str]:
    if upload.detected_resource != "PROPERTIES":
        raise HTTPException(
            status_code=409,
            detail="Staged upload must be resolved to PROPERTIES before property dry run.",
        )
    rows = (
        db.query(PlatformMigrationStagedRow)
        .filter(
            PlatformMigrationStagedRow.upload_id == upload.id,
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.organization_id == run.organization_id,
            PlatformMigrationStagedRow.provider == "APPFOLIO",
        )
        .order_by(
            PlatformMigrationStagedRow.row_number.asc(),
            PlatformMigrationStagedRow.id.asc(),
        )
        .all()
    )
    if not rows:
        raise HTTPException(status_code=409, detail="Staged upload has no property rows.")

    blocking: list[PlatformMigrationStagedRow] = []
    for row in rows:
        if row.disposition == "INVALID":
            blocking.append(row)
        elif row.disposition == "POSSIBLE_MATCH" and row.resolution_action not in {
            "MATCH_EXISTING",
            "CREATE_NEW",
            "SKIP",
        }:
            blocking.append(row)
        elif row.disposition == "REVIEW" and row.resolution_action != "SKIP":
            blocking.append(row)
    if blocking:
        counts: dict[str, int] = {}
        for row in blocking:
            counts[row.disposition] = counts.get(row.disposition, 0) + 1
        detail = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
        raise HTTPException(
            status_code=409,
            detail=(
                "Staged property dry run is blocked by unresolved rows: "
                f"{detail}. Resolve staged validation/match decisions before continuing."
            ),
        )

    records: list[dict[str, object]] = []
    resolved_existing: dict[str, int] = {}
    force_create_new: set[str] = set()

    for row in rows:
        if row.resolution_action == "SKIP":
            continue
        data = dict(row.normalized_data or {})
        source_id = row.source_id or data.get("source_id")
        if row.resolution_action == "MATCH_EXISTING":
            if not source_id or row.resolution_target_id is None:
                raise HTTPException(
                    status_code=409,
                    detail="Resolved staged property match is incomplete.",
                )
            resolved_existing[str(source_id)] = int(row.resolution_target_id)
        elif row.resolution_action == "CREATE_NEW":
            if not source_id:
                raise HTTPException(
                    status_code=409,
                    detail="Resolved staged property create-new row lacks a source ID.",
                )
            force_create_new.add(str(source_id))

        records.append(
            {
                "Id": source_id,
                "Name": data.get("name"),
                "Address1": data.get("address_line1"),
                "Address2": data.get("address_line2"),
                "City": data.get("city"),
                "State": data.get("state"),
                "Zip": data.get("zip_code"),
                "PropertyType": data.get("property_type"),
                "HiddenAt": data.get("hidden_at"),
            }
        )
    if not records:
        raise HTTPException(
            status_code=409,
            detail="No staged property rows remain after explicit skip decisions.",
        )
    return (
        records,
        resolved_existing,
        force_create_new,
        _staged_review_fingerprint(upload, rows),
    )


def _staged_unit_state(
    db: Session,
    *,
    run: PlatformMigrationRun,
    upload: PlatformMigrationUpload,
) -> tuple[list[dict[str, object]], dict[str, int], set[str], str]:
    if upload.detected_resource != "UNITS":
        raise HTTPException(
            status_code=409,
            detail="Staged upload must be resolved to UNITS before Unit dry run.",
        )
    rows = (
        db.query(PlatformMigrationStagedRow)
        .filter(
            PlatformMigrationStagedRow.upload_id == upload.id,
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.organization_id == run.organization_id,
            PlatformMigrationStagedRow.provider == "APPFOLIO",
            PlatformMigrationStagedRow.resource == "UNITS",
        )
        .order_by(
            PlatformMigrationStagedRow.row_number.asc(),
            PlatformMigrationStagedRow.id.asc(),
        )
        .all()
    )
    if not rows:
        raise HTTPException(status_code=409, detail="Staged upload has no Unit rows.")

    blocking: list[PlatformMigrationStagedRow] = []
    for row in rows:
        if row.errors or row.disposition == "INVALID":
            blocking.append(row)
        elif row.disposition == "POSSIBLE_MATCH" and row.resolution_action not in {
            "MATCH_EXISTING",
            "CREATE_NEW",
            "SKIP",
        }:
            blocking.append(row)
        elif row.disposition == "REVIEW" and row.resolution_action != "SKIP":
            blocking.append(row)
        elif row.disposition == "ALREADY_MAPPED" and row.resolution_action is not None:
            blocking.append(row)
        elif row.resolution_action == "CREATE_NEW" and row.disposition != "POSSIBLE_MATCH":
            blocking.append(row)
    if blocking:
        counts: dict[str, int] = {}
        for row in blocking:
            counts[row.disposition] = counts.get(row.disposition, 0) + 1
        detail = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
        raise HTTPException(
            status_code=409,
            detail=(
                "Staged Unit dry run is blocked by unresolved rows: "
                f"{detail}. Resolve staged Unit validation/match decisions before continuing."
            ),
        )

    records: list[dict[str, object]] = []
    resolved_existing: dict[str, int] = {}
    force_create_new: set[str] = set()
    property_links: list[dict[str, object]] = []
    seen_property_sources: set[str] = set()

    for row in rows:
        if row.resolution_action == "SKIP":
            continue
        data = dict(row.normalized_data or {})
        source_id = row.source_id or data.get("source_id")
        source_property_id = data.get("source_property_id")
        if not source_id or not source_property_id:
            raise HTTPException(
                status_code=409,
                detail="Staged Unit row lacks durable Unit or Property source identity.",
            )
        source_key = str(source_id).strip()
        property_source = str(source_property_id).strip()
        mapping = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "APPFOLIO",
                PlatformMigrationItem.resource == "PROPERTIES",
                PlatformMigrationItem.source_id == property_source,
            )
            .first()
        )
        if mapping is None or mapping.target_entity != "PROPERTY":
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Source Property ID {property_source} no longer has a valid durable Property mapping."
                ),
            )
        target_property = (
            db.query(Property)
            .filter(
                Property.id == mapping.target_id,
                Property.organization_id == run.organization_id,
                Property.is_active.is_(True),
                Property.deleted_at.is_(None),
            )
            .first()
        )
        if target_property is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Source Property ID {property_source} no longer maps to an active same-organization Property."
                ),
            )

        if row.resolution_action == "MATCH_EXISTING":
            if row.resolution_target_unit_id is None:
                raise HTTPException(
                    status_code=409,
                    detail="Resolved staged Unit match is missing its Unit target.",
                )
            target_unit = (
                db.query(Unit)
                .filter(
                    Unit.id == row.resolution_target_unit_id,
                    Unit.property_id == target_property.id,
                    Unit.is_active.is_(True),
                    Unit.deleted_at.is_(None),
                )
                .first()
            )
            if target_unit is None:
                raise HTTPException(
                    status_code=409,
                    detail="Resolved staged Unit target is no longer active under the mapped Property.",
                )
            resolved_existing[source_key] = target_unit.id
        elif row.resolution_action == "CREATE_NEW":
            force_create_new.add(source_key)

        if property_source not in seen_property_sources:
            seen_property_sources.add(property_source)
            property_links.append(
                {
                    "source_property_id": property_source,
                    "target_property_id": mapping.target_id,
                    "source_fingerprint": mapping.source_fingerprint,
                }
            )
        records.append(
            {
                "Id": source_key,
                "PropertyId": property_source,
                "UnitName": data.get("unit_name"),
                "UnitAddress": data.get("unit_address"),
                "Address1": data.get("address_line1"),
                "Address2": data.get("address_line2"),
                "City": data.get("city"),
                "State": data.get("state"),
                "Zip": data.get("zip_code"),
            }
        )

    if not records:
        raise HTTPException(
            status_code=409,
            detail="No staged Unit rows remain after explicit skip decisions.",
        )

    canonical = {
        "staged_review_fingerprint": _staged_review_fingerprint(upload, rows),
        "property_links": sorted(
            property_links,
            key=lambda item: str(item["source_property_id"]),
        ),
    }
    relationship_fingerprint = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return records, resolved_existing, force_create_new, relationship_fingerprint


def _staged_owner_state(
    db: Session,
    *,
    run: PlatformMigrationRun,
    upload: PlatformMigrationUpload,
) -> tuple[list[dict[str, object]], dict[str, int], str]:
    if upload.detected_resource != "OWNERS":
        raise HTTPException(
            status_code=409,
            detail="Staged upload must be resolved to OWNERS before Owner dry run.",
        )
    rows = (
        db.query(PlatformMigrationStagedRow)
        .filter(
            PlatformMigrationStagedRow.upload_id == upload.id,
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.organization_id == run.organization_id,
            PlatformMigrationStagedRow.provider == "APPFOLIO",
            PlatformMigrationStagedRow.resource == "OWNERS",
        )
        .order_by(
            PlatformMigrationStagedRow.row_number.asc(),
            PlatformMigrationStagedRow.id.asc(),
        )
        .all()
    )
    if not rows:
        raise HTTPException(status_code=409, detail="Staged upload has no Owner rows.")

    blocking: list[PlatformMigrationStagedRow] = []
    for row in rows:
        if row.errors or row.disposition == "INVALID":
            blocking.append(row)
        elif row.disposition == "REVIEW" and row.resolution_action != "SKIP":
            blocking.append(row)
        elif row.disposition in {"POSSIBLE_MATCH", "NEW"} and row.resolution_action not in {
            "MATCH_EXISTING", "SKIP",
        }:
            blocking.append(row)
        elif row.disposition == "ALREADY_MAPPED" and row.resolution_action is not None:
            blocking.append(row)
        elif row.resolution_action == "CREATE_NEW":
            blocking.append(row)
    if blocking:
        counts: dict[str, int] = {}
        for row in blocking:
            counts[row.disposition] = counts.get(row.disposition, 0) + 1
        detail = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
        raise HTTPException(
            status_code=409,
            detail=(
                "Staged Owner dry run is blocked by unresolved rows: "
                f"{detail}. Owner CREATE_NEW is intentionally unsupported; "
                "match an existing OWNER user or skip the staged row."
            ),
        )

    records: list[dict[str, object]] = []
    resolved_existing: dict[str, int] = {}
    for row in rows:
        if row.resolution_action == "SKIP":
            continue
        data = dict(row.normalized_data or {})
        source_id = row.source_id or data.get("source_id")
        owner_name = data.get("name")
        if not source_id or not owner_name:
            raise HTTPException(
                status_code=409,
                detail="Staged Owner row lacks durable Owner source identity or display name.",
            )
        source_key = str(source_id).strip()
        if row.resolution_action == "MATCH_EXISTING":
            if row.resolution_target_owner_user_id is None:
                raise HTTPException(
                    status_code=409,
                    detail="Resolved staged Owner match is missing its OWNER-user target.",
                )
            target = (
                db.query(User)
                .filter(
                    User.id == row.resolution_target_owner_user_id,
                    User.organization_id == run.organization_id,
                    User.role == UserRole.OWNER,
                    User.is_active.is_(True),
                    User.deleted_at.is_(None),
                )
                .first()
            )
            if target is None:
                raise HTTPException(
                    status_code=409,
                    detail="Resolved staged Owner target is no longer an active OWNER in this organization.",
                )
            resolved_existing[source_key] = target.id

        records.append({
            "Owner ID": source_key,
            "Name": owner_name,
            "Phone Numbers": data.get("phone_numbers"),
            "Email": data.get("email"),
            "Properties Owned": data.get("properties_owned"),
            "Properties Owned IDs": data.get("properties_owned_ids"),
        })

    if not records:
        raise HTTPException(
            status_code=409,
            detail="No staged Owner rows remain after explicit skip decisions.",
        )
    return records, resolved_existing, _staged_review_fingerprint(upload, rows)


def _staged_tenant_state(
    db: Session,
    *,
    run: PlatformMigrationRun,
    upload: PlatformMigrationUpload,
) -> tuple[list[dict[str, object]], dict[str, int], str]:
    if upload.detected_resource != "TENANTS":
        raise HTTPException(
            status_code=409,
            detail="Staged upload must be resolved to TENANTS before Tenant dry run.",
        )
    rows = (
        db.query(PlatformMigrationStagedRow)
        .filter(
            PlatformMigrationStagedRow.upload_id == upload.id,
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.organization_id == run.organization_id,
            PlatformMigrationStagedRow.provider == "APPFOLIO",
            PlatformMigrationStagedRow.resource == "TENANTS",
        )
        .order_by(
            PlatformMigrationStagedRow.row_number.asc(),
            PlatformMigrationStagedRow.id.asc(),
        )
        .all()
    )
    if not rows:
        raise HTTPException(status_code=409, detail="Staged upload has no Tenant rows.")

    blocking: list[PlatformMigrationStagedRow] = []
    for row in rows:
        if row.errors or row.disposition == "INVALID":
            blocking.append(row)
        elif row.disposition == "REVIEW" and row.resolution_action != "SKIP":
            blocking.append(row)
        elif row.disposition in {"POSSIBLE_MATCH", "NEW"} and row.resolution_action not in {
            "MATCH_EXISTING", "SKIP",
        }:
            blocking.append(row)
        elif row.disposition == "ALREADY_MAPPED" and row.resolution_action is not None:
            blocking.append(row)
        elif row.resolution_action == "CREATE_NEW":
            blocking.append(row)
    if blocking:
        counts: dict[str, int] = {}
        for row in blocking:
            counts[row.disposition] = counts.get(row.disposition, 0) + 1
        detail = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
        raise HTTPException(
            status_code=409,
            detail=(
                "Staged Tenant dry run is blocked by unresolved rows: "
                f"{detail}. Tenant CREATE_NEW is intentionally unsupported; "
                "match an existing TENANT user or skip the staged row."
            ),
        )

    records: list[dict[str, object]] = []
    resolved_existing: dict[str, int] = {}
    property_links: dict[str, dict[str, object]] = {}
    unit_links: dict[str, dict[str, object]] = {}

    for row in rows:
        if row.resolution_action == "SKIP":
            continue
        data = dict(row.normalized_data or {})
        source_id = row.source_id or data.get("source_id")
        source_property_id = data.get("source_property_id")
        source_unit_id = data.get("source_unit_id")
        tenant_name = data.get("tenant_name")
        if not source_id or not source_property_id or not source_unit_id or not tenant_name:
            raise HTTPException(
                status_code=409,
                detail="Staged Tenant row lacks durable Tenant/Property/Unit identity or display name.",
            )
        source_key = str(source_id).strip()
        property_source = str(source_property_id).strip()
        unit_source = str(source_unit_id).strip()

        property_mapping = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "APPFOLIO",
                PlatformMigrationItem.resource == "PROPERTIES",
                PlatformMigrationItem.source_id == property_source,
            )
            .first()
        )
        unit_mapping = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "APPFOLIO",
                PlatformMigrationItem.resource == "UNITS",
                PlatformMigrationItem.source_id == unit_source,
            )
            .first()
        )
        if property_mapping is None or property_mapping.target_entity != "PROPERTY":
            raise HTTPException(
                status_code=409,
                detail=f"Source Property ID {property_source} no longer has a valid durable Property mapping.",
            )
        if unit_mapping is None or unit_mapping.target_entity != "UNIT":
            raise HTTPException(
                status_code=409,
                detail=f"Source Unit ID {unit_source} no longer has a valid durable Unit mapping.",
            )
        target_property = (
            db.query(Property)
            .filter(
                Property.id == property_mapping.target_id,
                Property.organization_id == run.organization_id,
                Property.is_active.is_(True),
                Property.deleted_at.is_(None),
            )
            .first()
        )
        target_unit = (
            db.query(Unit)
            .filter(
                Unit.id == unit_mapping.target_id,
                Unit.property_id == property_mapping.target_id,
                Unit.is_active.is_(True),
                Unit.deleted_at.is_(None),
            )
            .first()
        )
        if target_property is None or target_unit is None:
            raise HTTPException(
                status_code=409,
                detail="Tenant source relationship no longer resolves to an active same-organization Unit/Property pair.",
            )

        if row.resolution_action == "MATCH_EXISTING":
            if row.resolution_target_tenant_user_id is None:
                raise HTTPException(
                    status_code=409,
                    detail="Resolved staged Tenant match is missing its TENANT-user target.",
                )
            target_tenant = (
                db.query(User)
                .filter(
                    User.id == row.resolution_target_tenant_user_id,
                    User.organization_id == run.organization_id,
                    User.role == UserRole.TENANT,
                    User.is_active.is_(True),
                    User.deleted_at.is_(None),
                )
                .first()
            )
            if target_tenant is None:
                raise HTTPException(
                    status_code=409,
                    detail="Resolved staged Tenant target is no longer an active TENANT in this organization.",
                )
            resolved_existing[source_key] = target_tenant.id

        property_links[property_source] = {
            "source_property_id": property_source,
            "target_property_id": property_mapping.target_id,
            "source_fingerprint": property_mapping.source_fingerprint,
        }
        unit_links[unit_source] = {
            "source_unit_id": unit_source,
            "target_unit_id": unit_mapping.target_id,
            "target_property_id": target_unit.property_id,
            "source_fingerprint": unit_mapping.source_fingerprint,
        }
        records.append({
            "Tenant ID": source_key,
            "Tenant": tenant_name,
            "Phone Numbers": data.get("phone_numbers"),
            "Emails": data.get("emails"),
            "Property ID": property_source,
            "Unit ID": unit_source,
            "Move-in": data.get("move_in"),
            "Move-out": data.get("move_out"),
            "Lease From": data.get("lease_from"),
            "Lease To": data.get("lease_to"),
        })

    if not records:
        raise HTTPException(
            status_code=409,
            detail="No staged Tenant rows remain after explicit skip decisions.",
        )

    canonical = {
        "staged_review_fingerprint": _staged_review_fingerprint(upload, rows),
        "property_links": sorted(
            property_links.values(), key=lambda item: str(item["source_property_id"])
        ),
        "unit_links": sorted(
            unit_links.values(), key=lambda item: str(item["source_unit_id"])
        ),
    }
    relationship_fingerprint = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return records, resolved_existing, relationship_fingerprint


def _staged_gl_account_state(
    db: Session,
    *,
    run: PlatformMigrationRun,
    upload: PlatformMigrationUpload,
) -> tuple[list[dict[str, object]], dict[str, int], str]:
    if upload.detected_resource != "GL_ACCOUNTS":
        raise HTTPException(
            status_code=409,
            detail="Staged upload must be resolved to GL_ACCOUNTS before GL Account dry run.",
        )
    rows = (
        db.query(PlatformMigrationStagedRow)
        .filter(
            PlatformMigrationStagedRow.upload_id == upload.id,
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.organization_id == run.organization_id,
            PlatformMigrationStagedRow.provider == "APPFOLIO",
            PlatformMigrationStagedRow.resource == "GL_ACCOUNTS",
        )
        .order_by(
            PlatformMigrationStagedRow.row_number.asc(),
            PlatformMigrationStagedRow.id.asc(),
        )
        .all()
    )
    if not rows:
        raise HTTPException(status_code=409, detail="Staged upload has no GL Account rows.")

    blocking: list[PlatformMigrationStagedRow] = []
    for row in rows:
        if row.errors or row.disposition == "INVALID":
            blocking.append(row)
        elif row.disposition == "REVIEW" and row.resolution_action not in {
            "MATCH_EXISTING",
            "SKIP",
        }:
            blocking.append(row)
        elif row.disposition == "ALREADY_MAPPED" and row.resolution_action is not None:
            blocking.append(row)
        elif row.disposition not in {"REVIEW", "ALREADY_MAPPED"}:
            blocking.append(row)
    if blocking:
        counts: dict[str, int] = {}
        for row in blocking:
            counts[row.disposition] = counts.get(row.disposition, 0) + 1
        detail = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
        raise HTTPException(
            status_code=409,
            detail=(
                "Staged GL Account dry run is blocked by unresolved rows: "
                f"{detail}. Match an existing active GL Account or skip each REVIEW row."
            ),
        )

    records: list[dict[str, object]] = []
    resolved_existing: dict[str, int] = {}
    for row in rows:
        if row.resolution_action == "SKIP":
            continue
        data = dict(row.normalized_data or {})
        source_id = row.source_id or data.get("source_id")
        account_number = data.get("account_number")
        account_name = data.get("account_name")
        source_type = data.get("account_type")
        if not source_id or not account_number or not account_name or not source_type:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Staged GL Account row lacks stable source ID, Number, Name or Type; "
                    "unsafe rows must be skipped before dry run."
                ),
            )
        source_key = str(source_id).strip()

        if row.resolution_action == "MATCH_EXISTING":
            if row.resolution_target_gl_account_id is None:
                raise HTTPException(
                    status_code=409,
                    detail="Resolved staged GL Account match is missing its target.",
                )
            target = (
                db.query(GLAccount)
                .filter(
                    GLAccount.id == row.resolution_target_gl_account_id,
                    GLAccount.organization_id == run.organization_id,
                    GLAccount.is_active.is_(True),
                    GLAccount.deleted_at.is_(None),
                )
                .first()
            )
            if target is None:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Resolved staged GL Account target is no longer active in "
                        "this organization."
                    ),
                )
            resolved_existing[source_key] = target.id

        records.append(
            {
                "GL Account ID": source_key,
                "Number": account_number,
                "Name": account_name,
                "Type": source_type,
                "FundAccount": data.get("fund_account"),
                "IsCorporateAccount": data.get("is_corporate_account"),
                "OffsetAccountId": data.get("offset_account_id"),
                "ParentGlAccountId": data.get("parent_gl_account_id"),
                "PropertyIds": data.get("property_ids"),
                "LastUpdatedAt": data.get("last_updated_at"),
            }
        )

    if not records:
        raise HTTPException(
            status_code=409,
            detail="No staged GL Account rows remain after explicit skip decisions.",
        )
    return records, resolved_existing, _staged_review_fingerprint(upload, rows)


def _staged_bill_dry_run_state(
    db: Session,
    *,
    run: PlatformMigrationRun,
    upload: PlatformMigrationUpload,
) -> tuple[list[dict[str, object]], str, dict[str, int]]:
    if upload.detected_resource != "BILLS":
        raise HTTPException(
            status_code=409,
            detail="Staged upload must be BILLS before Bills dry run.",
        )
    rows = (
        db.query(PlatformMigrationStagedRow)
        .filter(
            PlatformMigrationStagedRow.upload_id == upload.id,
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.organization_id == run.organization_id,
            PlatformMigrationStagedRow.provider == "APPFOLIO",
            PlatformMigrationStagedRow.resource == "BILLS",
        )
        .order_by(
            PlatformMigrationStagedRow.row_number.asc(),
            PlatformMigrationStagedRow.id.asc(),
        )
        .all()
    )
    if not rows:
        raise HTTPException(status_code=409, detail="Staged upload has no Bill rows.")

    blocking = [
        row
        for row in rows
        if row.errors
        or row.disposition == "INVALID"
        or (
            row.disposition == "REVIEW"
            and row.resolution_action not in {"ACCEPT_RELATIONSHIP", "SKIP"}
        )
    ]
    if blocking:
        raise HTTPException(
            status_code=409,
            detail="Bills dry run is blocked by invalid or unresolved staged rows.",
        )

    previews: list[dict[str, object]] = []
    relationship_links: list[dict[str, object]] = []
    skipped = 0
    for row in rows:
        if row.resolution_action == "SKIP":
            skipped += 1
            continue
        if row.resolution_action != "ACCEPT_RELATIONSHIP" or not row.source_id:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Every retained Bill row must have stable Bill ID identity "
                    "and explicit ACCEPT_RELATIONSHIP review."
                ),
            )

        data = dict(row.normalized_data or {})
        source_vendor_id = str(data.get("source_vendor_id") or "").strip()
        source_property_id = str(data.get("source_property_id") or "").strip()
        vendor_mapping = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "APPFOLIO",
                PlatformMigrationItem.resource == "VENDORS",
                PlatformMigrationItem.source_id == source_vendor_id,
            )
            .first()
        )
        if (
            vendor_mapping is None
            or vendor_mapping.target_entity != "VENDOR"
            or row.resolution_target_vendor_id != vendor_mapping.target_id
        ):
            raise HTTPException(
                status_code=409,
                detail="Accepted Bill Vendor relationship is stale or inconsistent.",
            )
        target_vendor = (
            db.query(Vendor)
            .filter(
                Vendor.id == vendor_mapping.target_id,
                Vendor.organization_id == run.organization_id,
                Vendor.is_active.is_(True),
                Vendor.deleted_at.is_(None),
            )
            .first()
        )
        if target_vendor is None:
            raise HTTPException(
                status_code=409,
                detail="Accepted Bill Vendor target is no longer active.",
            )

        target_property_id = None
        property_mapping_fingerprint = None
        if source_property_id:
            property_mapping = (
                db.query(PlatformMigrationItem)
                .filter(
                    PlatformMigrationItem.run_id == run.id,
                    PlatformMigrationItem.organization_id == run.organization_id,
                    PlatformMigrationItem.provider == "APPFOLIO",
                    PlatformMigrationItem.resource == "PROPERTIES",
                    PlatformMigrationItem.source_id == source_property_id,
                )
                .first()
            )
            if (
                property_mapping is None
                or property_mapping.target_entity != "PROPERTY"
                or row.resolution_target_id != property_mapping.target_id
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Accepted Bill Property relationship is stale or inconsistent.",
                )
            target_property = (
                db.query(Property)
                .filter(
                    Property.id == property_mapping.target_id,
                    Property.organization_id == run.organization_id,
                    Property.is_active.is_(True),
                    Property.deleted_at.is_(None),
                )
                .first()
            )
            if target_property is None:
                raise HTTPException(
                    status_code=409,
                    detail="Accepted Bill Property target is no longer active.",
                )
            target_property_id = target_property.id
            property_mapping_fingerprint = property_mapping.source_fingerprint

        relationship_links.append(
            {
                "source_bill_id": row.source_id,
                "source_vendor_id": source_vendor_id,
                "target_vendor_id": target_vendor.id,
                "vendor_mapping_fingerprint": vendor_mapping.source_fingerprint,
                "source_property_id": source_property_id or None,
                "target_property_id": target_property_id,
                "property_mapping_fingerprint": property_mapping_fingerprint,
            }
        )
        previews.append(
            {
                "source_id": row.source_id,
                "source_evidence": {
                    "source_vendor_id": source_vendor_id,
                    "source_property_id": source_property_id or None,
                    "due_date": data.get("due_date"),
                    "invoice_date": data.get("invoice_date"),
                    "posting_date": data.get("posting_date"),
                    "reference": data.get("reference"),
                    "remarks": data.get("remarks"),
                    "total_amount": data.get("total_amount"),
                    "approval_status": data.get("approval_status"),
                    "check_memo": data.get("check_memo"),
                    "account_number": data.get("account_number"),
                    "management_company_as_payee": data.get("management_company_as_payee"),
                    "source_work_order_id": data.get("source_work_order_id"),
                    "last_updated_at": data.get("last_updated_at"),
                },
                "resolved_targets": {
                    "vendor_id": target_vendor.id,
                    "property_id": target_property_id,
                },
                "warnings": [
                    (
                        "Dry run is review-only: approval, paid/unpaid state, "
                        "check/payment linkage, GL allocation, Work Order linkage "
                        "and posting semantics are not inferred."
                    )
                ],
            }
        )

    if not previews:
        raise HTTPException(
            status_code=409,
            detail="Bills dry run requires at least one accepted staged row.",
        )

    canonical = {
        "staged_review_fingerprint": _staged_review_fingerprint(upload, rows),
        "relationship_links": sorted(
            relationship_links,
            key=lambda item: str(item["source_bill_id"]),
        ),
    }
    fingerprint = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    counts = {
        "total": len(previews),
        "importable": len(previews),
        "invalid": 0,
        "warning_count": len(previews),
        "skipped": skipped,
    }
    return previews, fingerprint, counts


def _staged_work_order_dry_run_state(
    db: Session,
    *,
    run: PlatformMigrationRun,
    upload: PlatformMigrationUpload,
) -> tuple[list[dict[str, object]], str, dict[str, int]]:
    if upload.detected_resource != "WORK_ORDERS":
        raise HTTPException(
            status_code=409,
            detail="Staged upload must be WORK_ORDERS before Work Orders dry run.",
        )
    rows = (
        db.query(PlatformMigrationStagedRow)
        .filter(
            PlatformMigrationStagedRow.upload_id == upload.id,
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.organization_id == run.organization_id,
            PlatformMigrationStagedRow.provider == "APPFOLIO",
            PlatformMigrationStagedRow.resource == "WORK_ORDERS",
        )
        .order_by(
            PlatformMigrationStagedRow.row_number.asc(),
            PlatformMigrationStagedRow.id.asc(),
        )
        .all()
    )
    if not rows:
        raise HTTPException(
            status_code=409,
            detail="Staged upload has no Work Order rows.",
        )

    blocking = [
        row
        for row in rows
        if row.errors
        or row.disposition == "INVALID"
        or (
            row.disposition == "REVIEW"
            and row.resolution_action not in {"ACCEPT_RELATIONSHIP", "SKIP"}
        )
    ]
    if blocking:
        raise HTTPException(
            status_code=409,
            detail="Work Orders dry run is blocked by invalid or unresolved staged rows.",
        )

    previews: list[dict[str, object]] = []
    relationship_links: list[dict[str, object]] = []
    skipped = 0

    for row in rows:
        if row.resolution_action == "SKIP":
            skipped += 1
            continue
        if row.resolution_action != "ACCEPT_RELATIONSHIP" or not row.source_id:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Every retained Work Order row must have stable Work Order ID "
                    "identity and explicit ACCEPT_RELATIONSHIP review."
                ),
            )

        data = dict(row.normalized_data or {})
        source_property_id = str(data.get("source_property_id") or "").strip()
        source_unit_id = str(data.get("source_unit_id") or "").strip()
        source_vendor_id = str(data.get("source_vendor_id") or "").strip()
        if not source_property_id:
            raise HTTPException(
                status_code=409,
                detail="Accepted Work Order row is missing source PropertyId.",
            )

        property_mapping = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "APPFOLIO",
                PlatformMigrationItem.resource == "PROPERTIES",
                PlatformMigrationItem.source_id == source_property_id,
            )
            .first()
        )
        if (
            property_mapping is None
            or property_mapping.target_entity != "PROPERTY"
            or row.resolution_target_id != property_mapping.target_id
        ):
            raise HTTPException(
                status_code=409,
                detail="Accepted Work Order Property relationship is stale or inconsistent.",
            )
        target_property = (
            db.query(Property)
            .filter(
                Property.id == property_mapping.target_id,
                Property.organization_id == run.organization_id,
                Property.is_active.is_(True),
                Property.deleted_at.is_(None),
            )
            .first()
        )
        if target_property is None:
            raise HTTPException(
                status_code=409,
                detail="Accepted Work Order Property target is no longer active.",
            )

        target_unit_id = None
        unit_mapping_fingerprint = None
        if source_unit_id:
            unit_mapping = (
                db.query(PlatformMigrationItem)
                .filter(
                    PlatformMigrationItem.run_id == run.id,
                    PlatformMigrationItem.organization_id == run.organization_id,
                    PlatformMigrationItem.provider == "APPFOLIO",
                    PlatformMigrationItem.resource == "UNITS",
                    PlatformMigrationItem.source_id == source_unit_id,
                )
                .first()
            )
            if (
                unit_mapping is None
                or unit_mapping.target_entity != "UNIT"
                or row.resolution_target_unit_id != unit_mapping.target_id
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Accepted Work Order Unit relationship is stale or inconsistent.",
                )
            target_unit = (
                db.query(Unit)
                .join(Property, Property.id == Unit.property_id)
                .filter(
                    Unit.id == unit_mapping.target_id,
                    Unit.is_active.is_(True),
                    Unit.deleted_at.is_(None),
                    Property.organization_id == run.organization_id,
                    Property.is_active.is_(True),
                    Property.deleted_at.is_(None),
                )
                .first()
            )
            if target_unit is None:
                raise HTTPException(
                    status_code=409,
                    detail="Accepted Work Order Unit target is no longer active.",
                )
            if target_unit.property_id != target_property.id:
                raise HTTPException(
                    status_code=409,
                    detail="Accepted Work Order Unit no longer belongs to the accepted Property.",
                )
            target_unit_id = target_unit.id
            unit_mapping_fingerprint = unit_mapping.source_fingerprint
        elif row.resolution_target_unit_id is not None:
            raise HTTPException(
                status_code=409,
                detail="Accepted Work Order Unit snapshot is inconsistent with source evidence.",
            )

        target_vendor_id = None
        vendor_mapping_fingerprint = None
        if source_vendor_id:
            vendor_mapping = (
                db.query(PlatformMigrationItem)
                .filter(
                    PlatformMigrationItem.run_id == run.id,
                    PlatformMigrationItem.organization_id == run.organization_id,
                    PlatformMigrationItem.provider == "APPFOLIO",
                    PlatformMigrationItem.resource == "VENDORS",
                    PlatformMigrationItem.source_id == source_vendor_id,
                )
                .first()
            )
            if (
                vendor_mapping is None
                or vendor_mapping.target_entity != "VENDOR"
                or row.resolution_target_vendor_id != vendor_mapping.target_id
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Accepted Work Order Vendor relationship is stale or inconsistent.",
                )
            target_vendor = (
                db.query(Vendor)
                .filter(
                    Vendor.id == vendor_mapping.target_id,
                    Vendor.organization_id == run.organization_id,
                    Vendor.is_active.is_(True),
                    Vendor.deleted_at.is_(None),
                )
                .first()
            )
            if target_vendor is None:
                raise HTTPException(
                    status_code=409,
                    detail="Accepted Work Order Vendor target is no longer active.",
                )
            target_vendor_id = target_vendor.id
            vendor_mapping_fingerprint = vendor_mapping.source_fingerprint
        elif row.resolution_target_vendor_id is not None:
            raise HTTPException(
                status_code=409,
                detail="Accepted Work Order Vendor snapshot is inconsistent with source evidence.",
            )

        relationship_links.append(
            {
                "source_work_order_id": row.source_id,
                "source_property_id": source_property_id,
                "target_property_id": target_property.id,
                "property_mapping_fingerprint": property_mapping.source_fingerprint,
                "source_unit_id": source_unit_id or None,
                "target_unit_id": target_unit_id,
                "unit_mapping_fingerprint": unit_mapping_fingerprint,
                "source_vendor_id": source_vendor_id or None,
                "target_vendor_id": target_vendor_id,
                "vendor_mapping_fingerprint": vendor_mapping_fingerprint,
            }
        )
        previews.append(
            {
                "source_id": row.source_id,
                "source_evidence": {
                    "source_property_id": source_property_id,
                    "source_unit_id": source_unit_id or None,
                    "source_vendor_id": source_vendor_id or None,
                    "assigned_users": data.get("assigned_users"),
                    "status": data.get("status"),
                    "job_description": data.get("job_description"),
                    "canceled_on": data.get("canceled_on"),
                    "completed_on": data.get("completed_on"),
                    "permission_to_enter": data.get("permission_to_enter"),
                    "priority": data.get("priority"),
                    "scheduled_start": data.get("scheduled_start"),
                    "scheduled_end": data.get("scheduled_end"),
                    "vendor_trade": data.get("vendor_trade"),
                },
                "resolved_targets": {
                    "property_id": target_property.id,
                    "unit_id": target_unit_id,
                    "vendor_id": target_vendor_id,
                },
                "warnings": [
                    (
                        "Dry run is review-only: requester/tenant/occupancy identity, "
                        "staff assignment semantics, vendor contract, workflow-state "
                        "translation, completion/cancellation meaning and accounting "
                        "effects are not inferred."
                    )
                ],
            }
        )

    if not previews:
        raise HTTPException(
            status_code=409,
            detail="Work Orders dry run requires at least one accepted staged row.",
        )

    canonical = {
        "staged_review_fingerprint": _staged_review_fingerprint(upload, rows),
        "relationship_links": sorted(
            relationship_links,
            key=lambda item: str(item["source_work_order_id"]),
        ),
    }
    fingerprint = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    counts = {
        "total": len(previews),
        "importable": len(previews),
        "invalid": 0,
        "warning_count": len(previews),
        "skipped": skipped,
    }
    return previews, fingerprint, counts


def _staged_charge_dry_run_state(
    db: Session,
    *,
    run: PlatformMigrationRun,
    upload: PlatformMigrationUpload,
) -> tuple[list[dict[str, object]], str, dict[str, int]]:
    if upload.detected_resource != "CHARGES":
        raise HTTPException(
            status_code=409,
            detail="Staged upload must be CHARGES before Charges dry run.",
        )
    rows = (
        db.query(PlatformMigrationStagedRow)
        .filter(
            PlatformMigrationStagedRow.upload_id == upload.id,
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.organization_id == run.organization_id,
            PlatformMigrationStagedRow.provider == "APPFOLIO",
            PlatformMigrationStagedRow.resource == "CHARGES",
        )
        .order_by(
            PlatformMigrationStagedRow.row_number.asc(),
            PlatformMigrationStagedRow.id.asc(),
        )
        .all()
    )
    if not rows:
        raise HTTPException(status_code=409, detail="Staged upload has no Charge rows.")

    blocking = [
        row
        for row in rows
        if row.errors
        or row.disposition == "INVALID"
        or (
            row.disposition == "REVIEW"
            and row.resolution_action not in {"ACCEPT_RELATIONSHIP", "SKIP"}
        )
    ]
    if blocking:
        raise HTTPException(
            status_code=409,
            detail="Charges dry run is blocked by invalid or unresolved staged rows.",
        )

    previews: list[dict[str, object]] = []
    relationship_links: list[dict[str, object]] = []
    skipped = 0
    for row in rows:
        if row.resolution_action == "SKIP":
            skipped += 1
            continue
        if row.resolution_action != "ACCEPT_RELATIONSHIP" or not row.source_id:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Every retained Charge row must have stable Charge ID identity "
                    "and explicit ACCEPT_RELATIONSHIP review."
                ),
            )

        data = dict(row.normalized_data or {})
        source_gl_account_id = str(data.get("source_gl_account_id") or "").strip()
        gl_mapping = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "APPFOLIO",
                PlatformMigrationItem.resource == "GL_ACCOUNTS",
                PlatformMigrationItem.source_id == source_gl_account_id,
            )
            .first()
        )
        if (
            gl_mapping is None
            or gl_mapping.target_entity != "GL_ACCOUNT"
            or row.resolution_target_gl_account_id != gl_mapping.target_id
        ):
            raise HTTPException(
                status_code=409,
                detail="Accepted Charge GL Account relationship is stale or inconsistent.",
            )
        target_gl = (
            db.query(GLAccount)
            .filter(
                GLAccount.id == gl_mapping.target_id,
                GLAccount.organization_id == run.organization_id,
                GLAccount.is_active.is_(True),
                GLAccount.deleted_at.is_(None),
            )
            .first()
        )
        if target_gl is None:
            raise HTTPException(
                status_code=409,
                detail="Accepted Charge GL Account target is no longer active.",
            )

        relationship_links.append(
            {
                "source_charge_id": row.source_id,
                "source_gl_account_id": source_gl_account_id,
                "target_gl_account_id": target_gl.id,
                "gl_mapping_fingerprint": gl_mapping.source_fingerprint,
            }
        )
        previews.append(
            {
                "source_id": row.source_id,
                "source_evidence": {
                    "amount_due": data.get("amount_due"),
                    "charged_on": data.get("charged_on"),
                    "description": data.get("description"),
                    "source_gl_account_id": source_gl_account_id,
                    "source_occupancy_id": data.get("source_occupancy_id"),
                },
                "resolved_targets": {
                    "gl_account_id": target_gl.id,
                },
                "warnings": [
                    (
                        "Dry run is review-only: Occupancy target identity, tenant "
                        "liability, original amount, amount paid, paid/unpaid state, "
                        "rent classification, payment application, GL posting and "
                        "historical reconciliation are not inferred."
                    )
                ],
            }
        )

    if not previews:
        raise HTTPException(
            status_code=409,
            detail="Charges dry run requires at least one accepted staged row.",
        )

    canonical = {
        "staged_review_fingerprint": _staged_review_fingerprint(upload, rows),
        "relationship_links": sorted(
            relationship_links,
            key=lambda item: str(item["source_charge_id"]),
        ),
    }
    fingerprint = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    counts = {
        "total": len(previews),
        "importable": len(previews),
        "invalid": 0,
        "warning_count": len(previews),
        "skipped": skipped,
    }
    return previews, fingerprint, counts


def _staged_general_ledger_dry_run_state(
    db: Session,
    *,
    run: PlatformMigrationRun,
    upload: PlatformMigrationUpload,
) -> tuple[list[dict[str, object]], str, dict[str, int]]:
    if upload.detected_resource != "GENERAL_LEDGER":
        raise HTTPException(
            status_code=409,
            detail="Staged upload must be GENERAL_LEDGER before ledger dry run.",
        )
    rows = (
        db.query(PlatformMigrationStagedRow)
        .filter(
            PlatformMigrationStagedRow.upload_id == upload.id,
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.organization_id == run.organization_id,
            PlatformMigrationStagedRow.provider == "APPFOLIO",
            PlatformMigrationStagedRow.resource == "GENERAL_LEDGER",
        )
        .order_by(
            PlatformMigrationStagedRow.row_number.asc(),
            PlatformMigrationStagedRow.id.asc(),
        )
        .all()
    )
    if not rows:
        raise HTTPException(status_code=409, detail="Staged upload has no General Ledger rows.")

    blocking = [
        row
        for row in rows
        if row.errors
        or row.disposition == "INVALID"
        or (
            row.disposition == "REVIEW"
            and row.resolution_action not in {"ACCEPT_RELATIONSHIP", "SKIP"}
        )
    ]
    if blocking:
        raise HTTPException(
            status_code=409,
            detail=(
                "General Ledger dry run is blocked by invalid or unresolved staged rows."
            ),
        )

    previews: list[dict[str, object]] = []
    relationship_links: list[dict[str, object]] = []
    skipped = 0
    for row in rows:
        if row.resolution_action == "SKIP":
            skipped += 1
            continue
        if row.resolution_action != "ACCEPT_RELATIONSHIP" or not row.source_id:
            raise HTTPException(
                status_code=409,
                detail="Every retained General Ledger row must have stable LineItemId identity and explicit ACCEPT_RELATIONSHIP review.",
            )

        data = dict(row.normalized_data or {})
        source_gl = str(data.get("source_gl_account_id") or "").strip()
        source_property = str(data.get("source_property_id") or "").strip()
        source_unit = str(data.get("source_unit_id") or "").strip()
        gl_mapping = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "APPFOLIO",
                PlatformMigrationItem.resource == "GL_ACCOUNTS",
                PlatformMigrationItem.source_id == source_gl,
            )
            .first()
        )
        if (
            gl_mapping is None
            or gl_mapping.target_entity != "GL_ACCOUNT"
            or row.resolution_target_gl_account_id != gl_mapping.target_id
        ):
            raise HTTPException(
                status_code=409,
                detail="Accepted General Ledger GL Account relationship is stale or inconsistent.",
            )
        target_gl = (
            db.query(GLAccount)
            .filter(
                GLAccount.id == gl_mapping.target_id,
                GLAccount.organization_id == run.organization_id,
                GLAccount.is_active.is_(True),
                GLAccount.deleted_at.is_(None),
            )
            .first()
        )
        if target_gl is None:
            raise HTTPException(
                status_code=409,
                detail="Accepted General Ledger GL Account target is no longer active.",
            )

        target_property_id = None
        property_mapping_fingerprint = None
        if source_property:
            mapping = (
                db.query(PlatformMigrationItem)
                .filter(
                    PlatformMigrationItem.run_id == run.id,
                    PlatformMigrationItem.organization_id == run.organization_id,
                    PlatformMigrationItem.provider == "APPFOLIO",
                    PlatformMigrationItem.resource == "PROPERTIES",
                    PlatformMigrationItem.source_id == source_property,
                )
                .first()
            )
            if (
                mapping is None
                or mapping.target_entity != "PROPERTY"
                or row.resolution_target_id != mapping.target_id
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Accepted General Ledger Property relationship is stale or inconsistent.",
                )
            target_property = (
                db.query(Property)
                .filter(
                    Property.id == mapping.target_id,
                    Property.organization_id == run.organization_id,
                    Property.is_active.is_(True),
                    Property.deleted_at.is_(None),
                )
                .first()
            )
            if target_property is None:
                raise HTTPException(
                    status_code=409,
                    detail="Accepted General Ledger Property target is no longer active.",
                )
            target_property_id = target_property.id
            property_mapping_fingerprint = mapping.source_fingerprint

        target_unit_id = None
        unit_mapping_fingerprint = None
        if source_unit:
            mapping = (
                db.query(PlatformMigrationItem)
                .filter(
                    PlatformMigrationItem.run_id == run.id,
                    PlatformMigrationItem.organization_id == run.organization_id,
                    PlatformMigrationItem.provider == "APPFOLIO",
                    PlatformMigrationItem.resource == "UNITS",
                    PlatformMigrationItem.source_id == source_unit,
                )
                .first()
            )
            if (
                mapping is None
                or mapping.target_entity != "UNIT"
                or row.resolution_target_unit_id != mapping.target_id
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Accepted General Ledger Unit relationship is stale or inconsistent.",
                )
            target_unit = (
                db.query(Unit)
                .join(Property, Property.id == Unit.property_id)
                .filter(
                    Unit.id == mapping.target_id,
                    Unit.is_active.is_(True),
                    Unit.deleted_at.is_(None),
                    Property.organization_id == run.organization_id,
                    Property.is_active.is_(True),
                    Property.deleted_at.is_(None),
                )
                .first()
            )
            if target_unit is None:
                raise HTTPException(
                    status_code=409,
                    detail="Accepted General Ledger Unit target is no longer active.",
                )
            if target_property_id is not None and target_unit.property_id != target_property_id:
                raise HTTPException(
                    status_code=409,
                    detail="Accepted General Ledger Unit no longer belongs to the accepted Property.",
                )
            target_unit_id = target_unit.id
            unit_mapping_fingerprint = mapping.source_fingerprint

        relationship_links.append(
            {
                "source_line_item_id": row.source_id,
                "source_gl_account_id": source_gl,
                "target_gl_account_id": target_gl.id,
                "gl_mapping_fingerprint": gl_mapping.source_fingerprint,
                "source_property_id": source_property or None,
                "target_property_id": target_property_id,
                "property_mapping_fingerprint": property_mapping_fingerprint,
                "source_unit_id": source_unit or None,
                "target_unit_id": target_unit_id,
                "unit_mapping_fingerprint": unit_mapping_fingerprint,
            }
        )
        previews.append(
            {
                "source_id": row.source_id,
                "source_evidence": {
                    "transaction_id": data.get("transaction_id"),
                    "posted_date": data.get("posted_date"),
                    "debit": data.get("debit"),
                    "credit": data.get("credit"),
                    "description": data.get("description"),
                    "reference": data.get("reference"),
                    "remarks": data.get("remarks"),
                    "transaction_type": data.get("transaction_type"),
                    "source_gl_account_id": source_gl,
                    "source_property_id": source_property or None,
                    "source_unit_id": source_unit or None,
                },
                "resolved_targets": {
                    "gl_account_id": target_gl.id,
                    "property_id": target_property_id,
                    "unit_id": target_unit_id,
                },
                "warnings": [
                    "Dry run is review-only: no balancing, posting, netting, target transaction grouping, payer/payee inference or accounting mutation occurs."
                ],
            }
        )

    if not previews:
        raise HTTPException(
            status_code=409,
            detail="General Ledger dry run requires at least one accepted staged row.",
        )

    canonical = {
        "staged_review_fingerprint": _staged_review_fingerprint(upload, rows),
        "relationship_links": sorted(
            relationship_links,
            key=lambda item: str(item["source_line_item_id"]),
        ),
    }
    fingerprint = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    counts = {
        "total": len(previews),
        "importable": len(previews),
        "invalid": 0,
        "warning_count": len(previews),
        "skipped": skipped,
    }
    return previews, fingerprint, counts


def _general_ledger_commit_readiness_state(
    db: Session,
    *,
    run: PlatformMigrationRun,
    upload: PlatformMigrationUpload,
) -> tuple[list[dict[str, object]], str, str]:
    previews, dry_run_fingerprint, _counts = _staged_general_ledger_dry_run_state(
        db, run=run, upload=upload
    )
    if run.last_dry_run_fingerprint != dry_run_fingerprint:
        raise HTTPException(
            status_code=409,
            detail=(
                "General Ledger commit readiness requires the exact latest staged "
                "dry-run fingerprint."
            ),
        )

    grouped: dict[str, list[dict[str, object]]] = {}
    for preview in previews:
        evidence = dict(preview["source_evidence"])
        transaction_id = str(evidence.get("transaction_id") or "").strip()
        if not transaction_id:
            raise HTTPException(
                status_code=409,
                detail=(
                    "General Ledger rows without supplied TransactionId cannot be "
                    "commit-ready."
                ),
            )
        grouped.setdefault(transaction_id, []).append(preview)

    groups: list[dict[str, object]] = []
    canonical_groups: list[dict[str, object]] = []
    for transaction_id in sorted(grouped):
        debit_total = Decimal("0")
        credit_total = Decimal("0")
        lines: list[dict[str, object]] = []
        canonical_lines: list[dict[str, object]] = []
        for preview in sorted(grouped[transaction_id], key=lambda row: str(row["source_id"])):
            evidence = dict(preview["source_evidence"])
            try:
                debit = Decimal(str(evidence.get("debit") or "0"))
                credit = Decimal(str(evidence.get("credit") or "0"))
            except (InvalidOperation, ValueError) as exc:
                raise HTTPException(
                    status_code=409,
                    detail="General Ledger readiness encountered non-numeric debit/credit evidence.",
                ) from exc
            debit_total += debit
            credit_total += credit
            line = {
                "source_id": str(preview["source_id"]),
                "transaction_id": transaction_id,
                "posted_date": str(evidence.get("posted_date") or ""),
                "debit": str(evidence.get("debit") or "0"),
                "credit": str(evidence.get("credit") or "0"),
                "resolved_targets": dict(preview["resolved_targets"]),
            }
            lines.append(line)
            canonical_lines.append(
                {
                    **line,
                    "description": evidence.get("description"),
                    "reference": evidence.get("reference"),
                    "remarks": evidence.get("remarks"),
                    "transaction_type": evidence.get("transaction_type"),
                }
            )

        balanced = debit_total == credit_total
        if not balanced:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"General Ledger TransactionId {transaction_id!r} is not balanced "
                    "from supplied source debit/credit evidence."
                ),
            )
        groups.append(
            {
                "transaction_id": transaction_id,
                "line_count": len(lines),
                "debit_total": format(debit_total, "f"),
                "credit_total": format(credit_total, "f"),
                "balanced": True,
                "lines": lines,
            }
        )
        canonical_groups.append(
            {
                "transaction_id": transaction_id,
                "debit_total": format(debit_total, "f"),
                "credit_total": format(credit_total, "f"),
                "lines": canonical_lines,
            }
        )

    if not groups:
        raise HTTPException(
            status_code=409,
            detail="General Ledger commit readiness requires at least one balanced transaction group.",
        )

    canonical = {
        "dry_run_fingerprint": dry_run_fingerprint,
        "groups": canonical_groups,
    }
    readiness_fingerprint = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return groups, dry_run_fingerprint, readiness_fingerprint


def _staged_vendor_state(
    db: Session,
    *,
    run: PlatformMigrationRun,
    upload: PlatformMigrationUpload,
) -> tuple[list[dict[str, object]], dict[str, int], set[str], str]:
    if upload.detected_resource != "VENDORS":
        raise HTTPException(
            status_code=409,
            detail="Staged upload must be resolved to VENDORS before Vendor dry run.",
        )
    rows = (
        db.query(PlatformMigrationStagedRow)
        .filter(
            PlatformMigrationStagedRow.upload_id == upload.id,
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.organization_id == run.organization_id,
            PlatformMigrationStagedRow.provider == "APPFOLIO",
            PlatformMigrationStagedRow.resource == "VENDORS",
        )
        .order_by(
            PlatformMigrationStagedRow.row_number.asc(),
            PlatformMigrationStagedRow.id.asc(),
        )
        .all()
    )
    if not rows:
        raise HTTPException(status_code=409, detail="Staged upload has no Vendor rows.")

    blocking: list[PlatformMigrationStagedRow] = []
    for row in rows:
        if row.errors or row.disposition == "INVALID":
            blocking.append(row)
        elif row.disposition == "POSSIBLE_MATCH" and row.resolution_action not in {
            "MATCH_EXISTING", "CREATE_NEW", "SKIP",
        }:
            blocking.append(row)
        elif row.disposition == "REVIEW" and row.resolution_action != "SKIP":
            blocking.append(row)
        elif row.disposition == "ALREADY_MAPPED" and row.resolution_action is not None:
            blocking.append(row)
        elif row.resolution_action == "CREATE_NEW" and row.disposition != "POSSIBLE_MATCH":
            blocking.append(row)
    if blocking:
        counts: dict[str, int] = {}
        for row in blocking:
            counts[row.disposition] = counts.get(row.disposition, 0) + 1
        detail = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
        raise HTTPException(
            status_code=409,
            detail=(
                "Staged Vendor dry run is blocked by unresolved rows: "
                f"{detail}. Resolve staged Vendor validation/match decisions before continuing."
            ),
        )

    records: list[dict[str, object]] = []
    resolved_existing: dict[str, int] = {}
    force_create_new: set[str] = set()
    for row in rows:
        if row.resolution_action == "SKIP":
            continue
        data = dict(row.normalized_data or {})
        source_id = row.source_id or data.get("source_id")
        company_name = data.get("company_name")
        if not source_id or not company_name:
            raise HTTPException(
                status_code=409,
                detail="Staged Vendor row lacks durable Vendor source identity or company name.",
            )
        source_key = str(source_id).strip()
        if row.resolution_action == "MATCH_EXISTING":
            if row.resolution_target_vendor_id is None:
                raise HTTPException(
                    status_code=409,
                    detail="Resolved staged Vendor match is missing its Vendor target.",
                )
            target = (
                db.query(Vendor)
                .filter(
                    Vendor.id == row.resolution_target_vendor_id,
                    Vendor.organization_id == run.organization_id,
                    Vendor.is_active.is_(True),
                    Vendor.deleted_at.is_(None),
                )
                .first()
            )
            if target is None:
                raise HTTPException(
                    status_code=409,
                    detail="Resolved staged Vendor target is no longer active in this organization.",
                )
            resolved_existing[source_key] = target.id
        elif row.resolution_action == "CREATE_NEW":
            force_create_new.add(source_key)

        records.append({
            "Vendor ID": source_key,
            "Company Name": company_name,
            "Email": data.get("email"),
            "Address": data.get("address"),
            "Phone Numbers": data.get("phone_numbers"),
            "Send 1099?": data.get("send_1099"),
            "Liability Insurance Expiration": data.get("liability_insurance_expiration"),
            "Workers Comp Expiration": data.get("workers_comp_expiration"),
            "EPA Certification Expiration": data.get("epa_certification_expiration"),
            "State License Expiration": data.get("state_license_expiration"),
            "Contract Expiration": data.get("contract_expiration"),
        })

    if not records:
        raise HTTPException(
            status_code=409,
            detail="No staged Vendor rows remain after explicit skip decisions.",
        )
    return (
        records,
        resolved_existing,
        force_create_new,
        _staged_review_fingerprint(upload, rows),
    )


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/rows/{staged_row_id}/resolution",
    response_model=AppFolioMigrationStagedRowOut,
)
def resolve_staged_appfolio_property(
    run_id: int,
    upload_id: int,
    staged_row_id: int,
    payload: AppFolioStagedRowResolutionIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    if upload.detected_resource != "PROPERTIES":
        raise HTTPException(status_code=409, detail="Only staged PROPERTIES rows can be resolved here.")
    row = _staged_row(
        db,
        run=run,
        upload=upload,
        staged_row_id=staged_row_id,
    )
    if row.resource != "PROPERTIES" or row.errors:
        raise HTTPException(status_code=409, detail="Invalid staged property rows cannot be resolved.")
    if row.disposition == "ALREADY_MAPPED":
        raise HTTPException(
            status_code=409,
            detail="Already-mapped staged rows are controlled by their durable source mapping.",
        )
    if row.disposition == "REVIEW" and payload.action != "SKIP":
        raise HTTPException(
            status_code=409,
            detail="This REVIEW row may only be skipped in the current property migration batch.",
        )
    if payload.action == "CREATE_NEW" and row.disposition != "POSSIBLE_MATCH":
        raise HTTPException(
            status_code=409,
            detail="CREATE_NEW resolution is only valid for a reviewed POSSIBLE_MATCH row.",
        )

    target_id = payload.target_property_id
    if payload.action == "MATCH_EXISTING":
        if row.disposition not in {"POSSIBLE_MATCH", "NEW"}:
            raise HTTPException(status_code=409, detail="This staged row cannot be matched to an existing property.")
        target = (
            db.query(Property)
            .filter(
                Property.id == target_id,
                Property.organization_id == run.organization_id,
                Property.is_active.is_(True),
                Property.deleted_at.is_(None),
            )
            .first()
        )
        if target is None:
            raise HTTPException(status_code=404, detail="Existing target property not found.")
    else:
        target_id = None

    if (
        row.resolution_action == payload.action
        and row.resolution_target_id == target_id
    ):
        return row

    row.resolution_action = payload.action
    row.resolution_target_id = target_id
    row.resolved_by_platform_user_id = current_user.id
    row.resolved_at = datetime.utcnow()
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    run.status = "STAGED"
    append_audit_log(
        db,
        platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_staged_row",
        entity_id=row.id,
        action="appfolio_property_resolution_changed",
        new_value={
            "upload_id": upload.id,
            "source_id": row.source_id,
            "resolution_action": row.resolution_action,
            "resolution_target_id": row.resolution_target_id,
            "raw_source_stored": False,
            "target_mutation": False,
        },
    )
    db.commit()
    db.refresh(row)
    return row


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/rows/{staged_row_id}/unit-resolution",
    response_model=AppFolioMigrationStagedRowOut,
)
def resolve_staged_appfolio_unit(
    run_id: int,
    upload_id: int,
    staged_row_id: int,
    payload: AppFolioStagedUnitResolutionIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    if upload.detected_resource != "UNITS":
        raise HTTPException(status_code=409, detail="Only staged UNITS rows can be resolved here.")
    row = _staged_row(
        db,
        run=run,
        upload=upload,
        staged_row_id=staged_row_id,
    )
    if row.resource != "UNITS" or row.errors or row.disposition == "INVALID":
        raise HTTPException(status_code=409, detail="Invalid staged Unit rows cannot be resolved.")
    if row.disposition == "ALREADY_MAPPED":
        raise HTTPException(
            status_code=409,
            detail="Already-mapped staged Unit rows are controlled by their durable source mapping.",
        )
    if row.disposition == "REVIEW" and payload.action != "SKIP":
        raise HTTPException(
            status_code=409,
            detail="This REVIEW Unit row may only be skipped because durable Unit/Property identity is unresolved.",
        )
    if payload.action == "CREATE_NEW" and row.disposition != "POSSIBLE_MATCH":
        raise HTTPException(
            status_code=409,
            detail="CREATE_NEW is only valid for a reviewed same-property Unit POSSIBLE_MATCH row.",
        )
    if payload.action == "MATCH_EXISTING" and row.disposition not in {"POSSIBLE_MATCH", "NEW"}:
        raise HTTPException(
            status_code=409,
            detail="This staged Unit row cannot be matched to an existing Unit.",
        )

    target_unit_id = payload.target_unit_id
    if payload.action == "MATCH_EXISTING":
        data = dict(row.normalized_data or {})
        source_property_id = data.get("source_property_id")
        if not source_property_id:
            raise HTTPException(
                status_code=409,
                detail="Unit match requires a durable source Property ID.",
            )
        property_mapping = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "APPFOLIO",
                PlatformMigrationItem.resource == "PROPERTIES",
                PlatformMigrationItem.source_id == str(source_property_id).strip(),
            )
            .first()
        )
        if property_mapping is None or property_mapping.target_entity != "PROPERTY":
            raise HTTPException(
                status_code=409,
                detail="Unit match requires a valid durable Property mapping.",
            )
        target = (
            db.query(Unit)
            .join(Property, Property.id == Unit.property_id)
            .filter(
                Unit.id == target_unit_id,
                Unit.property_id == property_mapping.target_id,
                Unit.is_active.is_(True),
                Unit.deleted_at.is_(None),
                Property.organization_id == run.organization_id,
                Property.is_active.is_(True),
                Property.deleted_at.is_(None),
            )
            .first()
        )
        if target is None:
            raise HTTPException(
                status_code=404,
                detail="Existing target Unit not found under the mapped Property.",
            )
    else:
        target_unit_id = None

    if (
        row.resolution_action == payload.action
        and row.resolution_target_unit_id == target_unit_id
    ):
        return row

    row.resolution_action = payload.action
    row.resolution_target_unit_id = target_unit_id
    row.resolution_target_id = None
    row.resolved_by_platform_user_id = current_user.id
    row.resolved_at = datetime.utcnow()
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    run.status = "STAGED"
    append_audit_log(
        db,
        platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_staged_row",
        entity_id=row.id,
        action="appfolio_unit_resolution_changed",
        new_value={
            "upload_id": upload.id,
            "source_id": row.source_id,
            "resolution_action": row.resolution_action,
            "resolution_target_unit_id": row.resolution_target_unit_id,
            "raw_source_stored": False,
            "target_overwrite": False,
        },
    )
    db.commit()
    db.refresh(row)
    return row


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/rows/{staged_row_id}/owner-resolution",
    response_model=AppFolioMigrationStagedRowOut,
)
def resolve_staged_appfolio_owner(
    run_id: int,
    upload_id: int,
    staged_row_id: int,
    payload: AppFolioStagedOwnerResolutionIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    if upload.detected_resource != "OWNERS":
        raise HTTPException(status_code=409, detail="Only staged OWNERS rows can be resolved here.")
    row = _staged_row(db, run=run, upload=upload, staged_row_id=staged_row_id)
    if row.resource != "OWNERS" or row.errors or row.disposition == "INVALID":
        raise HTTPException(status_code=409, detail="Invalid staged Owner rows cannot be resolved.")
    if row.disposition == "ALREADY_MAPPED":
        raise HTTPException(
            status_code=409,
            detail="Already-mapped staged Owner rows are controlled by their durable source mapping.",
        )
    if not row.source_id and payload.action != "SKIP":
        raise HTTPException(
            status_code=409,
            detail="Owner rows without a durable source Owner ID may only be skipped.",
        )
    if row.disposition == "REVIEW" and payload.action != "SKIP":
        raise HTTPException(
            status_code=409,
            detail="This REVIEW Owner row may only be skipped until durable identity/contact relationships are resolved.",
        )
    if payload.action == "CREATE_NEW" and row.disposition != "POSSIBLE_MATCH":
        raise HTTPException(
            status_code=409,
            detail="CREATE_NEW is only valid for a reviewed Owner POSSIBLE_MATCH row.",
        )
    if payload.action == "MATCH_EXISTING" and row.disposition not in {"POSSIBLE_MATCH", "NEW"}:
        raise HTTPException(status_code=409, detail="This staged Owner row cannot be matched to an existing Owner.")

    target_owner_user_id = payload.target_owner_user_id
    if payload.action == "MATCH_EXISTING":
        target = (
            db.query(User)
            .filter(
                User.id == target_owner_user_id,
                User.organization_id == run.organization_id,
                User.role == UserRole.OWNER,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
            .first()
        )
        if target is None:
            raise HTTPException(status_code=404, detail="Existing target Owner not found in this organization.")
    else:
        target_owner_user_id = None

    if (
        row.resolution_action == payload.action
        and row.resolution_target_owner_user_id == target_owner_user_id
    ):
        return row

    row.resolution_action = payload.action
    row.resolution_target_owner_user_id = target_owner_user_id
    row.resolution_target_id = None
    row.resolution_target_unit_id = None
    row.resolution_target_vendor_id = None
    row.resolution_target_tenant_user_id = None
    row.resolution_target_gl_account_id = None
    row.resolved_by_platform_user_id = current_user.id
    row.resolved_at = datetime.utcnow()
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    run.status = "STAGED"
    append_audit_log(
        db,
        platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_staged_row",
        entity_id=row.id,
        action="appfolio_owner_resolution_changed",
        new_value={
            "upload_id": upload.id,
            "source_id": row.source_id,
            "resolution_action": row.resolution_action,
            "resolution_target_owner_user_id": row.resolution_target_owner_user_id,
            "raw_source_stored": False,
            "target_overwrite": False,
        },
    )
    db.commit()
    db.refresh(row)
    return row


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/rows/{staged_row_id}/tenant-resolution",
    response_model=AppFolioMigrationStagedRowOut,
)
def resolve_staged_appfolio_tenant(
    run_id: int,
    upload_id: int,
    staged_row_id: int,
    payload: AppFolioStagedTenantResolutionIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    if upload.detected_resource != "TENANTS":
        raise HTTPException(status_code=409, detail="Only staged TENANTS rows can be resolved here.")
    row = _staged_row(db, run=run, upload=upload, staged_row_id=staged_row_id)
    if row.resource != "TENANTS" or row.errors or row.disposition == "INVALID":
        raise HTTPException(status_code=409, detail="Invalid staged Tenant rows cannot be resolved.")
    if row.disposition == "ALREADY_MAPPED":
        raise HTTPException(
            status_code=409,
            detail="Already-mapped staged Tenant rows are controlled by their durable source mapping.",
        )
    if not row.source_id and payload.action != "SKIP":
        raise HTTPException(
            status_code=409,
            detail="Tenant rows without a durable source Tenant ID may only be skipped.",
        )
    if row.disposition == "REVIEW" and payload.action != "SKIP":
        raise HTTPException(
            status_code=409,
            detail="This REVIEW Tenant row may only be skipped until durable Tenant/Unit/Property identity is resolved.",
        )
    if payload.action == "CREATE_NEW" and row.disposition != "POSSIBLE_MATCH":
        raise HTTPException(
            status_code=409,
            detail="CREATE_NEW is only valid for a reviewed Tenant POSSIBLE_MATCH row.",
        )
    if payload.action == "MATCH_EXISTING" and row.disposition not in {"POSSIBLE_MATCH", "NEW"}:
        raise HTTPException(
            status_code=409,
            detail="This staged Tenant row cannot be matched to an existing Tenant.",
        )

    target_tenant_user_id = payload.target_tenant_user_id
    if payload.action == "MATCH_EXISTING":
        target = (
            db.query(User)
            .filter(
                User.id == target_tenant_user_id,
                User.organization_id == run.organization_id,
                User.role == UserRole.TENANT,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
            .first()
        )
        if target is None:
            raise HTTPException(
                status_code=404,
                detail="Existing target Tenant not found in this organization.",
            )
    else:
        target_tenant_user_id = None

    if (
        row.resolution_action == payload.action
        and row.resolution_target_tenant_user_id == target_tenant_user_id
    ):
        return row

    row.resolution_action = payload.action
    row.resolution_target_tenant_user_id = target_tenant_user_id
    row.resolution_target_id = None
    row.resolution_target_unit_id = None
    row.resolution_target_owner_user_id = None
    row.resolution_target_vendor_id = None
    row.resolved_by_platform_user_id = current_user.id
    row.resolved_at = datetime.utcnow()
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    run.status = "STAGED"
    append_audit_log(
        db,
        platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_staged_row",
        entity_id=row.id,
        action="appfolio_tenant_resolution_changed",
        new_value={
            "upload_id": upload.id,
            "source_id": row.source_id,
            "resolution_action": row.resolution_action,
            "resolution_target_tenant_user_id": row.resolution_target_tenant_user_id,
            "raw_source_stored": False,
            "target_overwrite": False,
            "tenant_user_creation": False,
            "lease_or_occupancy_mutation": False,
        },
    )
    db.commit()
    db.refresh(row)
    return row


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/rows/{staged_row_id}/lease-occupancy-resolution",
    response_model=AppFolioMigrationStagedRowOut,
)
def resolve_staged_appfolio_lease_occupancy(
    run_id: int,
    upload_id: int,
    staged_row_id: int,
    payload: AppFolioStagedLeaseOccupancyResolutionIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    if upload.detected_resource != "LEASE_OCCUPANCY":
        raise HTTPException(
            status_code=409,
            detail="Only staged LEASE_OCCUPANCY rows can be resolved here.",
        )
    row = _staged_row(db, run=run, upload=upload, staged_row_id=staged_row_id)
    if row.resource != "LEASE_OCCUPANCY" or row.errors or row.disposition == "INVALID":
        raise HTTPException(
            status_code=409,
            detail="Invalid staged Lease/occupancy rows cannot be resolved.",
        )

    target_property_id = None
    target_unit_id = None
    target_tenant_user_id = None

    if payload.action == "ACCEPT_RELATIONSHIP":
        data = dict(row.normalized_data or {})
        tenant_source = str(data.get("source_tenant_id") or "").strip()
        property_source = str(data.get("source_property_id") or "").strip()
        unit_source = str(data.get("source_unit_id") or "").strip()
        if not tenant_source or not property_source or not unit_source:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Lease/occupancy relationship cannot be accepted until durable "
                    "Tenant, Property and Unit source IDs are all present."
                ),
            )

        tenant_mapping = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "APPFOLIO",
                PlatformMigrationItem.resource == "TENANTS",
                PlatformMigrationItem.source_id == tenant_source,
            )
            .first()
        )
        property_mapping = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "APPFOLIO",
                PlatformMigrationItem.resource == "PROPERTIES",
                PlatformMigrationItem.source_id == property_source,
            )
            .first()
        )
        unit_mapping = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "APPFOLIO",
                PlatformMigrationItem.resource == "UNITS",
                PlatformMigrationItem.source_id == unit_source,
            )
            .first()
        )
        if (
            tenant_mapping is None
            or tenant_mapping.target_entity != "TENANT_USER"
            or property_mapping is None
            or property_mapping.target_entity != "PROPERTY"
            or unit_mapping is None
            or unit_mapping.target_entity != "UNIT"
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Lease/occupancy relationship cannot be accepted until all "
                    "durable source mappings resolve with the expected target types."
                ),
            )

        target_tenant = (
            db.query(User)
            .filter(
                User.id == tenant_mapping.target_id,
                User.organization_id == run.organization_id,
                User.role == UserRole.TENANT,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
            .first()
        )
        target_property = (
            db.query(Property)
            .filter(
                Property.id == property_mapping.target_id,
                Property.organization_id == run.organization_id,
                Property.is_active.is_(True),
                Property.deleted_at.is_(None),
            )
            .first()
        )
        target_unit = (
            db.query(Unit)
            .join(Property, Property.id == Unit.property_id)
            .filter(
                Unit.id == unit_mapping.target_id,
                Unit.is_active.is_(True),
                Unit.deleted_at.is_(None),
                Property.organization_id == run.organization_id,
                Property.is_active.is_(True),
                Property.deleted_at.is_(None),
            )
            .first()
        )
        if target_tenant is None or target_property is None or target_unit is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Lease/occupancy relationship targets are no longer active in "
                    "the migration organization."
                ),
            )
        if target_unit.property_id != target_property.id:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Mapped Lease/occupancy Unit and Property no longer resolve "
                    "to the same target Property."
                ),
            )

        target_property_id = target_property.id
        target_unit_id = target_unit.id
        target_tenant_user_id = target_tenant.id

    if (
        row.resolution_action == payload.action
        and row.resolution_target_id == target_property_id
        and row.resolution_target_unit_id == target_unit_id
        and row.resolution_target_tenant_user_id == target_tenant_user_id
    ):
        return row

    row.resolution_action = payload.action
    row.resolution_target_id = target_property_id
    row.resolution_target_unit_id = target_unit_id
    row.resolution_target_tenant_user_id = target_tenant_user_id
    row.resolution_target_owner_user_id = None
    row.resolution_target_vendor_id = None
    row.resolution_target_gl_account_id = None
    row.resolved_by_platform_user_id = current_user.id
    row.resolved_at = datetime.utcnow()
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    run.status = "STAGED"
    append_audit_log(
        db,
        platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_staged_row",
        entity_id=row.id,
        action="appfolio_lease_occupancy_resolution_changed",
        new_value={
            "upload_id": upload.id,
            "source_tenant_id": (row.normalized_data or {}).get("source_tenant_id"),
            "source_property_id": (row.normalized_data or {}).get("source_property_id"),
            "source_unit_id": (row.normalized_data or {}).get("source_unit_id"),
            "resolution_action": row.resolution_action,
            "resolution_target_id": row.resolution_target_id,
            "resolution_target_unit_id": row.resolution_target_unit_id,
            "resolution_target_tenant_user_id": row.resolution_target_tenant_user_id,
            "accepted_for_later_commit": row.resolution_action == "ACCEPT_RELATIONSHIP",
            "customer_lease_mutation": False,
            "accounting_mutation": False,
        },
    )
    db.commit()
    db.refresh(row)
    return row


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/rows/{staged_row_id}/general-ledger-resolution",
    response_model=AppFolioMigrationStagedRowOut,
)
def resolve_staged_appfolio_general_ledger(
    run_id: int,
    upload_id: int,
    staged_row_id: int,
    payload: AppFolioStagedGeneralLedgerResolutionIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    if upload.detected_resource != "GENERAL_LEDGER":
        raise HTTPException(
            status_code=409,
            detail="Only staged GENERAL_LEDGER rows can be resolved here.",
        )
    row = _staged_row(db, run=run, upload=upload, staged_row_id=staged_row_id)
    if row.resource != "GENERAL_LEDGER" or row.errors or row.disposition == "INVALID":
        raise HTTPException(
            status_code=409,
            detail="Invalid staged General Ledger rows cannot be resolved.",
        )
    if not row.source_id and payload.action != "SKIP":
        raise HTTPException(
            status_code=409,
            detail=(
                "General Ledger rows without a durable LineItemId may only be skipped."
            ),
        )

    target_gl_account_id = None
    target_property_id = None
    target_unit_id = None

    if payload.action == "ACCEPT_RELATIONSHIP":
        data = dict(row.normalized_data or {})
        source_gl_account_id = str(data.get("source_gl_account_id") or "").strip()
        source_property_id = str(data.get("source_property_id") or "").strip()
        source_unit_id = str(data.get("source_unit_id") or "").strip()
        if not source_gl_account_id:
            raise HTTPException(
                status_code=409,
                detail="General Ledger relationship requires a source GL Account ID.",
            )

        gl_mapping = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "APPFOLIO",
                PlatformMigrationItem.resource == "GL_ACCOUNTS",
                PlatformMigrationItem.source_id == source_gl_account_id,
            )
            .first()
        )
        if gl_mapping is None or gl_mapping.target_entity != "GL_ACCOUNT":
            raise HTTPException(
                status_code=409,
                detail=(
                    "General Ledger relationship cannot be accepted until the "
                    "source GL Account has a durable GL_ACCOUNT mapping."
                ),
            )
        target_gl = (
            db.query(GLAccount)
            .filter(
                GLAccount.id == gl_mapping.target_id,
                GLAccount.organization_id == run.organization_id,
                GLAccount.is_active.is_(True),
                GLAccount.deleted_at.is_(None),
            )
            .first()
        )
        if target_gl is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Mapped General Ledger GL Account is no longer active in this "
                    "organization."
                ),
            )
        target_gl_account_id = target_gl.id

        target_property = None
        if source_property_id:
            property_mapping = (
                db.query(PlatformMigrationItem)
                .filter(
                    PlatformMigrationItem.run_id == run.id,
                    PlatformMigrationItem.organization_id == run.organization_id,
                    PlatformMigrationItem.provider == "APPFOLIO",
                    PlatformMigrationItem.resource == "PROPERTIES",
                    PlatformMigrationItem.source_id == source_property_id,
                )
                .first()
            )
            if property_mapping is None or property_mapping.target_entity != "PROPERTY":
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Supplied General Ledger PropertyId must have a durable "
                        "PROPERTY mapping before acceptance."
                    ),
                )
            target_property = (
                db.query(Property)
                .filter(
                    Property.id == property_mapping.target_id,
                    Property.organization_id == run.organization_id,
                    Property.is_active.is_(True),
                    Property.deleted_at.is_(None),
                )
                .first()
            )
            if target_property is None:
                raise HTTPException(
                    status_code=409,
                    detail="Mapped General Ledger Property is no longer active.",
                )
            target_property_id = target_property.id

        if source_unit_id:
            unit_mapping = (
                db.query(PlatformMigrationItem)
                .filter(
                    PlatformMigrationItem.run_id == run.id,
                    PlatformMigrationItem.organization_id == run.organization_id,
                    PlatformMigrationItem.provider == "APPFOLIO",
                    PlatformMigrationItem.resource == "UNITS",
                    PlatformMigrationItem.source_id == source_unit_id,
                )
                .first()
            )
            if unit_mapping is None or unit_mapping.target_entity != "UNIT":
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Supplied General Ledger UnitId must have a durable UNIT "
                        "mapping before acceptance."
                    ),
                )
            target_unit = (
                db.query(Unit)
                .join(Property, Property.id == Unit.property_id)
                .filter(
                    Unit.id == unit_mapping.target_id,
                    Unit.is_active.is_(True),
                    Unit.deleted_at.is_(None),
                    Property.organization_id == run.organization_id,
                    Property.is_active.is_(True),
                    Property.deleted_at.is_(None),
                )
                .first()
            )
            if target_unit is None:
                raise HTTPException(
                    status_code=409,
                    detail="Mapped General Ledger Unit is no longer active.",
                )
            if target_property is not None and target_unit.property_id != target_property.id:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Mapped General Ledger Unit and Property no longer resolve "
                        "to the same target Property."
                    ),
                )
            target_unit_id = target_unit.id

    if (
        row.resolution_action == payload.action
        and row.resolution_target_gl_account_id == target_gl_account_id
        and row.resolution_target_id == target_property_id
        and row.resolution_target_unit_id == target_unit_id
    ):
        return row

    row.resolution_action = payload.action
    row.resolution_target_gl_account_id = target_gl_account_id
    row.resolution_target_id = target_property_id
    row.resolution_target_unit_id = target_unit_id
    row.resolution_target_owner_user_id = None
    row.resolution_target_vendor_id = None
    row.resolution_target_tenant_user_id = None
    row.resolved_by_platform_user_id = current_user.id
    row.resolved_at = datetime.utcnow()
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    run.status = "STAGED"
    append_audit_log(
        db,
        platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_staged_row",
        entity_id=row.id,
        action="appfolio_general_ledger_resolution_changed",
        new_value={
            "upload_id": upload.id,
            "source_line_item_id": row.source_id,
            "source_gl_account_id": (row.normalized_data or {}).get("source_gl_account_id"),
            "source_property_id": (row.normalized_data or {}).get("source_property_id"),
            "source_unit_id": (row.normalized_data or {}).get("source_unit_id"),
            "resolution_action": row.resolution_action,
            "resolution_target_gl_account_id": row.resolution_target_gl_account_id,
            "resolution_target_id": row.resolution_target_id,
            "resolution_target_unit_id": row.resolution_target_unit_id,
            "accepted_for_later_commit": row.resolution_action == "ACCEPT_RELATIONSHIP",
            "target_accounting_mutation": False,
            "accounting_history_mutation": False,
        },
    )
    db.commit()
    db.refresh(row)
    return row


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/rows/{staged_row_id}/bill-resolution",
    response_model=AppFolioMigrationStagedRowOut,
)
def resolve_staged_appfolio_bill(
    run_id: int,
    upload_id: int,
    staged_row_id: int,
    payload: AppFolioStagedBillResolutionIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    if upload.detected_resource != "BILLS":
        raise HTTPException(
            status_code=409,
            detail="Only staged BILLS rows can be resolved here.",
        )
    row = _staged_row(db, run=run, upload=upload, staged_row_id=staged_row_id)
    if row.resource != "BILLS" or row.errors or row.disposition == "INVALID":
        raise HTTPException(
            status_code=409,
            detail="Invalid staged Bill rows cannot be resolved.",
        )
    if not row.source_id and payload.action != "SKIP":
        raise HTTPException(
            status_code=409,
            detail="Bill rows without a durable Bill ID may only be skipped.",
        )

    target_vendor_id = None
    target_property_id = None

    if payload.action == "ACCEPT_RELATIONSHIP":
        data = dict(row.normalized_data or {})
        source_vendor_id = str(data.get("source_vendor_id") or "").strip()
        source_property_id = str(data.get("source_property_id") or "").strip()
        if not source_vendor_id:
            raise HTTPException(
                status_code=409,
                detail="Bill relationship requires a source VendorId.",
            )

        vendor_mapping = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "APPFOLIO",
                PlatformMigrationItem.resource == "VENDORS",
                PlatformMigrationItem.source_id == source_vendor_id,
            )
            .first()
        )
        if vendor_mapping is None or vendor_mapping.target_entity != "VENDOR":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Bill relationship cannot be accepted until the source "
                    "VendorId has a durable VENDOR mapping."
                ),
            )
        target_vendor = (
            db.query(Vendor)
            .filter(
                Vendor.id == vendor_mapping.target_id,
                Vendor.organization_id == run.organization_id,
                Vendor.is_active.is_(True),
                Vendor.deleted_at.is_(None),
            )
            .first()
        )
        if target_vendor is None:
            raise HTTPException(
                status_code=409,
                detail="Mapped Bill Vendor is no longer active in this organization.",
            )
        target_vendor_id = target_vendor.id

        if source_property_id:
            property_mapping = (
                db.query(PlatformMigrationItem)
                .filter(
                    PlatformMigrationItem.run_id == run.id,
                    PlatformMigrationItem.organization_id == run.organization_id,
                    PlatformMigrationItem.provider == "APPFOLIO",
                    PlatformMigrationItem.resource == "PROPERTIES",
                    PlatformMigrationItem.source_id == source_property_id,
                )
                .first()
            )
            if property_mapping is None or property_mapping.target_entity != "PROPERTY":
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Supplied Bill PropertyId must have a durable PROPERTY "
                        "mapping before acceptance."
                    ),
                )
            target_property = (
                db.query(Property)
                .filter(
                    Property.id == property_mapping.target_id,
                    Property.organization_id == run.organization_id,
                    Property.is_active.is_(True),
                    Property.deleted_at.is_(None),
                )
                .first()
            )
            if target_property is None:
                raise HTTPException(
                    status_code=409,
                    detail="Mapped Bill Property is no longer active in this organization.",
                )
            target_property_id = target_property.id

    if (
        row.resolution_action == payload.action
        and row.resolution_target_vendor_id == target_vendor_id
        and row.resolution_target_id == target_property_id
    ):
        return row

    row.resolution_action = payload.action
    row.resolution_target_vendor_id = target_vendor_id
    row.resolution_target_id = target_property_id
    row.resolution_target_unit_id = None
    row.resolution_target_owner_user_id = None
    row.resolution_target_tenant_user_id = None
    row.resolution_target_gl_account_id = None
    row.resolved_by_platform_user_id = current_user.id
    row.resolved_at = datetime.utcnow()
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    run.status = "STAGED"
    append_audit_log(
        db,
        platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_staged_row",
        entity_id=row.id,
        action="appfolio_bill_resolution_changed",
        new_value={
            "upload_id": upload.id,
            "source_bill_id": row.source_id,
            "source_vendor_id": (row.normalized_data or {}).get("source_vendor_id"),
            "source_property_id": (row.normalized_data or {}).get("source_property_id"),
            "resolution_action": row.resolution_action,
            "resolution_target_vendor_id": row.resolution_target_vendor_id,
            "resolution_target_id": row.resolution_target_id,
            "accepted_for_later_commit": row.resolution_action == "ACCEPT_RELATIONSHIP",
            "target_bill_mutation": False,
            "accounting_history_mutation": False,
        },
    )
    db.commit()
    db.refresh(row)
    return row


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/rows/{staged_row_id}/work-order-resolution",
    response_model=AppFolioMigrationStagedRowOut,
)
def resolve_staged_appfolio_work_order(
    run_id: int,
    upload_id: int,
    staged_row_id: int,
    payload: AppFolioStagedWorkOrderResolutionIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    if upload.detected_resource != "WORK_ORDERS":
        raise HTTPException(
            status_code=409,
            detail="Only staged WORK_ORDERS rows can be resolved here.",
        )
    row = _staged_row(db, run=run, upload=upload, staged_row_id=staged_row_id)
    if row.resource != "WORK_ORDERS" or row.errors or row.disposition == "INVALID":
        raise HTTPException(
            status_code=409,
            detail="Invalid staged Work Order rows cannot be resolved.",
        )
    if not row.source_id and payload.action != "SKIP":
        raise HTTPException(
            status_code=409,
            detail="Work Order rows without a durable Work Order ID may only be skipped.",
        )

    target_property_id = None
    target_unit_id = None
    target_vendor_id = None

    if payload.action == "ACCEPT_RELATIONSHIP":
        data = dict(row.normalized_data or {})
        source_property_id = str(data.get("source_property_id") or "").strip()
        source_unit_id = str(data.get("source_unit_id") or "").strip()
        source_vendor_id = str(data.get("source_vendor_id") or "").strip()

        if not source_property_id:
            raise HTTPException(
                status_code=409,
                detail="Work Order relationship requires a source PropertyId.",
            )

        property_mapping = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "APPFOLIO",
                PlatformMigrationItem.resource == "PROPERTIES",
                PlatformMigrationItem.source_id == source_property_id,
            )
            .first()
        )
        if property_mapping is None or property_mapping.target_entity != "PROPERTY":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Supplied Work Order PropertyId must have a durable PROPERTY "
                    "mapping before acceptance."
                ),
            )
        target_property = (
            db.query(Property)
            .filter(
                Property.id == property_mapping.target_id,
                Property.organization_id == run.organization_id,
                Property.is_active.is_(True),
                Property.deleted_at.is_(None),
            )
            .first()
        )
        if target_property is None:
            raise HTTPException(
                status_code=409,
                detail="Mapped Work Order Property is no longer active in this organization.",
            )
        target_property_id = target_property.id

        target_unit = None
        if source_unit_id:
            unit_mapping = (
                db.query(PlatformMigrationItem)
                .filter(
                    PlatformMigrationItem.run_id == run.id,
                    PlatformMigrationItem.organization_id == run.organization_id,
                    PlatformMigrationItem.provider == "APPFOLIO",
                    PlatformMigrationItem.resource == "UNITS",
                    PlatformMigrationItem.source_id == source_unit_id,
                )
                .first()
            )
            if unit_mapping is None or unit_mapping.target_entity != "UNIT":
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Supplied Work Order UnitId must have a durable UNIT "
                        "mapping before acceptance."
                    ),
                )
            target_unit = (
                db.query(Unit)
                .join(Property, Property.id == Unit.property_id)
                .filter(
                    Unit.id == unit_mapping.target_id,
                    Unit.is_active.is_(True),
                    Unit.deleted_at.is_(None),
                    Property.organization_id == run.organization_id,
                    Property.is_active.is_(True),
                    Property.deleted_at.is_(None),
                )
                .first()
            )
            if target_unit is None:
                raise HTTPException(
                    status_code=409,
                    detail="Mapped Work Order Unit is no longer active in this organization.",
                )
            if target_unit.property_id != target_property.id:
                raise HTTPException(
                    status_code=409,
                    detail="Mapped Work Order Unit does not belong to the mapped Property.",
                )
            target_unit_id = target_unit.id

        if source_vendor_id:
            vendor_mapping = (
                db.query(PlatformMigrationItem)
                .filter(
                    PlatformMigrationItem.run_id == run.id,
                    PlatformMigrationItem.organization_id == run.organization_id,
                    PlatformMigrationItem.provider == "APPFOLIO",
                    PlatformMigrationItem.resource == "VENDORS",
                    PlatformMigrationItem.source_id == source_vendor_id,
                )
                .first()
            )
            if vendor_mapping is None or vendor_mapping.target_entity != "VENDOR":
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Supplied Work Order VendorId must have a durable VENDOR "
                        "mapping before acceptance."
                    ),
                )
            target_vendor = (
                db.query(Vendor)
                .filter(
                    Vendor.id == vendor_mapping.target_id,
                    Vendor.organization_id == run.organization_id,
                    Vendor.is_active.is_(True),
                    Vendor.deleted_at.is_(None),
                )
                .first()
            )
            if target_vendor is None:
                raise HTTPException(
                    status_code=409,
                    detail="Mapped Work Order Vendor is no longer active in this organization.",
                )
            target_vendor_id = target_vendor.id

    if (
        row.resolution_action == payload.action
        and row.resolution_target_id == target_property_id
        and row.resolution_target_unit_id == target_unit_id
        and row.resolution_target_vendor_id == target_vendor_id
        and row.resolution_target_owner_user_id is None
        and row.resolution_target_tenant_user_id is None
        and row.resolution_target_gl_account_id is None
    ):
        return row

    row.resolution_action = payload.action
    row.resolution_target_id = target_property_id
    row.resolution_target_unit_id = target_unit_id
    row.resolution_target_vendor_id = target_vendor_id
    row.resolution_target_owner_user_id = None
    row.resolution_target_tenant_user_id = None
    row.resolution_target_gl_account_id = None
    row.resolved_by_platform_user_id = current_user.id
    row.resolved_at = datetime.utcnow()
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    run.status = "STAGED"
    append_audit_log(
        db,
        platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_staged_row",
        entity_id=row.id,
        action="appfolio_work_order_resolution_changed",
        new_value={
            "upload_id": upload.id,
            "source_work_order_id": row.source_id,
            "source_property_id": (row.normalized_data or {}).get("source_property_id"),
            "source_unit_id": (row.normalized_data or {}).get("source_unit_id"),
            "source_vendor_id": (row.normalized_data or {}).get("source_vendor_id"),
            "resolution_action": row.resolution_action,
            "resolution_target_id": row.resolution_target_id,
            "resolution_target_unit_id": row.resolution_target_unit_id,
            "resolution_target_vendor_id": row.resolution_target_vendor_id,
            "accepted_for_later_commit": row.resolution_action == "ACCEPT_RELATIONSHIP",
            "assigned_users_inferred": False,
            "workflow_state_inferred": False,
            "target_work_order_mutation": False,
            "accounting_mutation": False,
        },
    )
    db.commit()
    db.refresh(row)
    return row


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/rows/{staged_row_id}/charge-resolution",
    response_model=AppFolioMigrationStagedRowOut,
)
def resolve_staged_appfolio_charge(
    run_id: int,
    upload_id: int,
    staged_row_id: int,
    payload: AppFolioStagedChargeResolutionIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    if upload.detected_resource != "CHARGES":
        raise HTTPException(
            status_code=409,
            detail="Only staged CHARGES rows can be resolved here.",
        )
    row = _staged_row(db, run=run, upload=upload, staged_row_id=staged_row_id)
    if row.resource != "CHARGES" or row.errors or row.disposition == "INVALID":
        raise HTTPException(
            status_code=409,
            detail="Invalid staged Charge rows cannot be resolved.",
        )
    if not row.source_id and payload.action != "SKIP":
        raise HTTPException(
            status_code=409,
            detail="Charge rows without a durable Charge ID may only be skipped.",
        )

    target_gl_account_id = None
    if payload.action == "ACCEPT_RELATIONSHIP":
        data = dict(row.normalized_data or {})
        source_gl_account_id = str(data.get("source_gl_account_id") or "").strip()
        if not source_gl_account_id:
            raise HTTPException(
                status_code=409,
                detail="Charge relationship requires a source GlAccountId.",
            )
        gl_mapping = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "APPFOLIO",
                PlatformMigrationItem.resource == "GL_ACCOUNTS",
                PlatformMigrationItem.source_id == source_gl_account_id,
            )
            .first()
        )
        if gl_mapping is None or gl_mapping.target_entity != "GL_ACCOUNT":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Charge relationship cannot be accepted until the source "
                    "GlAccountId has a durable GL_ACCOUNT mapping."
                ),
            )
        target_gl = (
            db.query(GLAccount)
            .filter(
                GLAccount.id == gl_mapping.target_id,
                GLAccount.organization_id == run.organization_id,
                GLAccount.is_active.is_(True),
                GLAccount.deleted_at.is_(None),
            )
            .first()
        )
        if target_gl is None:
            raise HTTPException(
                status_code=409,
                detail="Mapped Charge GL Account is no longer active in this organization.",
            )
        target_gl_account_id = target_gl.id

    if (
        row.resolution_action == payload.action
        and row.resolution_target_gl_account_id == target_gl_account_id
        and row.resolution_target_id is None
        and row.resolution_target_unit_id is None
        and row.resolution_target_tenant_user_id is None
    ):
        return row

    row.resolution_action = payload.action
    row.resolution_target_gl_account_id = target_gl_account_id
    row.resolution_target_id = None
    row.resolution_target_unit_id = None
    row.resolution_target_owner_user_id = None
    row.resolution_target_vendor_id = None
    row.resolution_target_tenant_user_id = None
    row.resolved_by_platform_user_id = current_user.id
    row.resolved_at = datetime.utcnow()
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    run.status = "STAGED"
    append_audit_log(
        db,
        platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_staged_row",
        entity_id=row.id,
        action="appfolio_charge_resolution_changed",
        new_value={
            "upload_id": upload.id,
            "source_charge_id": row.source_id,
            "source_gl_account_id": (row.normalized_data or {}).get("source_gl_account_id"),
            "source_occupancy_id": (row.normalized_data or {}).get("source_occupancy_id"),
            "resolution_action": row.resolution_action,
            "resolution_target_gl_account_id": row.resolution_target_gl_account_id,
            "accepted_gl_relationship_only": row.resolution_action == "ACCEPT_RELATIONSHIP",
            "occupancy_mapping_inferred": False,
            "tenant_liability_inferred": False,
            "payment_state_inferred": False,
            "target_charge_mutation": False,
            "accounting_history_mutation": False,
        },
    )
    db.commit()
    db.refresh(row)
    return row


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/rows/{staged_row_id}/gl-account-resolution",
    response_model=AppFolioMigrationStagedRowOut,
)
def resolve_staged_appfolio_gl_account(
    run_id: int,
    upload_id: int,
    staged_row_id: int,
    payload: AppFolioStagedGLAccountResolutionIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    if upload.detected_resource != "GL_ACCOUNTS":
        raise HTTPException(
            status_code=409,
            detail="Only staged GL_ACCOUNTS rows can be resolved here.",
        )
    row = _staged_row(db, run=run, upload=upload, staged_row_id=staged_row_id)
    if row.resource != "GL_ACCOUNTS" or row.errors or row.disposition == "INVALID":
        raise HTTPException(
            status_code=409,
            detail="Invalid staged GL Account rows cannot be resolved.",
        )
    if row.disposition == "ALREADY_MAPPED":
        raise HTTPException(
            status_code=409,
            detail=(
                "Already-mapped staged GL Account rows are controlled by their "
                "durable source mapping."
            ),
        )
    if not row.source_id and payload.action != "SKIP":
        raise HTTPException(
            status_code=409,
            detail=(
                "GL Account rows without a durable source GL Account ID may only "
                "be skipped."
            ),
        )

    target_gl_account_id = payload.target_gl_account_id
    if payload.action == "MATCH_EXISTING":
        target = (
            db.query(GLAccount)
            .filter(
                GLAccount.id == target_gl_account_id,
                GLAccount.organization_id == run.organization_id,
                GLAccount.is_active.is_(True),
                GLAccount.deleted_at.is_(None),
            )
            .first()
        )
        if target is None:
            raise HTTPException(
                status_code=404,
                detail="Existing target GL Account not found in this organization.",
            )
    else:
        target_gl_account_id = None

    if (
        row.resolution_action == payload.action
        and row.resolution_target_gl_account_id == target_gl_account_id
    ):
        return row

    row.resolution_action = payload.action
    row.resolution_target_gl_account_id = target_gl_account_id
    row.resolution_target_id = None
    row.resolution_target_unit_id = None
    row.resolution_target_owner_user_id = None
    row.resolution_target_vendor_id = None
    row.resolution_target_tenant_user_id = None
    row.resolved_by_platform_user_id = current_user.id
    row.resolved_at = datetime.utcnow()
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    run.status = "STAGED"
    append_audit_log(
        db,
        platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_staged_row",
        entity_id=row.id,
        action="appfolio_gl_account_resolution_changed",
        new_value={
            "upload_id": upload.id,
            "source_id": row.source_id,
            "source_account_number": (row.normalized_data or {}).get("account_number"),
            "source_account_name": (row.normalized_data or {}).get("account_name"),
            "source_account_type": (row.normalized_data or {}).get("account_type"),
            "resolution_action": row.resolution_action,
            "resolution_target_gl_account_id": row.resolution_target_gl_account_id,
            "target_overwrite": False,
            "target_classification_translation": False,
            "key_account_mutation": False,
            "accounting_history_mutation": False,
        },
    )
    db.commit()
    db.refresh(row)
    return row


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/rows/{staged_row_id}/vendor-resolution",
    response_model=AppFolioMigrationStagedRowOut,
)
def resolve_staged_appfolio_vendor(
    run_id: int,
    upload_id: int,
    staged_row_id: int,
    payload: AppFolioStagedVendorResolutionIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    if upload.detected_resource != "VENDORS":
        raise HTTPException(status_code=409, detail="Only staged VENDORS rows can be resolved here.")
    row = _staged_row(db, run=run, upload=upload, staged_row_id=staged_row_id)
    if row.resource != "VENDORS" or row.errors or row.disposition == "INVALID":
        raise HTTPException(status_code=409, detail="Invalid staged Vendor rows cannot be resolved.")
    if row.disposition == "ALREADY_MAPPED":
        raise HTTPException(
            status_code=409,
            detail="Already-mapped staged Vendor rows are controlled by their durable source mapping.",
        )
    if not row.source_id and payload.action != "SKIP":
        raise HTTPException(
            status_code=409,
            detail="Vendor rows without a durable source Vendor ID may only be skipped.",
        )
    if row.disposition == "REVIEW" and payload.action != "SKIP":
        raise HTTPException(
            status_code=409,
            detail="This REVIEW Vendor row may only be skipped until durable Vendor identity is resolved.",
        )
    if payload.action == "CREATE_NEW" and row.disposition != "POSSIBLE_MATCH":
        raise HTTPException(
            status_code=409,
            detail="CREATE_NEW is only valid for a reviewed Vendor POSSIBLE_MATCH row.",
        )
    if payload.action == "MATCH_EXISTING" and row.disposition not in {"POSSIBLE_MATCH", "NEW"}:
        raise HTTPException(status_code=409, detail="This staged Vendor row cannot be matched to an existing Vendor.")

    target_vendor_id = payload.target_vendor_id
    if payload.action == "MATCH_EXISTING":
        target = (
            db.query(Vendor)
            .filter(
                Vendor.id == target_vendor_id,
                Vendor.organization_id == run.organization_id,
                Vendor.is_active.is_(True),
                Vendor.deleted_at.is_(None),
            )
            .first()
        )
        if target is None:
            raise HTTPException(status_code=404, detail="Existing target Vendor not found in this organization.")
    else:
        target_vendor_id = None

    if (
        row.resolution_action == payload.action
        and row.resolution_target_vendor_id == target_vendor_id
    ):
        return row

    row.resolution_action = payload.action
    row.resolution_target_vendor_id = target_vendor_id
    row.resolution_target_id = None
    row.resolution_target_unit_id = None
    row.resolution_target_owner_user_id = None
    row.resolution_target_tenant_user_id = None
    row.resolution_target_gl_account_id = None
    row.resolved_by_platform_user_id = current_user.id
    row.resolved_at = datetime.utcnow()
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    run.status = "STAGED"
    append_audit_log(
        db,
        platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_staged_row",
        entity_id=row.id,
        action="appfolio_vendor_resolution_changed",
        new_value={
            "upload_id": upload.id,
            "source_id": row.source_id,
            "resolution_action": row.resolution_action,
            "resolution_target_vendor_id": row.resolution_target_vendor_id,
            "raw_source_stored": False,
            "target_overwrite": False,
        },
    )
    db.commit()
    db.refresh(row)
    return row


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/properties/dry-run",
    response_model=AppFolioPropertyDryRunOut,
)
def dry_run_staged_appfolio_properties(
    run_id: int,
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    records, resolved_existing, force_create_new, review_fingerprint = _staged_property_state(
        db, run=run, upload=upload
    )
    result = dry_run_properties(
        db,
        run=run,
        include_hidden=False,
        records=records,
        source_context_fingerprint=review_fingerprint,
    )
    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=run.organization_id,
            entity_type="platform_migration_run",
            entity_id=run.id,
            action="appfolio_staged_properties_dry_run",
            new_value={
                "upload_id": upload.id,
                "source_context_fingerprint": review_fingerprint,
                "dry_run_fingerprint": result.fingerprint,
                **result.summary,
                "raw_file_stored": False,
                "target_mutation": False,
            },
        )
        db.commit()
        db.refresh(run)
    return AppFolioPropertyDryRunOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        total=result.total,
        importable=result.importable,
        skipped_hidden=result.skipped_hidden,
        invalid=result.invalid,
        warning_count=result.warning_count,
        rows=result.rows,
    )


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/properties/commit",
    response_model=AppFolioPropertyCommitOut,
)
def commit_staged_appfolio_properties(
    run_id: int,
    upload_id: int,
    payload: AppFolioStagedPropertyCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    records, resolved_existing, force_create_new, review_fingerprint = _staged_property_state(
        db, run=run, upload=upload
    )
    try:
        result = commit_properties(
            db,
            run=run,
            include_hidden=False,
            records=records,
            expected_fingerprint=payload.fingerprint,
            platform_user_id=current_user.id,
            source_context_fingerprint=review_fingerprint,
            resolved_existing_matches=resolved_existing,
            force_create_new_source_ids=force_create_new,
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="appfolio_staged_properties_committed",
                new_value={
                    "upload_id": upload.id,
                    "review_fingerprint": review_fingerprint,
                    "dry_run_fingerprint": result.fingerprint,
                    "committed": result.committed,
                    "matched_existing": result.matched_existing,
                    "skipped_hidden": result.skipped_hidden,
                    "warning_count": result.warning_count,
                    "target_property_ids": [
                        item["target_property_id"] for item in result.rows
                    ],
                    "raw_source_stored": False,
                    "target_overwrite": False,
                },
            )
        db.commit()
        db.refresh(run)
    except AppFolioMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Controlled staged property commit conflicted with migration state.",
        ) from exc

    return AppFolioPropertyCommitOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        committed=result.committed,
        matched_existing=result.matched_existing,
        skipped_hidden=result.skipped_hidden,
        warning_count=result.warning_count,
        rows=result.rows,
    )


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/units/dry-run",
    response_model=AppFolioUnitDryRunOut,
)
def dry_run_staged_appfolio_units(
    run_id: int,
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    records, resolved_existing, force_create_new, relationship_fingerprint = _staged_unit_state(
        db, run=run, upload=upload
    )
    try:
        result = dry_run_units(
            db,
            run=run,
            records=records,
            source_context_fingerprint=relationship_fingerprint,
            resolved_existing_matches=resolved_existing,
            force_create_new_source_ids=force_create_new,
        )
    except AppFolioMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=run.organization_id,
            entity_type="platform_migration_run",
            entity_id=run.id,
            action="appfolio_staged_units_dry_run",
            new_value={
                "upload_id": upload.id,
                "source_context_fingerprint": relationship_fingerprint,
                "dry_run_fingerprint": result.fingerprint,
                **result.summary,
                "raw_file_stored": False,
                "target_mutation": False,
            },
        )
        db.commit()
        db.refresh(run)
    return AppFolioUnitDryRunOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        total=result.total,
        importable=result.importable,
        invalid=result.invalid,
        warning_count=result.warning_count,
        rows=result.rows,
    )


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/units/commit",
    response_model=AppFolioUnitCommitOut,
)
def commit_staged_appfolio_units(
    run_id: int,
    upload_id: int,
    payload: AppFolioStagedUnitCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    records, resolved_existing, force_create_new, relationship_fingerprint = _staged_unit_state(
        db, run=run, upload=upload
    )
    try:
        result = commit_units(
            db,
            run=run,
            records=records,
            expected_fingerprint=payload.fingerprint,
            platform_user_id=current_user.id,
            source_context_fingerprint=relationship_fingerprint,
            resolved_existing_matches=resolved_existing,
            force_create_new_source_ids=force_create_new,
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="appfolio_staged_units_committed",
                new_value={
                    "upload_id": upload.id,
                    "source_context_fingerprint": relationship_fingerprint,
                    "fingerprint": result.fingerprint,
                    "committed": result.committed,
                    "warning_count": result.warning_count,
                    "target_unit_ids": [
                        item["target_unit_id"] for item in result.rows
                    ],
                    "raw_file_stored": False,
                    "provider_credentials_stored": False,
                },
            )
            db.commit()
            db.refresh(run)
    except AppFolioMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Unit commit conflicted with an existing target or migration mapping.",
        ) from exc

    return AppFolioUnitCommitOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        committed=result.committed,
        matched_existing=result.matched_existing,
        warning_count=result.warning_count,
        rows=result.rows,
    )


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/owners/dry-run",
    response_model=AppFolioOwnerDryRunOut,
)
def dry_run_staged_appfolio_owners(
    run_id: int,
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    records, resolved_existing, review_fingerprint = _staged_owner_state(
        db, run=run, upload=upload
    )
    try:
        result = dry_run_owners(
            db,
            run=run,
            records=records,
            source_context_fingerprint=review_fingerprint,
            resolved_existing_matches=resolved_existing,
        )
    except AppFolioMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=run.organization_id,
            entity_type="platform_migration_run",
            entity_id=run.id,
            action="appfolio_staged_owners_dry_run",
            new_value={
                "upload_id": upload.id,
                "source_context_fingerprint": review_fingerprint,
                "dry_run_fingerprint": result.fingerprint,
                **result.summary,
                "raw_file_stored": False,
                "target_mutation": False,
                "owner_user_creation": False,
                "property_ownership_mutation": False,
            },
        )
        db.commit()
        db.refresh(run)
    return AppFolioOwnerDryRunOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        total=result.total,
        importable=result.importable,
        invalid=result.invalid,
        warning_count=result.warning_count,
        rows=result.rows,
    )


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/owners/commit",
    response_model=AppFolioOwnerCommitOut,
)
def commit_staged_appfolio_owners(
    run_id: int,
    upload_id: int,
    payload: AppFolioStagedOwnerCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    records, resolved_existing, review_fingerprint = _staged_owner_state(
        db, run=run, upload=upload
    )
    try:
        result = commit_owners(
            db,
            run=run,
            records=records,
            expected_fingerprint=payload.fingerprint,
            platform_user_id=current_user.id,
            source_context_fingerprint=review_fingerprint,
            resolved_existing_matches=resolved_existing,
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="appfolio_staged_owners_committed",
                new_value={
                    "upload_id": upload.id,
                    "source_context_fingerprint": review_fingerprint,
                    "fingerprint": result.fingerprint,
                    "mapped_existing": result.mapped_existing,
                    "warning_count": result.warning_count,
                    "target_owner_user_ids": [
                        item["target_owner_user_id"] for item in result.rows
                    ],
                    "raw_file_stored": False,
                    "target_overwrite": False,
                    "owner_user_creation": False,
                    "property_ownership_mutation": False,
                    "provider_credentials_stored": False,
                },
            )
        db.commit()
        db.refresh(run)
    except AppFolioMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Owner mapping commit conflicted with an existing target or migration mapping.",
        ) from exc

    return AppFolioOwnerCommitOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        mapped_existing=result.mapped_existing,
        warning_count=result.warning_count,
        rows=result.rows,
    )


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/tenants/dry-run",
    response_model=AppFolioTenantDryRunOut,
)
def dry_run_staged_appfolio_tenants(
    run_id: int,
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    records, resolved_existing, relationship_fingerprint = _staged_tenant_state(
        db, run=run, upload=upload
    )
    try:
        result = dry_run_tenants(
            db,
            run=run,
            records=records,
            source_context_fingerprint=relationship_fingerprint,
            resolved_existing_matches=resolved_existing,
        )
    except AppFolioMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=run.organization_id,
            entity_type="platform_migration_run",
            entity_id=run.id,
            action="appfolio_staged_tenants_dry_run",
            new_value={
                "upload_id": upload.id,
                "source_context_fingerprint": relationship_fingerprint,
                "dry_run_fingerprint": result.fingerprint,
                **result.summary,
                "raw_file_stored": False,
                "target_mutation": False,
                "tenant_user_creation": False,
                "tenant_user_update": False,
                "lease_or_occupancy_mutation": False,
                "accounting_mutation": False,
            },
        )
        db.commit()
        db.refresh(run)
    return AppFolioTenantDryRunOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        total=result.total,
        importable=result.importable,
        invalid=result.invalid,
        warning_count=result.warning_count,
        rows=result.rows,
    )


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/tenants/commit",
    response_model=AppFolioTenantCommitOut,
)
def commit_staged_appfolio_tenants(
    run_id: int,
    upload_id: int,
    payload: AppFolioStagedTenantCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    records, resolved_existing, relationship_fingerprint = _staged_tenant_state(
        db, run=run, upload=upload
    )
    try:
        result = commit_tenants(
            db,
            run=run,
            records=records,
            expected_fingerprint=payload.fingerprint,
            platform_user_id=current_user.id,
            source_context_fingerprint=relationship_fingerprint,
            resolved_existing_matches=resolved_existing,
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="appfolio_staged_tenants_committed",
                new_value={
                    "upload_id": upload.id,
                    "source_context_fingerprint": relationship_fingerprint,
                    "fingerprint": result.fingerprint,
                    "mapped_existing": result.mapped_existing,
                    "warning_count": result.warning_count,
                    "target_tenant_user_ids": [
                        item["target_tenant_user_id"] for item in result.rows
                    ],
                    "raw_file_stored": False,
                    "target_overwrite": False,
                    "tenant_user_creation": False,
                    "tenant_user_update": False,
                    "lease_or_occupancy_mutation": False,
                    "accounting_mutation": False,
                    "provider_credentials_stored": False,
                },
            )
        db.commit()
        db.refresh(run)
    except AppFolioMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Tenant mapping commit conflicted with an existing target or migration mapping.",
        ) from exc

    return AppFolioTenantCommitOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        mapped_existing=result.mapped_existing,
        warning_count=result.warning_count,
        rows=result.rows,
    )


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/bills/dry-run",
    response_model=AppFolioBillDryRunOut,
)
def dry_run_staged_appfolio_bills(
    run_id: int,
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    rows, fingerprint, counts = _staged_bill_dry_run_state(
        db, run=run, upload=upload
    )
    replayed = (
        run.last_dry_run_fingerprint == fingerprint
        and (run.last_dry_run_summary or {}).get("resource") == "BILLS"
    )
    summary = {
        **counts,
        "resource": "BILLS",
        "review_only": True,
        "target_mutation": False,
        "bill_mutation": False,
        "bill_line_mutation": False,
        "check_payment_mutation": False,
        "vendor_mutation": False,
        "work_order_mutation": False,
        "accounting_history_mutation": False,
        "approval_state_inferred": False,
        "payment_state_inferred": False,
        "gl_allocation_inferred": False,
        "work_order_linkage_inferred": False,
    }
    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = summary
        run.status = "DRY_RUN_READY"
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=run.organization_id,
            entity_type="platform_migration_run",
            entity_id=run.id,
            action="appfolio_staged_bills_dry_run",
            new_value={
                "upload_id": upload.id,
                "dry_run_fingerprint": fingerprint,
                **summary,
                "raw_file_stored": False,
                "bill_mutation": False,
                "bill_line_mutation": False,
                "check_mutation": False,
                "gl_transaction_mutation": False,
                "gl_entry_mutation": False,
                "charge_mutation": False,
            },
        )
        db.commit()
        db.refresh(run)

    return AppFolioBillDryRunOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        fingerprint=fingerprint,
        replayed=replayed,
        total=counts["total"],
        importable=counts["importable"],
        invalid=counts["invalid"],
        warning_count=counts["warning_count"],
        rows=rows,
    )


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/work-orders/dry-run",
    response_model=AppFolioWorkOrderDryRunOut,
)
def dry_run_staged_appfolio_work_orders(
    run_id: int,
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    rows, fingerprint, counts = _staged_work_order_dry_run_state(
        db, run=run, upload=upload
    )
    replayed = (
        run.last_dry_run_fingerprint == fingerprint
        and (run.last_dry_run_summary or {}).get("resource") == "WORK_ORDERS"
    )
    summary = {
        **counts,
        "resource": "WORK_ORDERS",
        "review_only": True,
        "target_mutation": False,
        "work_order_mutation": False,
        "bill_mutation": False,
        "charge_mutation": False,
        "accounting_history_mutation": False,
        "staff_assignment_inferred": False,
        "requester_tenant_occupancy_inferred": False,
        "vendor_contract_inferred": False,
        "workflow_state_translated": False,
        "completion_cancellation_semantics_inferred": False,
    }
    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = summary
        run.status = "DRY_RUN_READY"
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=run.organization_id,
            entity_type="platform_migration_run",
            entity_id=run.id,
            action="appfolio_staged_work_orders_dry_run",
            new_value={
                "upload_id": upload.id,
                "dry_run_fingerprint": fingerprint,
                **summary,
                "raw_file_stored": False,
                "work_order_mutation": False,
                "bill_mutation": False,
                "charge_mutation": False,
                "gl_transaction_mutation": False,
                "gl_entry_mutation": False,
                "inventory_mutation": False,
                "purchase_order_mutation": False,
                "vendor_payment_mutation": False,
            },
        )
        db.commit()
        db.refresh(run)

    return AppFolioWorkOrderDryRunOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        fingerprint=fingerprint,
        replayed=replayed,
        total=counts["total"],
        importable=counts["importable"],
        invalid=counts["invalid"],
        warning_count=counts["warning_count"],
        rows=rows,
    )


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/charges/dry-run",
    response_model=AppFolioChargeDryRunOut,
)
def dry_run_staged_appfolio_charges(
    run_id: int,
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    rows, fingerprint, counts = _staged_charge_dry_run_state(
        db, run=run, upload=upload
    )
    replayed = (
        run.last_dry_run_fingerprint == fingerprint
        and (run.last_dry_run_summary or {}).get("resource") == "CHARGES"
    )
    summary = {
        **counts,
        "resource": "CHARGES",
        "review_only": True,
        "target_mutation": False,
        "charge_mutation": False,
        "rent_invoice_mutation": False,
        "receipt_payment_mutation": False,
        "accounting_history_mutation": False,
        "occupancy_target_inferred": False,
        "tenant_liability_inferred": False,
        "payment_state_inferred": False,
        "original_amount_inferred": False,
        "rent_classification_inferred": False,
        "gl_posting_inferred": False,
    }
    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = summary
        run.status = "DRY_RUN_READY"
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=run.organization_id,
            entity_type="platform_migration_run",
            entity_id=run.id,
            action="appfolio_staged_charges_dry_run",
            new_value={
                "upload_id": upload.id,
                "dry_run_fingerprint": fingerprint,
                **summary,
                "raw_file_stored": False,
                "charge_mutation": False,
                "rent_invoice_mutation": False,
                "receipt_mutation": False,
                "payment_mutation": False,
                "gl_transaction_mutation": False,
                "gl_entry_mutation": False,
            },
        )
        db.commit()
        db.refresh(run)

    return AppFolioChargeDryRunOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        fingerprint=fingerprint,
        replayed=replayed,
        total=counts["total"],
        importable=counts["importable"],
        invalid=counts["invalid"],
        warning_count=counts["warning_count"],
        rows=rows,
    )


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/general-ledger/dry-run",
    response_model=AppFolioGeneralLedgerDryRunOut,
)
def dry_run_staged_appfolio_general_ledger(
    run_id: int,
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    rows, fingerprint, counts = _staged_general_ledger_dry_run_state(
        db, run=run, upload=upload
    )
    replayed = run.last_dry_run_fingerprint == fingerprint
    summary = {
        **counts,
        "resource": "GENERAL_LEDGER",
        "review_only": True,
        "target_mutation": False,
        "accounting_history_mutation": False,
        "transaction_grouping_inferred": False,
        "balancing_entries_inferred": False,
        "payer_payee_inferred": False,
    }
    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = summary
        run.status = "DRY_RUN_READY"
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=run.organization_id,
            entity_type="platform_migration_run",
            entity_id=run.id,
            action="appfolio_staged_general_ledger_dry_run",
            new_value={
                "upload_id": upload.id,
                "dry_run_fingerprint": fingerprint,
                **summary,
                "raw_file_stored": False,
                "gl_transaction_mutation": False,
                "gl_entry_mutation": False,
                "journal_entry_mutation": False,
                "receipt_bill_charge_mutation": False,
                "gl_account_mutation": False,
                "key_account_mutation": False,
            },
        )
        db.commit()
        db.refresh(run)

    return AppFolioGeneralLedgerDryRunOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        fingerprint=fingerprint,
        replayed=replayed,
        total=counts["total"],
        importable=counts["importable"],
        invalid=counts["invalid"],
        warning_count=counts["warning_count"],
        rows=rows,
    )


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/general-ledger/commit-readiness",
    response_model=AppFolioGeneralLedgerCommitReadinessOut,
)
def analyze_staged_appfolio_general_ledger_commit_readiness(
    run_id: int,
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    groups, dry_run_fingerprint, readiness_fingerprint = (
        _general_ledger_commit_readiness_state(db, run=run, upload=upload)
    )
    previous = dict(run.last_dry_run_summary or {})
    prior_readiness = previous.get("ledger_commit_readiness_fingerprint")
    replayed = prior_readiness == readiness_fingerprint
    summary = {
        **previous,
        "resource": "GENERAL_LEDGER",
        "ledger_commit_readiness_fingerprint": readiness_fingerprint,
        "ledger_commit_readiness_group_count": len(groups),
        "ledger_commit_readiness_line_count": sum(int(group["line_count"]) for group in groups),
        "ledger_commit_ready": True,
        "accounting_history_mutation": False,
        "target_transaction_grouping_inferred": False,
        "balancing_entries_inferred": False,
        "payer_payee_inferred": False,
    }
    if not replayed:
        run.last_dry_run_summary = summary
        run.status = "DRY_RUN_READY"
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=run.organization_id,
            entity_type="platform_migration_run",
            entity_id=run.id,
            action="appfolio_staged_general_ledger_commit_readiness",
            new_value={
                "upload_id": upload.id,
                "dry_run_fingerprint": dry_run_fingerprint,
                "readiness_fingerprint": readiness_fingerprint,
                "group_count": len(groups),
                "line_count": sum(int(group["line_count"]) for group in groups),
                "source_transaction_ids_only": True,
                "source_balance_check_only": True,
                "gl_transaction_mutation": False,
                "gl_entry_mutation": False,
                "journal_entry_mutation": False,
                "receipt_bill_charge_mutation": False,
                "gl_account_mutation": False,
                "key_account_mutation": False,
            },
        )
        db.commit()
        db.refresh(run)

    return AppFolioGeneralLedgerCommitReadinessOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        dry_run_fingerprint=dry_run_fingerprint,
        readiness_fingerprint=readiness_fingerprint,
        replayed=replayed,
        group_count=len(groups),
        line_count=sum(int(group["line_count"]) for group in groups),
        groups=groups,
    )


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/gl-accounts/dry-run",
    response_model=AppFolioGLAccountDryRunOut,
)
def dry_run_staged_appfolio_gl_accounts(
    run_id: int,
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    records, resolved_existing, review_fingerprint = _staged_gl_account_state(
        db, run=run, upload=upload
    )
    try:
        result = dry_run_gl_accounts(
            db,
            run=run,
            records=records,
            source_context_fingerprint=review_fingerprint,
            resolved_existing_matches=resolved_existing,
        )
    except AppFolioMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=run.organization_id,
            entity_type="platform_migration_run",
            entity_id=run.id,
            action="appfolio_staged_gl_accounts_dry_run",
            new_value={
                "upload_id": upload.id,
                "source_context_fingerprint": review_fingerprint,
                "dry_run_fingerprint": result.fingerprint,
                **result.summary,
                "raw_file_stored": False,
                "target_mutation": False,
                "gl_account_creation": False,
                "gl_account_update": False,
                "classification_translation": False,
                "key_account_mutation": False,
                "accounting_history_mutation": False,
            },
        )
        db.commit()
        db.refresh(run)
    return AppFolioGLAccountDryRunOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        total=result.total,
        importable=result.importable,
        invalid=result.invalid,
        warning_count=result.warning_count,
        rows=result.rows,
    )


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/gl-accounts/commit",
    response_model=AppFolioGLAccountCommitOut,
)
def commit_staged_appfolio_gl_accounts(
    run_id: int,
    upload_id: int,
    payload: AppFolioStagedGLAccountCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    records, resolved_existing, review_fingerprint = _staged_gl_account_state(
        db, run=run, upload=upload
    )
    try:
        result = commit_gl_accounts(
            db,
            run=run,
            records=records,
            expected_fingerprint=payload.fingerprint,
            platform_user_id=current_user.id,
            source_context_fingerprint=review_fingerprint,
            resolved_existing_matches=resolved_existing,
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="appfolio_staged_gl_accounts_committed",
                new_value={
                    "upload_id": upload.id,
                    "source_context_fingerprint": review_fingerprint,
                    "fingerprint": result.fingerprint,
                    "mapped_existing": result.mapped_existing,
                    "warning_count": result.warning_count,
                    "target_gl_account_ids": [
                        item["target_gl_account_id"] for item in result.rows
                    ],
                    "raw_file_stored": False,
                    "target_overwrite": False,
                    "gl_account_creation": False,
                    "gl_account_update": False,
                    "classification_translation": False,
                    "key_account_mutation": False,
                    "accounting_history_mutation": False,
                    "provider_credentials_stored": False,
                },
            )
        db.commit()
        db.refresh(run)
    except AppFolioMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "GL Account mapping commit conflicted with an existing target or "
                "migration mapping."
            ),
        ) from exc

    return AppFolioGLAccountCommitOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        mapped_existing=result.mapped_existing,
        warning_count=result.warning_count,
        rows=result.rows,
    )


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/vendors/dry-run",
    response_model=AppFolioVendorDryRunOut,
)
def dry_run_staged_appfolio_vendors(
    run_id: int,
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    records, resolved_existing, force_create_new, review_fingerprint = _staged_vendor_state(
        db, run=run, upload=upload
    )
    try:
        result = dry_run_vendors(
            db,
            run=run,
            records=records,
            source_context_fingerprint=review_fingerprint,
            resolved_existing_matches=resolved_existing,
            force_create_new_source_ids=force_create_new,
        )
    except AppFolioMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=run.organization_id,
            entity_type="platform_migration_run",
            entity_id=run.id,
            action="appfolio_staged_vendors_dry_run",
            new_value={
                "upload_id": upload.id,
                "source_context_fingerprint": review_fingerprint,
                "dry_run_fingerprint": result.fingerprint,
                **result.summary,
                "raw_file_stored": False,
                "target_mutation": False,
            },
        )
        db.commit()
        db.refresh(run)
    return AppFolioVendorDryRunOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        total=result.total,
        importable=result.importable,
        invalid=result.invalid,
        warning_count=result.warning_count,
        rows=result.rows,
    )


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/vendors/commit",
    response_model=AppFolioVendorCommitOut,
)
def commit_staged_appfolio_vendors(
    run_id: int,
    upload_id: int,
    payload: AppFolioStagedVendorCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    records, resolved_existing, force_create_new, review_fingerprint = _staged_vendor_state(
        db, run=run, upload=upload
    )
    try:
        result = commit_vendors(
            db,
            run=run,
            records=records,
            expected_fingerprint=payload.fingerprint,
            platform_user_id=current_user.id,
            source_context_fingerprint=review_fingerprint,
            resolved_existing_matches=resolved_existing,
            force_create_new_source_ids=force_create_new,
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="appfolio_staged_vendors_committed",
                new_value={
                    "upload_id": upload.id,
                    "source_context_fingerprint": review_fingerprint,
                    "fingerprint": result.fingerprint,
                    "committed": result.committed,
                    "matched_existing": result.matched_existing,
                    "warning_count": result.warning_count,
                    "target_vendor_ids": [
                        item["target_vendor_id"] for item in result.rows
                    ],
                    "raw_file_stored": False,
                    "target_overwrite": False,
                    "provider_credentials_stored": False,
                },
            )
        db.commit()
        db.refresh(run)
    except AppFolioMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Vendor commit conflicted with an existing target or migration mapping.",
        ) from exc

    return AppFolioVendorCommitOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        committed=result.committed,
        matched_existing=result.matched_existing,
        warning_count=result.warning_count,
        rows=result.rows,
    )


@router.post(
    "/runs/{run_id}/uploads",
    response_model=AppFolioMigrationUploadOut,
    status_code=status.HTTP_201_CREATED,
)
async def stage_appfolio_upload(
    run_id: int,
    file: UploadFile = File(...),
    resource: str | None = Form(default=None),
    sheet_name: str | None = Form(default=None),
    column_mapping_json: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    filename = Path(file.filename or "").name.strip()
    if not filename:
        raise HTTPException(status_code=422, detail="A source filename is required.")

    mapping: dict[str, str] | None = None
    if column_mapping_json:
        try:
            parsed = json.loads(column_mapping_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="column_mapping_json must be valid JSON.") from exc
        if not isinstance(parsed, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in parsed.items()
        ):
            raise HTTPException(
                status_code=422,
                detail="column_mapping_json must be an object of target fields to source headers.",
            )
        mapping = parsed

    content = await file.read(MAX_FILE_BYTES + 1)
    try:
        result = stage_appfolio_file(
            db,
            run=run,
            filename=filename,
            content=content,
            resource_override=resource,
            sheet_name=sheet_name,
            explicit_mapping=mapping,
            platform_user_id=current_user.id,
        )
        active_rules = (
            db.query(PlatformMigrationCorrectionRule)
            .filter(
                PlatformMigrationCorrectionRule.run_id == run.id,
                PlatformMigrationCorrectionRule.organization_id == run.organization_id,
                PlatformMigrationCorrectionRule.provider == "APPFOLIO",
                PlatformMigrationCorrectionRule.resource == result.upload.detected_resource,
            )
            .order_by(
                PlatformMigrationCorrectionRule.field_name.asc(),
                PlatformMigrationCorrectionRule.source_value.asc(),
                PlatformMigrationCorrectionRule.id.asc(),
            )
            .all()
        )
        correction_rule_rows_applied = 0
        for rule in active_rules:
            correction_rule_rows_applied += _apply_correction_rule_to_staged_rows(
                db,
                run=run,
                rule=rule,
                platform_user_id=current_user.id,
            )

        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="appfolio_file_staged",
                new_value={
                    "upload_id": result.upload.id,
                    "filename": result.upload.filename,
                    "file_format": result.upload.file_format,
                    "normalized_fingerprint": result.upload.normalized_fingerprint,
                    "detected_resource": result.upload.detected_resource,
                    "status": result.upload.status,
                    "row_count": result.upload.row_count,
                    "validation_summary": result.upload.validation_summary,
                    "raw_file_stored": False,
                    "target_mutation": False,
                    "provider_credentials_stored": False,
                    "correction_rule_rows_applied": correction_rule_rows_applied,
                },
            )
        if not result.replayed or correction_rule_rows_applied:
            db.commit()
            db.refresh(result.upload)
    except AppFolioFileIngestionError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Staged upload conflicted with an existing replay.") from exc
    return _upload_out(result.upload, replayed=result.replayed)


@router.get(
    "/runs/{run_id}/uploads",
    response_model=list[AppFolioMigrationUploadOut],
)
def list_appfolio_uploads(
    run_id: int,
    response: Response,
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=False)
    rows = (
        db.query(PlatformMigrationUpload)
        .filter(
            PlatformMigrationUpload.run_id == run.id,
            PlatformMigrationUpload.organization_id == run.organization_id,
            PlatformMigrationUpload.provider == "APPFOLIO",
        )
        .order_by(PlatformMigrationUpload.created_at.desc(), PlatformMigrationUpload.id.desc())
        .limit(limit)
        .all()
    )
    response.headers["Cache-Control"] = "no-store"
    return [_upload_out(row, replayed=False) for row in rows]


@router.get(
    "/runs/{run_id}/coverage",
    response_model=AppFolioMigrationCoverageOut,
)
def get_appfolio_migration_coverage(
    run_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=False)
    uploads = (
        db.query(PlatformMigrationUpload)
        .filter(
            PlatformMigrationUpload.run_id == run.id,
            PlatformMigrationUpload.organization_id == run.organization_id,
            PlatformMigrationUpload.provider == "APPFOLIO",
        )
        .order_by(
            PlatformMigrationUpload.created_at.asc(),
            PlatformMigrationUpload.id.asc(),
        )
        .all()
    )

    by_resource: dict[str, list[PlatformMigrationUpload]] = {}
    for upload in uploads:
        by_resource.setdefault(upload.detected_resource, []).append(upload)

    mappings = (
        db.query(PlatformMigrationItem)
        .filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "APPFOLIO",
        )
        .all()
    )
    mappings_by_resource: dict[str, list[PlatformMigrationItem]] = {}
    for mapping in mappings:
        mappings_by_resource.setdefault(mapping.resource, []).append(mapping)

    items: list[dict[str, object]] = []
    top_level_blockers: list[str] = []
    supplied_count = 0
    partial_count = 0
    missing_count = 0
    blocked_count = 0

    for resource, label in _MIGRATION_COVERAGE_RESOURCES:
        resource_uploads = by_resource.get(resource, [])
        resource_mappings = mappings_by_resource.get(resource, [])
        has_source_evidence = bool(resource_uploads or resource_mappings)
        blockers: list[str] = []
        if resource in _MIGRATION_SOURCE_SCHEMA_BLOCKERS:
            state = "BLOCKED"
            blockers.append(_MIGRATION_SOURCE_SCHEMA_BLOCKERS[resource])
            blocked_count += 1
        elif not has_source_evidence:
            state = "MISSING"
            missing_count += 1
        elif resource in _MIGRATION_PARTIAL_BLOCKERS:
            state = "PARTIAL"
            blockers.append(_MIGRATION_PARTIAL_BLOCKERS[resource])
            partial_count += 1
        else:
            state = "SUPPLIED"
            supplied_count += 1

        if blockers:
            top_level_blockers.extend(
                f"{label}: {blocker}" for blocker in blockers
            )
        items.append(
            {
                "resource": resource,
                "label": label,
                "state": state,
                "upload_count": len(resource_uploads),
                "mapping_count": len(resource_mappings),
                "row_count": sum(int(upload.row_count or 0) for upload in resource_uploads),
                "latest_upload_status": (
                    resource_uploads[-1].status if resource_uploads else None
                ),
                "blockers": blockers,
            }
        )

    state_by_resource = {str(item["resource"]): str(item["state"]) for item in items}
    accounting_complete = all(
        state_by_resource.get(resource) == "SUPPLIED"
        for resource in _ACCOUNTING_COVERAGE_RESOURCES
    )
    if not accounting_complete:
        top_level_blockers.append(
            "Accounting migration is not complete until every required accounting "
            "source family is supplied under a verified commit-safe contract and "
            "the applicable reconciliation controls pass."
        )

    operational_resources = {"PROPERTIES", "UNITS", "OWNERS", "VENDORS", "TENANTS"}
    partial_operational_migration_may_be_possible = any(
        state_by_resource.get(resource) == "SUPPLIED"
        for resource in operational_resources
    )

    response.headers["Cache-Control"] = "no-store"
    return AppFolioMigrationCoverageOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        supplied_count=supplied_count,
        partial_count=partial_count,
        missing_count=missing_count,
        blocked_count=blocked_count,
        accounting_complete=accounting_complete,
        partial_operational_migration_may_be_possible=(
            partial_operational_migration_may_be_possible
        ),
        items=items,
        blockers=top_level_blockers,
    )


@router.get(
    "/runs/{run_id}/review-summary",
    response_model=AppFolioMigrationReviewSummaryOut,
)
def get_appfolio_migration_review_summary(
    run_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Read-only run-level staged review/readiness summary.

    This aggregates durable staging/review/mapping evidence only. It does not
    infer accounting completeness, target mutation readiness or financial
    commit safety beyond the already-recorded staged review state.
    """
    run = _run(db, run_id=run_id, current_user=current_user, write=False)
    uploads = (
        db.query(PlatformMigrationUpload)
        .filter(
            PlatformMigrationUpload.run_id == run.id,
            PlatformMigrationUpload.organization_id == run.organization_id,
            PlatformMigrationUpload.provider == "APPFOLIO",
        )
        .order_by(PlatformMigrationUpload.id.asc())
        .all()
    )
    rows = (
        db.query(PlatformMigrationStagedRow)
        .filter(
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.organization_id == run.organization_id,
            PlatformMigrationStagedRow.provider == "APPFOLIO",
        )
        .order_by(
            PlatformMigrationStagedRow.resource.asc(),
            PlatformMigrationStagedRow.upload_id.asc(),
            PlatformMigrationStagedRow.row_number.asc(),
            PlatformMigrationStagedRow.id.asc(),
        )
        .all()
    )
    mappings = (
        db.query(PlatformMigrationItem)
        .filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "APPFOLIO",
        )
        .all()
    )

    uploads_by_resource: dict[str, int] = {}
    for upload in uploads:
        uploads_by_resource[upload.detected_resource] = (
            uploads_by_resource.get(upload.detected_resource, 0) + 1
        )

    mappings_by_resource: dict[str, int] = {}
    for mapping in mappings:
        mappings_by_resource[mapping.resource] = (
            mappings_by_resource.get(mapping.resource, 0) + 1
        )

    def blank_counts() -> dict[str, int]:
        return {
            "row_count": 0,
            "new": 0,
            "possible_matches": 0,
            "matched_existing": 0,
            "create_new": 0,
            "accepted_relationships": 0,
            "already_imported": 0,
            "skipped": 0,
            "invalid": 0,
            "unresolved_review": 0,
            "warning_count": 0,
            "blocking_count": 0,
        }

    by_resource: dict[str, dict[str, int]] = {}
    totals = blank_counts()

    for row in rows:
        counts = by_resource.setdefault(row.resource, blank_counts())
        for bucket in (counts, totals):
            bucket["row_count"] += 1
            bucket["warning_count"] += len(row.warnings or [])

        action = row.resolution_action
        disposition = row.disposition
        has_errors = bool(row.errors)

        if action == "SKIP":
            for bucket in (counts, totals):
                bucket["skipped"] += 1
            # Explicit SKIP is a resolved review decision; an INVALID/error row
            # still remains invalid evidence and cannot be represented as safe.
            if disposition == "INVALID" or has_errors:
                for bucket in (counts, totals):
                    bucket["invalid"] += 1
                    bucket["blocking_count"] += 1
            continue

        if disposition == "INVALID" or has_errors:
            for bucket in (counts, totals):
                bucket["invalid"] += 1
                bucket["blocking_count"] += 1
            continue

        if action == "MATCH_EXISTING":
            for bucket in (counts, totals):
                bucket["matched_existing"] += 1
            continue
        if action == "CREATE_NEW":
            for bucket in (counts, totals):
                bucket["create_new"] += 1
            continue
        if action == "ACCEPT_RELATIONSHIP":
            for bucket in (counts, totals):
                bucket["accepted_relationships"] += 1
            continue

        if disposition == "ALREADY_MAPPED":
            for bucket in (counts, totals):
                bucket["already_imported"] += 1
        elif disposition == "POSSIBLE_MATCH":
            for bucket in (counts, totals):
                bucket["possible_matches"] += 1
                bucket["blocking_count"] += 1
        elif disposition == "REVIEW":
            for bucket in (counts, totals):
                bucket["unresolved_review"] += 1
                bucket["blocking_count"] += 1
        elif disposition == "NEW":
            for bucket in (counts, totals):
                bucket["new"] += 1
        else:
            # Unknown staged dispositions are surfaced conservatively as review
            # blockers instead of being silently treated as importable.
            for bucket in (counts, totals):
                bucket["unresolved_review"] += 1
                bucket["blocking_count"] += 1

    resources = []
    all_resources = sorted(
        set(uploads_by_resource) | set(by_resource) | set(mappings_by_resource)
    )
    for resource in all_resources:
        counts = by_resource.get(resource, blank_counts())
        resources.append(
            {
                "resource": resource,
                "upload_count": uploads_by_resource.get(resource, 0),
                **counts,
                "mapping_count": mappings_by_resource.get(resource, 0),
            }
        )

    last_summary = dict(run.last_dry_run_summary or {})
    last_resource = last_summary.get("resource")
    if run.last_dry_run_fingerprint:
        dry_run_state = "CURRENT"
    elif uploads or rows or mappings:
        # Durable migration evidence without a current fingerprint means either
        # no dry run has been performed yet or a prior preview was invalidated.
        # Do not trust the mutable run status alone to distinguish those cases.
        dry_run_state = "NONE_OR_STALE"
    else:
        dry_run_state = "NONE"

    response.headers["Cache-Control"] = "no-store"
    return AppFolioMigrationReviewSummaryOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        upload_count=len(uploads),
        mapping_count=len(mappings),
        dry_run_state=dry_run_state,
        last_dry_run_resource=(str(last_resource) if last_resource else None),
        last_dry_run_fingerprint=run.last_dry_run_fingerprint,
        resources=resources,
        **totals,
    )


def _apply_correction_rule_to_staged_rows(
    db: Session,
    *,
    run: PlatformMigrationRun,
    rule: PlatformMigrationCorrectionRule,
    platform_user_id: int,
    prior_corrected_value: str | None = None,
) -> int:
    rows = (
        db.query(PlatformMigrationStagedRow)
        .filter(
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.organization_id == run.organization_id,
            PlatformMigrationStagedRow.provider == "APPFOLIO",
            PlatformMigrationStagedRow.resource == rule.resource,
        )
        .order_by(PlatformMigrationStagedRow.id.asc())
        .all()
    )
    applied = 0
    applied_at = datetime.utcnow()
    for row in rows:
        if row.disposition == "INVALID" or row.errors:
            continue
        data = dict(row.normalized_data or {})
        current = data.get(rule.field_name)
        if current is None:
            continue

        current_text = str(current).strip()
        evidence = list(row.correction_evidence or [])
        exact_source_match = current_text == rule.source_value
        prior_rule_match = False
        if (
            not exact_source_match
            and prior_corrected_value is not None
            and current_text == prior_corrected_value
        ):
            field_evidence = [
                item
                for item in evidence
                if item.get("field_name") == rule.field_name
            ]
            last_evidence = field_evidence[-1] if field_evidence else None
            prior_rule_match = bool(
                last_evidence
                and last_evidence.get("kind") == "RUN_CORRECTION_RULE"
                and last_evidence.get("rule_id") == rule.id
                and last_evidence.get("source_value") == rule.source_value
                and last_evidence.get("corrected_value") == prior_corrected_value
            )

        if not exact_source_match and not prior_rule_match:
            continue
        if current_text == rule.corrected_value:
            continue

        data[rule.field_name] = rule.corrected_value
        evidence.append(
            {
                "kind": "RUN_CORRECTION_RULE",
                "rule_id": rule.id,
                "field_name": rule.field_name,
                "source_value": rule.source_value,
                "corrected_value": rule.corrected_value,
                "platform_user_id": platform_user_id,
                "applied_at": applied_at.isoformat(),
            }
        )
        row.normalized_data = data
        row.correction_evidence = evidence
        append_audit_log(
            db,
            platform_user_id=platform_user_id,
            organization_id=run.organization_id,
            entity_type="platform_migration_staged_row",
            entity_id=row.id,
            action="appfolio_correction_rule_applied",
            old_value={
                "rule_id": rule.id,
                "field_name": rule.field_name,
                "value": current,
            },
            new_value={
                "rule_id": rule.id,
                "field_name": rule.field_name,
                "value": rule.corrected_value,
                "source_file_rewritten": False,
                "customer_target_mutation": False,
                "accounting_mutation": False,
            },
        )
        applied += 1

    if applied:
        run.last_dry_run_fingerprint = None
        run.last_dry_run_summary = None
        run.status = "STAGED"
    return applied


@router.get(
    "/runs/{run_id}/correction-rules",
    response_model=list[AppFolioMigrationCorrectionRuleOut],
)
def list_appfolio_correction_rules(
    run_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=False)
    rules = (
        db.query(PlatformMigrationCorrectionRule)
        .filter(
            PlatformMigrationCorrectionRule.run_id == run.id,
            PlatformMigrationCorrectionRule.organization_id == run.organization_id,
            PlatformMigrationCorrectionRule.provider == "APPFOLIO",
        )
        .order_by(
            PlatformMigrationCorrectionRule.resource.asc(),
            PlatformMigrationCorrectionRule.field_name.asc(),
            PlatformMigrationCorrectionRule.source_value.asc(),
            PlatformMigrationCorrectionRule.id.asc(),
        )
        .all()
    )
    response.headers["Cache-Control"] = "no-store"
    return [
        AppFolioMigrationCorrectionRuleOut.model_validate(rule).model_copy(
            update={"replayed": False, "applied_row_count": 0}
        )
        for rule in rules
    ]


@router.post(
    "/runs/{run_id}/uploads/{upload_id}/rows/{staged_row_id}/correction-rule",
    response_model=AppFolioMigrationCorrectionRuleOut,
    status_code=status.HTTP_201_CREATED,
)
def create_appfolio_correction_rule(
    run_id: int,
    upload_id: int,
    staged_row_id: int,
    payload: AppFolioMigrationCorrectionRuleCreateIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    upload = _upload(db, run=run, upload_id=upload_id)
    row = _staged_row(
        db,
        run=run,
        upload=upload,
        staged_row_id=staged_row_id,
    )
    if row.disposition == "INVALID" or row.errors:
        raise HTTPException(
            status_code=409,
            detail="Invalid staged rows cannot seed reusable correction rules.",
        )

    allowed = _MIGRATION_CORRECTABLE_FIELDS.get(row.resource, set())
    if payload.field_name not in allowed:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Field {payload.field_name!r} is not an approved descriptive "
                f"correction field for {row.resource}."
            ),
        )

    data = dict(row.normalized_data or {})
    if payload.field_name not in data or data.get(payload.field_name) is None:
        raise HTTPException(
            status_code=409,
            detail="Correction-rule source field is not present in the staged row.",
        )
    source_value = str(data[payload.field_name]).strip()
    corrected_value = payload.corrected_value.strip()
    if not source_value:
        raise HTTPException(
            status_code=409,
            detail="Blank source values cannot seed reusable correction rules.",
        )
    if not corrected_value:
        raise HTTPException(
            status_code=422,
            detail="Corrected value must contain non-whitespace text.",
        )
    if source_value == corrected_value:
        raise HTTPException(
            status_code=422,
            detail="Correction rule must change the exact source value.",
        )

    prior = (
        db.query(PlatformMigrationCorrectionRule)
        .filter(
            PlatformMigrationCorrectionRule.run_id == run.id,
            PlatformMigrationCorrectionRule.organization_id == run.organization_id,
            PlatformMigrationCorrectionRule.provider == "APPFOLIO",
            PlatformMigrationCorrectionRule.resource == row.resource,
            PlatformMigrationCorrectionRule.field_name == payload.field_name,
            PlatformMigrationCorrectionRule.source_value == source_value,
        )
        .first()
    )
    replayed = prior is not None
    if prior is not None and prior.corrected_value != corrected_value:
        raise HTTPException(
            status_code=409,
            detail=(
                "A different correction already exists for this exact run/resource/"
                "field/source value. Use the explicit correction-rule update path."
            ),
        )

    rule = prior
    if rule is None:
        rule = PlatformMigrationCorrectionRule(
            run_id=run.id,
            organization_id=run.organization_id,
            provider="APPFOLIO",
            resource=row.resource,
            field_name=payload.field_name,
            source_value=source_value,
            corrected_value=corrected_value,
            created_by_platform_user_id=current_user.id,
        )
        db.add(rule)
        db.flush()
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=run.organization_id,
            entity_type="platform_migration_correction_rule",
            entity_id=rule.id,
            action="appfolio_correction_rule_created",
            new_value={
                "resource": rule.resource,
                "field_name": rule.field_name,
                "source_value": rule.source_value,
                "corrected_value": rule.corrected_value,
                "run_scoped": True,
                "fuzzy_matching": False,
                "customer_target_mutation": False,
                "accounting_mutation": False,
            },
        )

    applied = _apply_correction_rule_to_staged_rows(
        db,
        run=run,
        rule=rule,
        platform_user_id=current_user.id,
    )
    db.commit()
    db.refresh(rule)
    return AppFolioMigrationCorrectionRuleOut.model_validate(rule).model_copy(
        update={"replayed": replayed, "applied_row_count": applied}
    )


@router.put(
    "/runs/{run_id}/correction-rules/{rule_id}",
    response_model=AppFolioMigrationCorrectionRuleOut,
)
def update_appfolio_correction_rule(
    run_id: int,
    rule_id: int,
    payload: AppFolioMigrationCorrectionRuleUpdateIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    rule = (
        db.query(PlatformMigrationCorrectionRule)
        .filter(
            PlatformMigrationCorrectionRule.id == rule_id,
            PlatformMigrationCorrectionRule.run_id == run.id,
            PlatformMigrationCorrectionRule.organization_id == run.organization_id,
            PlatformMigrationCorrectionRule.provider == "APPFOLIO",
        )
        .first()
    )
    if rule is None:
        raise HTTPException(status_code=404, detail="Correction rule not found.")

    corrected_value = payload.corrected_value.strip()
    if not corrected_value:
        raise HTTPException(
            status_code=422,
            detail="Corrected value must contain non-whitespace text.",
        )
    if corrected_value == rule.source_value:
        raise HTTPException(
            status_code=422,
            detail="Correction rule must change the exact source value.",
        )
    if corrected_value == rule.corrected_value:
        return AppFolioMigrationCorrectionRuleOut.model_validate(rule).model_copy(
            update={"replayed": True, "applied_row_count": 0}
        )

    previous_corrected_value = rule.corrected_value
    rule.corrected_value = corrected_value
    applied = _apply_correction_rule_to_staged_rows(
        db,
        run=run,
        rule=rule,
        platform_user_id=current_user.id,
        prior_corrected_value=previous_corrected_value,
    )
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    run.status = "STAGED"
    append_audit_log(
        db,
        platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_correction_rule",
        entity_id=rule.id,
        action="appfolio_correction_rule_updated",
        old_value={
            "resource": rule.resource,
            "field_name": rule.field_name,
            "source_value": rule.source_value,
            "corrected_value": previous_corrected_value,
        },
        new_value={
            "resource": rule.resource,
            "field_name": rule.field_name,
            "source_value": rule.source_value,
            "corrected_value": rule.corrected_value,
            "run_scoped": True,
            "fuzzy_matching": False,
            "dry_run_invalidated": True,
            "customer_target_mutation": False,
            "accounting_mutation": False,
        },
    )
    db.commit()
    db.refresh(rule)
    return AppFolioMigrationCorrectionRuleOut.model_validate(rule).model_copy(
        update={"replayed": False, "applied_row_count": applied}
    )


@router.get(
    "/runs/{run_id}/uploads/{upload_id}/rows",
    response_model=list[AppFolioMigrationStagedRowOut],
)
def list_appfolio_staged_rows(
    run_id: int,
    upload_id: int,
    response: Response,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=False)
    upload = _upload(db, run=run, upload_id=upload_id)
    rows = (
        db.query(PlatformMigrationStagedRow)
        .filter(
            PlatformMigrationStagedRow.upload_id == upload.id,
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.organization_id == run.organization_id,
            PlatformMigrationStagedRow.provider == "APPFOLIO",
        )
        .order_by(PlatformMigrationStagedRow.row_number.asc(), PlatformMigrationStagedRow.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    response.headers["Cache-Control"] = "no-store"
    return rows
