"""Phase 4.16: RentManager provider-labelled migration-run foundation only.

No outbound API calls, customer record creation, accounting or source ingestion.
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session
from app.services.appfolio_file_ingestion import MAX_FILE_BYTES, AppFolioFileIngestionError, _parse_file, _safe_filename

from app.core.database import get_db
from app.models.platform_migration import PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.user import Organization
from app.routers.platform_auth import get_current_platform_user
from app.schemas.rentmanager_migration import RentManagerRunCreateIn, RentManagerRunOut
from app.services.audit import append_audit_log


router = APIRouter(prefix="/api/platform/migrations/rentmanager", tags=["Platform RentManager Migration"])
_VIEW_ROLES = {
    PlatformUserRole.PLATFORM_ADMIN, PlatformUserRole.PLATFORM_TECH,
    PlatformUserRole.PLATFORM_SUPPORT, PlatformUserRole.PLATFORM_DEV,
}
_WRITE_ROLES = {
    PlatformUserRole.PLATFORM_ADMIN, PlatformUserRole.PLATFORM_TECH,
    PlatformUserRole.PLATFORM_DEV,
}


def _role(user: PlatformUser, *, write: bool) -> None:
    if user.role not in (_WRITE_ROLES if write else _VIEW_ROLES):
        raise HTTPException(status_code=403, detail="Platform migration access required.")


def _organization(db: Session, organization_id: int) -> Organization:
    org = db.query(Organization).filter(
        Organization.id == organization_id, Organization.is_active.is_(True),
    ).first()
    if org is None:
        raise HTTPException(status_code=404, detail="Target organization not found.")
    return org


@router.get("/runs", response_model=list[RentManagerRunOut])
def list_rentmanager_runs(
    response: Response,
    organization_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    _role(current_user, write=False)
    query = db.query(PlatformMigrationRun).join(
        Organization, Organization.id == PlatformMigrationRun.organization_id,
    ).filter(
        PlatformMigrationRun.provider == "RENTMANAGER",
        Organization.is_active.is_(True),
    )
    if organization_id is not None:
        _organization(db, organization_id)
        query = query.filter(PlatformMigrationRun.organization_id == organization_id)
    response.headers["Cache-Control"] = "no-store"
    return query.order_by(PlatformMigrationRun.created_at.desc(), PlatformMigrationRun.id.desc()).limit(limit).all()


@router.get("/runs/{run_id}", response_model=RentManagerRunOut)
def get_rentmanager_run(
    run_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    _role(current_user, write=False)
    row = db.query(PlatformMigrationRun).filter(
        PlatformMigrationRun.id == run_id,
        PlatformMigrationRun.provider == "RENTMANAGER",
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="RentManager migration run not found.")
    _organization(db, row.organization_id)
    response.headers["Cache-Control"] = "no-store"
    return row


@router.get("/runs/{run_id}/source-readiness")
def rentmanager_run_source_readiness(
    run_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Read-only run-specific source gate; never authorize an import by inference."""
    run = get_rentmanager_run(run_id, response, db, current_user)
    return {
        "run_id": run.id,
        "provider": "RENTMANAGER",
        "source_account_bound": bool(run.source_account_ref),
        "source_inspection_enabled": True,
        "file_upload_enabled": False,
        "official_api_enabled": False,
        "controlled_commit_enabled": False,
        "customer_business_mutation": False,
        "blocker": "No independently verified RentManager export or API source contract.",
    }


@router.post("/runs/{run_id}/inspect-source")
async def inspect_rentmanager_source_headers(
    run_id: int,
    response: Response,
    file: UploadFile = File(...),
    sheet_name: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Bounded, nonpersistent CSV/XLSX header discovery; NOT an import contract."""
    _role(current_user, write=True)
    run = db.query(PlatformMigrationRun).filter(
        PlatformMigrationRun.id == run_id,
        PlatformMigrationRun.provider == "RENTMANAGER",
    ).first()
    if run is None:
        raise HTTPException(status_code=404, detail="RentManager migration run not found.")
    _organization(db, run.organization_id)
    try:
        filename = _safe_filename(file.filename or "")
        contents = await file.read(MAX_FILE_BYTES + 1)
        parsed = _parse_file(filename, contents, sheet_name)
    except AppFolioFileIngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response.headers["Cache-Control"] = "no-store"
    return {
        "run_id": run.id,
        "provider": "RENTMANAGER",
        "file_format": parsed.file_format,
        "sheet_name": parsed.sheet_name,
        "headers": parsed.headers,
        "column_inventory": [
            {"index": index, "source_header": header, "mapping_status": "UNMAPPED"}
            for index, header in enumerate(parsed.headers)
        ],
        "suggested_target_fields": [],
        "row_count": len(parsed.rows),
        "source_contract_verified": False,
        "source_rows_returned": False,
        "raw_source_stored": False,
        "staging_mutation": False,
        "customer_business_mutation": False,
    }


@router.post("/runs", response_model=RentManagerRunOut, status_code=status.HTTP_201_CREATED)
def create_rentmanager_run(
    payload: RentManagerRunCreateIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    _role(current_user, write=True)
    org = _organization(db, payload.organization_id)
    row = PlatformMigrationRun(
        organization_id=org.id, provider="RENTMANAGER",
        source_account_ref=payload.source_account_ref,
        status="DRAFT", created_by_platform_user_id=current_user.id,
    )
    db.add(row)
    db.flush()
    append_audit_log(
        db, platform_user_id=current_user.id,
        organization_id=org.id,
        entity_type="platform_migration_run", entity_id=row.id,
        action="rentmanager_migration_run_created",
        new_value={
            "provider": "RENTMANAGER", "status": row.status,
            "source_account_bound": True, "credentials_stored": False,
            "raw_provider_payload_stored": False,
            "customer_business_mutation": False, "accounting_mutation": False,
        },
    )
    db.commit()
    db.refresh(row)
    return row


@router.get("/resource-readiness")
def get_rentmanager_resource_readiness(
    response: Response,
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Explicitly block unverified RentManager export/API contracts."""
    _role(current_user, write=False)
    response.headers["Cache-Control"] = "no-store"
    return {
        "provider": "RENTMANAGER",
        "run_foundation_available": True,
        "source_inspection_enabled": True,
        "file_upload_enabled": False,
        "official_api_enabled": False,
        "controlled_commit_enabled": False,
        "customer_business_mutation": False,
        "reason": "Authoritative RentManager source file and API contracts are not verified.",
    }
