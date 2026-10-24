"""Phase 4.17: DoorLoop provider migration discovery; no import writes."""
import hashlib
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from app.schemas.doorloop_migration import DoorLoopRunCreateIn, DoorLoopRunOut
from app.services.audit import append_audit_log
from app.services.rentmanager_source_preview import assess_source_rows
from app.services.appfolio_file_ingestion import (
    MAX_FILE_BYTES, AppFolioFileIngestionError, _parse_file, _safe_filename,
)
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.platform_migration import PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.user import Organization
from app.routers.platform_auth import get_current_platform_user

router = APIRouter(prefix="/api/platform/migrations/doorloop", tags=["Platform DoorLoop Migration"])
_ALLOWED = {
    PlatformUserRole.PLATFORM_ADMIN, PlatformUserRole.PLATFORM_TECH,
    PlatformUserRole.PLATFORM_SUPPORT, PlatformUserRole.PLATFORM_DEV,
}


def _authorize(user: PlatformUser) -> None:
    if user.role not in _ALLOWED:
        raise HTTPException(status_code=403, detail="Platform migration access required.")


@router.get("/resource-readiness")
def doorloop_resource_readiness(
    response: Response,
    user: PlatformUser = Depends(get_current_platform_user),
):
    _authorize(user)
    response.headers["Cache-Control"] = "no-store"
    return {
        "provider": "DOORLOOP",
        "source_contract_verified": False,
        "official_api_enabled": False,
        "file_staging_enabled": False,
        "source_inspection_enabled": True,
        "controlled_commit_enabled": False,
        "customer_business_mutation": False,
        "blocker": "DoorLoop resource contracts and customer authorization must be reviewed before migration imports.",
    }


@router.get("/runs", response_model=list[DoorLoopRunOut])
def list_doorloop_runs(
    response: Response,
    organization_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    user: PlatformUser = Depends(get_current_platform_user),
):
    _authorize(user)
    query = db.query(PlatformMigrationRun).join(
        Organization, Organization.id == PlatformMigrationRun.organization_id,
    ).filter(
        PlatformMigrationRun.provider == "DOORLOOP",
        Organization.is_active.is_(True),
    )
    if organization_id is not None:
        org = db.query(Organization).filter(
            Organization.id == organization_id, Organization.is_active.is_(True),
        ).first()
        if org is None:
            raise HTTPException(status_code=404, detail="Target organization not found.")
        query = query.filter(PlatformMigrationRun.organization_id == organization_id)
    response.headers["Cache-Control"] = "no-store"
    return query.order_by(
        PlatformMigrationRun.created_at.desc(), PlatformMigrationRun.id.desc(),
    ).limit(limit).all()


@router.post("/runs", response_model=DoorLoopRunOut, status_code=status.HTTP_201_CREATED)
def create_doorloop_run(
    payload: DoorLoopRunCreateIn,
    db: Session = Depends(get_db),
    user: PlatformUser = Depends(get_current_platform_user),
):
    if user.role not in {PlatformUserRole.PLATFORM_ADMIN, PlatformUserRole.PLATFORM_TECH, PlatformUserRole.PLATFORM_DEV}:
        raise HTTPException(status_code=403, detail="Migration creation requires platform write access.")
    org = db.query(Organization).filter(
        Organization.id == payload.organization_id, Organization.is_active.is_(True),
    ).first()
    if org is None:
        raise HTTPException(status_code=404, detail="Target organization not found.")
    run = PlatformMigrationRun(
        organization_id=org.id, provider="DOORLOOP", source_account_ref=payload.source_account_ref,
        status="DRAFT", created_by_platform_user_id=user.id,
    )
    db.add(run)
    db.flush()
    append_audit_log(
        db, platform_user_id=user.id, organization_id=org.id,
        entity_type="platform_migration_run", entity_id=run.id,
        action="doorloop_migration_run_created",
        new_value={"provider": "DOORLOOP", "status": "DRAFT",
                   "credentials_stored": False, "customer_business_mutation": False},
    )
    db.commit()
    db.refresh(run)
    return run


@router.get("/runs/{run_id}", response_model=DoorLoopRunOut)
def get_doorloop_run(
    run_id: int,
    response: Response,
    db: Session = Depends(get_db),
    user: PlatformUser = Depends(get_current_platform_user),
):
    _authorize(user)
    run = db.query(PlatformMigrationRun).join(
        Organization, Organization.id == PlatformMigrationRun.organization_id,
    ).filter(
        PlatformMigrationRun.id == run_id,
        PlatformMigrationRun.provider == "DOORLOOP",
        Organization.is_active.is_(True),
    ).first()
    if run is None:
        raise HTTPException(status_code=404, detail="DoorLoop migration run not found.")
    response.headers["Cache-Control"] = "no-store"
    return run


@router.get("/runs/{run_id}/source-readiness")
def doorloop_run_source_readiness(
    run_id: int,
    response: Response,
    db: Session = Depends(get_db),
    user: PlatformUser = Depends(get_current_platform_user),
):
    """Run-scoped review of the unverified source contract, without customer writes."""
    run = get_doorloop_run(run_id, response, db, user)
    return {
        "run_id": run.id,
        "provider": "DOORLOOP",
        "source_account_bound": bool(run.source_account_ref),
        "source_inspection_enabled": True,
        "source_contract_verified": False,
        "official_api_enabled": False,
        "file_staging_enabled": False,
        "controlled_commit_enabled": False,
        "customer_business_mutation": False,
        "blocker": "Approved DoorLoop source exports, relationships and accounting semantics are required before staging or importing.",
    }


@router.post("/runs/{run_id}/inspect-source")
async def inspect_doorloop_source_headers(
    run_id: int,
    response: Response,
    file: UploadFile = File(...),
    sheet_name: str | None = Form(default=None),
    db: Session = Depends(get_db),
    user: PlatformUser = Depends(get_current_platform_user),
):
    """Bounded, nonpersistent CSV/XLSX inventory. No field mapping or source-row exposure."""
    if user.role not in {
        PlatformUserRole.PLATFORM_ADMIN, PlatformUserRole.PLATFORM_TECH,
        PlatformUserRole.PLATFORM_DEV,
    }:
        raise HTTPException(status_code=403, detail="Migration source inspection requires platform write access.")
    run = get_doorloop_run(run_id, response, db, user)
    try:
        filename = _safe_filename(file.filename or "")
        raw = await file.read(MAX_FILE_BYTES + 1)
        parsed = _parse_file(filename, raw, sheet_name)
    except AppFolioFileIngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "run_id": run.id,
        "provider": "DOORLOOP",
        "file_format": parsed.file_format,
        "sheet_name": parsed.sheet_name,
        "source_file_sha256": hashlib.sha256(raw).hexdigest(),
        "source_file_bytes": len(raw),
        "headers": parsed.headers,
        "column_inventory": [
            {"index": i, "source_header": header, "mapping_status": "UNMAPPED"}
            for i, header in enumerate(parsed.headers)
        ],
        "row_count": len(parsed.rows),
        "headers_validated_unique": True,
        "suggested_target_fields": [],
        "source_contract_verified": False,
        "explicit_mapping_required": True,
        "can_stage_import": False,
        "can_commit_import": False,
        "source_rows_returned": False,
        "raw_source_stored": False,
        "staging_mutation": False,
        "customer_business_mutation": False,
    }


@router.post("/runs/{run_id}/preview-source-quality")
async def preview_doorloop_source_quality(
    run_id: int,
    response: Response,
    file: UploadFile = File(...),
    sheet_name: str | None = Form(default=None),
    column_mapping_json: str = Form(...),
    expected_source_sha256: str = Form(...),
    identity_field: str | None = Form(default=None),
    db: Session = Depends(get_db),
    user: PlatformUser = Depends(get_current_platform_user),
):
    """Read-only quality diagnostics bound to exactly the staff-inspected export."""
    if user.role not in {
        PlatformUserRole.PLATFORM_ADMIN, PlatformUserRole.PLATFORM_TECH,
        PlatformUserRole.PLATFORM_DEV,
    }:
        raise HTTPException(status_code=403, detail="Migration source review requires platform write access.")
    run = get_doorloop_run(run_id, response, db, user)
    if len(column_mapping_json) > 32768:
        raise HTTPException(status_code=422, detail="Source mapping proposal is too large.")
    try:
        mapping = json.loads(column_mapping_json)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="Invalid column mapping JSON.") from exc
    if not isinstance(mapping, dict) or not mapping or len(mapping) > 100:
        raise HTTPException(status_code=422, detail="At least one bounded source mapping is required.")
    if any(
        not isinstance(key, str) or not isinstance(value, str)
        or not key.strip() or len(key) > 100 or not value.strip() or len(value) > 255
        for key, value in mapping.items()
    ):
        raise HTTPException(status_code=422, detail="Proposed source mapping fields must be bounded strings.")
    if any(
        token in key.casefold()
        for key in mapping for token in ("password", "secret", "token", "cookie", "apikey", "api_key", "authorization")
    ):
        raise HTTPException(status_code=422, detail="Credential fields cannot be proposed in source mappings.")
    if len(set(mapping.values())) != len(mapping):
        raise HTTPException(status_code=422, detail="Each export column may be mapped only once.")
    if identity_field is not None and (len(identity_field) > 100 or identity_field not in mapping):
        raise HTTPException(status_code=422, detail="Identity field must be an explicitly proposed mapping key.")
    try:
        filename = _safe_filename(file.filename or "")
        contents = await file.read(MAX_FILE_BYTES + 1)
        parsed = _parse_file(filename, contents, sheet_name)
    except AppFolioFileIngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    digest = hashlib.sha256(contents).hexdigest()
    if (
        len(expected_source_sha256) != 64
        or any(ch not in "0123456789abcdef" for ch in expected_source_sha256)
        or expected_source_sha256 != digest
    ):
        raise HTTPException(status_code=409, detail="Source file differs from the inspected export.")
    if any(header not in parsed.headers for header in mapping.values()):
        raise HTTPException(status_code=422, detail="Proposed source column not found in inspected export.")
    result = assess_source_rows(parsed.rows, mapping, identity_field)
    return {
        "run_id": run.id,
        "provider": "DOORLOOP",
        "source_file_sha256": digest,
        "mapping_stored": False,
        **result,
    }
