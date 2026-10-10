"""Phase 4.15 Yardi migration-run foundation.

This bounded foundation creates provider-labelled YARDI migration runs only.
It does not implement outbound Yardi API transport or mutate customer business data.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
import json
import hashlib
from pathlib import Path

from fastapi import File, Form, UploadFile
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from app.models.platform_migration import PlatformMigrationUpload, PlatformMigrationStagedRow
from app.schemas.platform_migration import AppFolioMigrationUploadOut, AppFolioMigrationStagedRowOut
from app.services.appfolio_file_ingestion import MAX_FILE_BYTES, AppFolioFileIngestionError
from app.services.yardi_file_ingestion import stage_yardi_file

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.platform_migration import PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.user import Organization
from app.routers.platform_auth import get_current_platform_user
from app.schemas.yardi_migration import YardiMigrationRunCreateIn, YardiMigrationRunOut
from app.services.audit import append_audit_log


router = APIRouter(
    prefix="/api/platform/migrations/yardi",
    tags=["Platform Yardi Migration"],
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
            PlatformMigrationRun.provider == "YARDI",
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Yardi migration run not found.")
    _target_org(db, row.organization_id)
    return row


@router.get("/runs", response_model=list[YardiMigrationRunOut])
def list_yardi_runs(
    response: Response,
    organization_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    _require_role(current_user, _VIEW_ROLES, "Platform migration access required.")
    query = db.query(PlatformMigrationRun).filter(
        PlatformMigrationRun.provider == "YARDI"
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


@router.get("/runs/{run_id}", response_model=YardiMigrationRunOut)
def get_yardi_run(
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
    response_model=YardiMigrationRunOut,
    status_code=status.HTTP_201_CREATED,
)
def create_yardi_run(
    payload: YardiMigrationRunCreateIn,
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
        provider="YARDI",
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
        action="yardi_migration_run_created",
        new_value={
            "provider": "YARDI",
            "status": row.status,
            "source_account_bound": True,
            "credentials_stored": False,
            "raw_provider_payload_stored": False,
            "customer_business_mutation": False,
            "accounting_mutation": False,
        },
    )
    db.commit()
    db.refresh(row)
    return row


@router.post(
    "/runs/{run_id}/uploads",
    response_model=AppFolioMigrationUploadOut,
    status_code=status.HTTP_201_CREATED,
)
async def stage_yardi_upload(
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
    try:
        mapping = json.loads(column_mapping_json) if column_mapping_json else None
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Invalid column mapping JSON.") from exc
    content = await file.read(MAX_FILE_BYTES + 1)
    try:
        result = stage_yardi_file(
            db, run=run, filename=filename, content=content,
            resource_override=resource, sheet_name=sheet_name,
            explicit_mapping=mapping, platform_user_id=current_user.id,
        )
        if not result.replayed:
            append_audit_log(
                db, platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run", entity_id=run.id,
                action="yardi_file_staged",
                new_value={
                    "upload_id": result.upload.id,
                    "provider": "YARDI",
                    "resource": result.upload.detected_resource,
                    "row_count": result.upload.row_count,
                    "normalized_fingerprint": result.upload.normalized_fingerprint,
                    "raw_file_stored": False, "target_mutation": False,
                },
            )
            db.commit()
            db.refresh(result.upload)
    except AppFolioFileIngestionError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Upload replay conflicted.") from exc
    return AppFolioMigrationUploadOut.model_validate(result.upload).model_copy(
        update={"replayed": result.replayed}
    )


@router.get("/runs/{run_id}/uploads", response_model=list[AppFolioMigrationUploadOut])
def list_yardi_uploads(
    run_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=False)
    response.headers["Cache-Control"] = "no-store"
    return (
        db.query(PlatformMigrationUpload)
        .filter(
            PlatformMigrationUpload.run_id == run.id,
            PlatformMigrationUpload.organization_id == run.organization_id,
            PlatformMigrationUpload.provider == "YARDI",
        )
        .order_by(PlatformMigrationUpload.id.desc()).all()
    )


@router.get("/runs/{run_id}/uploads/{upload_id}/rows", response_model=list[AppFolioMigrationStagedRowOut])
def list_yardi_staged_rows(
    run_id: int,
    upload_id: int,
    response: Response,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=False)
    upload = db.query(PlatformMigrationUpload).filter(
        PlatformMigrationUpload.id == upload_id,
        PlatformMigrationUpload.run_id == run.id,
        PlatformMigrationUpload.organization_id == run.organization_id,
        PlatformMigrationUpload.provider == "YARDI",
    ).first()
    if upload is None:
        raise HTTPException(status_code=404, detail="Yardi upload not found.")
    rows = db.query(PlatformMigrationStagedRow).filter(
        PlatformMigrationStagedRow.upload_id == upload.id,
        PlatformMigrationStagedRow.run_id == run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
    ).order_by(
        PlatformMigrationStagedRow.row_number.asc(),
        PlatformMigrationStagedRow.id.asc(),
    ).offset(offset).limit(limit).all()
    response.headers["Cache-Control"] = "no-store"
    return rows


@router.get("/resource-readiness")
def yardi_resource_readiness(
    response: Response,
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Expose source-contract readiness without treating staged data as imported."""
    _require_role(current_user, _VIEW_ROLES, "Platform migration access required.")
    response.headers["Cache-Control"] = "no-store"
    return {
        "provider": "YARDI",
        "supported_staging_only": [
            "PROPERTIES", "UNITS", "OWNERS", "VENDORS",
            "TENANTS", "LEASE_OCCUPANCY",
        ],
        "blocked_pending_source_contract": [
            "GL_ACCOUNTS", "OPEN_RECEIVABLES", "LEASE_CHARGES",
            "OPEN_PAYABLES", "BANK_ACCOUNTS", "CURRENT_YEAR_BUDGETS",
            "OUTSTANDING_CHECKS", "TRIAL_BALANCE", "GENERAL_LEDGER",
        ],
        "customer_records_created_by_upload": False,
        "financial_posting_enabled": False,
        "official_api_adapter_enabled": False,
    }


@router.get("/runs/{run_id}/staging-preview")
def preview_yardi_staging(
    run_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Read-only, provider-scoped inventory; never authorizes a commit."""
    run = _run(db, run_id=run_id, current_user=current_user, write=False)
    uploads = db.query(PlatformMigrationUpload).filter(
        PlatformMigrationUpload.run_id == run.id,
        PlatformMigrationUpload.organization_id == run.organization_id,
        PlatformMigrationUpload.provider == "YARDI",
    ).order_by(PlatformMigrationUpload.id.asc()).all()
    counts = db.query(
        PlatformMigrationStagedRow.resource,
        PlatformMigrationStagedRow.disposition,
        func.count(PlatformMigrationStagedRow.id),
    ).filter(
        PlatformMigrationStagedRow.run_id == run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
    ).group_by(
        PlatformMigrationStagedRow.resource,
        PlatformMigrationStagedRow.disposition,
    ).all()
    resources: dict[str, dict[str, int]] = {}
    for resource, disposition, count in counts:
        resources.setdefault(resource, {})[disposition] = count
    fingerprint_input = json.dumps(
        [(upload.id, upload.normalized_fingerprint) for upload in uploads],
        separators=(",", ":"),
    )
    preview_fingerprint = hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()
    response.headers["Cache-Control"] = "no-store"
    return {
        "run_id": run.id,
        "provider": "YARDI",
        "upload_count": len(uploads),
        "staged_row_count": sum(count for _, _, count in counts),
        "dispositions_by_resource": resources,
        "preview_fingerprint": preview_fingerprint,
        "reconciliation_authorized": False,
        "controlled_commit_enabled": False,
        "customer_business_mutation": False,
    }
