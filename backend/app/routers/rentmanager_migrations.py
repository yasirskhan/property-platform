"""Phase 4.16: RentManager provider-labelled migration-run foundation only.

No outbound API calls, customer record creation, accounting or source ingestion.
"""
import hashlib
from pydantic import BaseModel, ConfigDict, Field

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
        "blocker": "Official Rent Manager API documentation exists; customer authorization, edition, endpoint schemas and source-to-target import contract remain unverified.",
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
        "headers_validated_unique": True,
        "headers_require_review": False,
        "file_format": parsed.file_format,
        "source_file_sha256": hashlib.sha256(contents).hexdigest(),
        "source_file_bytes": len(contents),
        "sheet_name": parsed.sheet_name,
        "headers": parsed.headers,
        "column_inventory": [
            {"index": index, "source_header": header, "mapping_status": "UNMAPPED"}
            for index, header in enumerate(parsed.headers)
        ],
        "suggested_target_fields": [],
        "row_count": len(parsed.rows),
        "source_contract_verified": False,
        "explicit_mapping_required": True,
        "can_stage_import": False,
        "can_commit_import": False,
        "source_rows_returned": False,
        "raw_source_stored": False,
        "staging_mutation": False,
        "customer_business_mutation": False,
    }


class RentManagerMappingProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_headers: list[str] = Field(min_length=1, max_length=200)
    column_mapping: dict[str, str] = Field(default_factory=dict)


@router.post("/runs/{run_id}/review-mapping")
def review_rentmanager_mapping(
    run_id: int,
    payload: RentManagerMappingProposal,
    response: Response,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Review column mapping shape without storing or authorizing imports."""
    get_rentmanager_run(run_id, response, db, current_user)
    _role(current_user, write=True)
    headers = payload.source_headers
    if any(not value.strip() for value in headers) or len(set(headers)) != len(headers):
        raise HTTPException(status_code=422, detail="Source headers must be distinct and nonempty.")
    if any(len(value) > 255 for value in headers):
        raise HTTPException(status_code=422, detail="Source header exceeds allowed length.")
    if len(payload.column_mapping) > 200 or any(
        not field.strip() or len(field) > 100 or
        not source.strip() or len(source) > 255
        for field, source in payload.column_mapping.items()
    ):
        raise HTTPException(status_code=422, detail="Proposed mapping fields must be bounded and nonempty.")
    normalized_headers = [value.strip().casefold() for value in headers]
    if len(set(normalized_headers)) != len(normalized_headers):
        raise HTTPException(status_code=422, detail="Normalized source headers must be unique.")
    if any(
        any(key in field.casefold() for key in ("password", "secret", "token", "cookie", "apikey", "api_key"))
        for field in payload.column_mapping
    ):
        raise HTTPException(status_code=422, detail="Credential fields are not accepted in migration mapping.")
    forbidden_headers = ("password", "secret", "token", "cookie", "authorization", "bearer", "apikey", "api_key")
    if any(any(key in header.casefold() for key in forbidden_headers) for header in headers):
        raise HTTPException(status_code=422, detail="Credential or session source columns are not accepted.")
    if any(value not in headers for value in payload.column_mapping.values()):
        raise HTTPException(status_code=422, detail="Mapped column is missing from source headers.")
    if len(set(payload.column_mapping.values())) != len(payload.column_mapping):
        raise HTTPException(status_code=422, detail="Source columns may only map once.")
    response.headers["Cache-Control"] = "no-store"
    return {
        "run_id": run_id, "provider": "RENTMANAGER",
        "proposed_mapping": payload.column_mapping,
        "unmapped_headers": [h for h in headers if h not in payload.column_mapping.values()],
        "mapping_stored": False, "mapping_authorized": False,
        "can_stage_import": False, "can_commit_import": False,
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
        "reason": "Official Rent Manager API documentation exists; customer access and resource-level migration contracts are not verified.",
    }
