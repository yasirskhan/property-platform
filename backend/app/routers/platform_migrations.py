"""Platform-run AppFolio migration foundation.

This phase intentionally has no outbound AppFolio transport yet. The public
AppFolio API surface is known, but customer-specific credentials/provider
authorization are not stored or guessed here. Platform staff can establish a
target run and dry-run Property records supplied by a future verified adapter.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.platform_migration import (
    PlatformMigrationItem,
    PlatformMigrationRun,
    PlatformMigrationStagedRow,
    PlatformMigrationUpload,
)
from app.models.property import Property
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.user import Organization
from app.routers.platform_auth import get_current_platform_user
from app.schemas.platform_migration import (
    AppFolioMigrationRunCreateIn,
    AppFolioMigrationItemOut,
    AppFolioMigrationRunOut,
    AppFolioMigrationStagedRowOut,
    AppFolioMigrationUploadOut,
    AppFolioPropertyCommitIn,
    AppFolioPropertyCommitOut,
    AppFolioPropertyDryRunIn,
    AppFolioPropertyDryRunOut,
)
from app.services.appfolio_migration import (
    AppFolioMigrationError,
    commit_properties,
    dry_run_properties,
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


def _staged_property_records(
    db: Session,
    *,
    run: PlatformMigrationRun,
    upload: PlatformMigrationUpload,
) -> list[dict[str, object]]:
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

    blocking = [
        row
        for row in rows
        if row.disposition in {"INVALID", "POSSIBLE_MATCH", "REVIEW"}
    ]
    if blocking:
        counts: dict[str, int] = {}
        for row in blocking:
            counts[row.disposition] = counts.get(row.disposition, 0) + 1
        detail = ", ".join(
            f"{key}={counts[key]}" for key in sorted(counts)
        )
        raise HTTPException(
            status_code=409,
            detail=(
                "Staged property dry run is blocked by unresolved rows: "
                f"{detail}. Resolve staged validation/match decisions before continuing."
            ),
        )

    records: list[dict[str, object]] = []
    for row in rows:
        data = dict(row.normalized_data or {})
        records.append(
            {
                "Id": row.source_id or data.get("source_id"),
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
    return records


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
    records = _staged_property_records(db, run=run, upload=upload)
    result = dry_run_properties(
        db,
        run=run,
        include_hidden=False,
        records=records,
        source_context_fingerprint=upload.normalized_fingerprint,
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
                "source_context_fingerprint": upload.normalized_fingerprint,
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
                },
            )
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
