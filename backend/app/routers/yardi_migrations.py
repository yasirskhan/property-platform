"""Phase 4.15 Yardi migration-run foundation.

This bounded foundation creates provider-labelled YARDI migration runs only.
It does not implement outbound Yardi API transport or mutate customer business data.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
import json
import hashlib
from datetime import datetime
from typing import Literal
from pydantic import BaseModel
from pathlib import Path

from fastapi import File, Form, UploadFile
from sqlalchemy import case, func, or_
from sqlalchemy.exc import IntegrityError
from app.models.platform_migration import PlatformMigrationUpload, PlatformMigrationStagedRow, PlatformMigrationItem
from app.schemas.platform_migration import AppFolioMigrationUploadOut, AppFolioMigrationStagedRowOut
from app.services.appfolio_file_ingestion import (
    MAX_FILE_BYTES, AppFolioFileIngestionError, _parse_file, _safe_filename,
)
from app.services.yardi_file_ingestion import stage_yardi_file

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.platform_migration import PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.user import Organization
from app.models.property import Property, Unit
from app.models.vendor import Vendor
from app.models.user import User, UserRole
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


@router.post("/runs/{run_id}/inspect-source")
async def inspect_yardi_source_headers(
    run_id: int,
    file: UploadFile = File(...),
    sheet_name: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Inspect bounded source headers only: no staging, PII rows or customer writes."""
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        filename = _safe_filename(file.filename or "")
        contents = await file.read(MAX_FILE_BYTES + 1)
        parsed = _parse_file(filename, contents, sheet_name)
    except AppFolioFileIngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "run_id": run.id,
        "provider": "YARDI",
        "file_format": parsed.file_format,
        "sheet_name": parsed.sheet_name,
        "headers": parsed.headers,
        "row_count": len(parsed.rows),
        "source_rows_returned": False,
        "raw_source_stored": False,
        "staging_mutation": False,
        "customer_business_mutation": False,
    }


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
        # The historical supported_staging_only key describes upload semantics.
        # It is retained for existing consumers; these resources also support
        # explicitly reviewed, metadata-only existing-target identity bindings.
        "resource_capabilities": {
            "PROPERTIES": {"csv_xlsx_staging": True, "reviewed_existing_target_binding": True,
                           "customer_record_creation_enabled": False},
            "UNITS": {"csv_xlsx_staging": True, "reviewed_existing_target_binding": True,
                      "requires_same_run_parent_property": True,
                      "customer_record_creation_enabled": False},
            "OWNERS": {"csv_xlsx_staging": True, "reviewed_existing_target_binding": True,
                       "ownership_relationship_import_enabled": False,
                       "customer_record_creation_enabled": False},
            "VENDORS": {"csv_xlsx_staging": True, "reviewed_existing_target_binding": True,
                        "customer_record_creation_enabled": False},
            "TENANTS": {"csv_xlsx_staging": True, "reviewed_existing_target_binding": True,
                        "login_creation_enabled": False, "occupancy_import_enabled": False,
                        "customer_record_creation_enabled": False},
            "LEASE_OCCUPANCY": {"csv_xlsx_staging": True, "reviewed_existing_target_binding": False,
                                "read_only_identity_relationship_preview": True,
                                "lease_creation_enabled": False,
                                "customer_record_creation_enabled": False},
        },
        "existing_target_metadata_binding_resources": [
            "PROPERTIES", "UNITS", "OWNERS", "VENDORS", "TENANTS",
        ],
        "lease_relationship_preview_enabled": True,
        "customer_business_mutation_enabled": False,
        "customer_records_created_by_upload": False,
        "financial_posting_enabled": False,
        "official_api_adapter_enabled": False,
    }


@router.get("/runs/{run_id}/existing-targets")
def list_yardi_existing_targets(
    run_id: int,
    response: Response,
    resource: Literal["PROPERTIES", "UNITS", "OWNERS", "VENDORS", "TENANTS"],
    q: str = Query(min_length=2, max_length=80),
    limit: int = Query(default=20, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Scoped, bounded candidate picker: staff still must explicitly review matches.

    Returns identity labels and IDs only. No source-row data, credentials,
    tax/financial fields, password hashes or customer mutation.
    """
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    search = q.strip()
    if len(search) < 2:
        raise HTTPException(status_code=422, detail="Enter at least two search characters.")
    escaped = search.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    candidates = []
    if resource == "PROPERTIES":
        found = db.query(Property.id, Property.name).filter(
            Property.organization_id == run.organization_id,
            Property.is_active.is_(True),
            Property.deleted_at.is_(None),
            func.lower(Property.name).like(pattern, escape="\\"),
        ).order_by(Property.id.asc()).limit(limit).all()
        candidates = [{"id":id_, "label": name} for id_, name in found]
    elif resource == "UNITS":
        found = db.query(Unit.id, Unit.unit_number, Property.name).join(
            Property, Unit.property_id == Property.id,
        ).filter(
            Property.organization_id == run.organization_id,
            Property.is_active.is_(True),
            Property.deleted_at.is_(None),
            Unit.is_active.is_(True),
            Unit.deleted_at.is_(None),
            or_(
                func.lower(Unit.unit_number).like(pattern, escape="\\"),
                func.lower(Property.name).like(pattern, escape="\\"),
            ),
        ).order_by(Unit.id.asc()).limit(limit).all()
        candidates = [{"id":id_, "label": f"{unit_number} — {property_name}"}
                      for id_, unit_number, property_name in found]
    elif resource == "VENDORS":
        found = db.query(Vendor.id, Vendor.company_name).filter(
            Vendor.organization_id == run.organization_id,
            Vendor.deleted_at.is_(None),
            func.lower(Vendor.company_name).like(pattern, escape="\\"),
        ).order_by(Vendor.id.asc()).limit(limit).all()
        candidates = [{"id":id_, "label": name} for id_, name in found]
    else:
        target_role = UserRole.OWNER if resource == "OWNERS" else UserRole.TENANT
        found = db.query(User.id, User.first_name, User.last_name).filter(
            User.organization_id == run.organization_id,
            User.role == target_role,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
            or_(
                func.lower(User.first_name).like(pattern, escape="\\"),
                func.lower(User.last_name).like(pattern, escape="\\"),
            ),
        ).order_by(User.id.asc()).limit(limit).all()
        candidates = [{"id":id_, "label": f"{first} {last}".strip()}
                      for id_, first, last in found]
    response.headers["Cache-Control"] = "no-store"
    return {
        "run_id": run.id, "resource": resource, "candidates": candidates,
        "review_required": True, "auto_match_enabled": False,
        "customer_business_mutation": False,
    }


@router.get("/runs/{run_id}/bindings")
def list_yardi_durable_bindings(
    run_id: int,
    response: Response,
    resource: Literal["PROPERTIES", "UNITS", "OWNERS", "VENDORS", "TENANTS"] | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Read-only, organization-scoped inventory of committed migration identity metadata.

    No source file contents or customer record details are returned. An identity
    binding is not a lease, an occupancy determination, or an accounting posting.
    """
    run = _run(db, run_id=run_id, current_user=current_user, write=False)
    supported = ("PROPERTIES", "UNITS", "OWNERS", "VENDORS", "TENANTS")
    query = db.query(PlatformMigrationItem).filter(
        PlatformMigrationItem.run_id == run.id,
        PlatformMigrationItem.organization_id == run.organization_id,
        PlatformMigrationItem.provider == "YARDI",
        PlatformMigrationItem.resource.in_(supported),
    )
    if resource is not None:
        query = query.filter(PlatformMigrationItem.resource == resource)
    count = query.count()
    bindings = query.order_by(
        PlatformMigrationItem.id.asc(),
    ).offset(offset).limit(limit).all()
    results = []
    identity_collisions = _yardi_unresolved_identity_sources(db, run)
    entity_by_resource = {
        "PROPERTIES": "PROPERTY",
        "UNITS": "UNIT",
        "OWNERS": "OWNER_USER",
        "VENDORS": "VENDOR",
        "TENANTS": "TENANT_USER",
    }
    # Fetch reviewed source-to-target claims once for the page, instead of
    # running another reviewed-claim SELECT for every durable binding.
    # Unknown historical provider source IDs still contest valid target IDs.
    reviewed_claim_sources = {}
    reviewed_rows = db.query(
        PlatformMigrationStagedRow.resource,
        PlatformMigrationStagedRow.source_id,
        PlatformMigrationStagedRow.resolution_target_id,
        PlatformMigrationStagedRow.resolution_target_unit_id,
        PlatformMigrationStagedRow.resolution_target_owner_user_id,
        PlatformMigrationStagedRow.resolution_target_vendor_id,
        PlatformMigrationStagedRow.resolution_target_tenant_user_id,
    ).filter(
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource.in_(supported),
        PlatformMigrationStagedRow.resolution_action == "MATCH_EXISTING",
    ).all()
    for resource_name, source_id, property_id, unit_id, owner_id, vendor_id, tenant_id in reviewed_rows:
        target_id = {
            "PROPERTIES": property_id,
            "UNITS": unit_id,
            "OWNERS": owner_id,
            "VENDORS": vendor_id,
            "TENANTS": tenant_id,
        }[resource_name]
        if target_id is not None:
            reviewed_claim_sources.setdefault((resource_name, target_id), set()).add(source_id)
    # Read the exact historical Unit source-parent evidence once for the page.
    # Include NULL source IDs when present so historical unknown-source evidence
    # retains the same fail-closed behavior as per-item equality comparisons.
    unit_review_keys = {
        (item.source_id, item.source_fingerprint, item.target_id)
        for item in bindings
        if item.resource == "UNITS" and item.target_entity == "UNIT"
    }
    unit_source_ids = {key[0] for key in unit_review_keys if key[0] is not None}
    unit_reviews_by_key = {}
    if unit_review_keys:
        source_filter = PlatformMigrationStagedRow.source_id.in_(unit_source_ids)
        if any(key[0] is None for key in unit_review_keys):
            source_filter = source_filter | PlatformMigrationStagedRow.source_id.is_(None)
        reviews = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.organization_id == run.organization_id,
            PlatformMigrationStagedRow.provider == "YARDI",
            PlatformMigrationStagedRow.resource == "UNITS",
            source_filter,
            PlatformMigrationStagedRow.resolution_action == "MATCH_EXISTING",
        ).all()
        for review in reviews:
            key = (review.source_id, review.row_fingerprint,
                   review.resolution_target_unit_id)
            if key in unit_review_keys:
                unit_reviews_by_key.setdefault(key, []).append(review)
    for item in bindings:
        source_identity_collision = (item.resource, item.source_id) in identity_collisions
        # Keep an active target distinct from another source's reviewed claim.
        # A NULL historical source ID is different from every durable source.
        target_review_collision = any(
            reviewed_source_id != item.source_id
            for reviewed_source_id in reviewed_claim_sources.get(
                (item.resource, item.target_id), ()
            )
        )
        valid_entity = item.target_entity == entity_by_resource[item.resource]
        target_current = False
        parent_relationship_current = None  # Only applicable to verified Unit source-parent evidence.
        if valid_entity and item.resource == "PROPERTIES":
            target_current = db.query(Property.id).filter(
                Property.id == item.target_id,
                Property.organization_id == run.organization_id,
                Property.is_active.is_(True),
                Property.deleted_at.is_(None),
            ).first() is not None
        elif valid_entity and item.resource == "UNITS":
            target_current = db.query(Unit.id).join(
                Property, Unit.property_id == Property.id,
            ).filter(
                Unit.id == item.target_id,
                Property.organization_id == run.organization_id,
                Unit.is_active.is_(True), Unit.deleted_at.is_(None),
                Property.is_active.is_(True), Property.deleted_at.is_(None),
            ).first() is not None
            # Only an exact reviewed source-row fingerprint establishes which
            # Yardi Property this durable Unit identity was originally bound under.
            # Never infer the parent from an unreviewed name or current Unit location.
            source_reviews = unit_reviews_by_key.get(
                (item.source_id, item.source_fingerprint, item.target_id), ()
            )
            if source_reviews:
                # Every exact reviewed version is evidence. Picking the newest
                # hides contradictory or invalid older source-parent reviews.
                reviewed_parents = {
                    str((review.normalized_data or {}).get("source_property_id") or "").strip()
                    if not review.errors and review.disposition != "INVALID" else None
                    for review in source_reviews
                }
                if None in reviewed_parents or len(reviewed_parents) != 1 or not next(iter(reviewed_parents)):
                    parent_relationship_current = False
                else:
                    source_parent_id = next(iter(reviewed_parents))
                    parent_mapping = db.query(PlatformMigrationItem.target_id).filter(
                        PlatformMigrationItem.run_id == run.id,
                        PlatformMigrationItem.organization_id == run.organization_id,
                        PlatformMigrationItem.provider == "YARDI",
                        PlatformMigrationItem.resource == "PROPERTIES",
                        PlatformMigrationItem.source_id == source_parent_id,
                        PlatformMigrationItem.target_entity == "PROPERTY",
                    ).first()
                    parent_relationship_current = bool(
                        target_current and parent_mapping is not None
                        and db.query(Unit.id).filter(
                            Unit.id == item.target_id,
                            Unit.property_id == parent_mapping.target_id,
                        ).first() is not None
                    )
        elif valid_entity and item.resource in ("OWNERS", "TENANTS"):
            target_role = UserRole.OWNER if item.resource == "OWNERS" else UserRole.TENANT
            target_current = db.query(User.id).filter(
                User.id == item.target_id, User.organization_id == run.organization_id,
                User.role == target_role, User.is_active.is_(True),
                User.deleted_at.is_(None),
            ).first() is not None
        elif valid_entity and item.resource == "VENDORS":
            target_current = db.query(Vendor.id).filter(
                Vendor.id == item.target_id,
                Vendor.organization_id == run.organization_id,
                Vendor.deleted_at.is_(None),
            ).first() is not None
        # Current customer target validity and original source-parent certainty
        # are different. A new unresolved source version keeps the target active
        # but makes the reviewed original Unit source parent untrustworthy.
        if item.resource == "UNITS" and source_identity_collision:
            parent_relationship_current = False
        results.append({
            "id": item.id, "resource": item.resource, "source_id": item.source_id,
            "source_identity_collision": source_identity_collision,
            "target_review_collision": target_review_collision,
            "target_entity": item.target_entity, "target_id": item.target_id,
            "target_current": target_current,
            "unit_parent_relationship_current": parent_relationship_current,
            "created_by_platform_user_id": item.created_by_platform_user_id,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        })
    response.headers["Cache-Control"] = "no-store"
    return {
        "run_id": run.id, "organization_id": run.organization_id, "provider": "YARDI",
        "total": count, "offset": offset, "limit": limit, "items": results,
        "read_only": True, "customer_business_mutation": False,
    }


@router.get("/runs/{run_id}/source-collisions")
def list_yardi_source_collisions(
    run_id: int,
    response: Response,
    resource: Literal["PROPERTIES", "UNITS", "OWNERS", "VENDORS", "TENANTS", "LEASE_OCCUPANCY"] | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Read-only source-ID collision inventory across staged uploads in one Yardi run.

    Identical staged rows can be a replay-like overlap, while differing source
    fingerprints demand manual reconciliation. Neither case authorizes auto-merge.
    """
    run = _run(db, run_id=run_id, current_user=current_user, write=False)
    base = db.query(
        PlatformMigrationStagedRow.resource.label("resource"),
        PlatformMigrationStagedRow.source_id.label("source_id"),
        func.count(PlatformMigrationStagedRow.id).label("row_count"),
        func.count(func.distinct(PlatformMigrationStagedRow.upload_id)).label("upload_count"),
        func.count(func.distinct(PlatformMigrationStagedRow.row_fingerprint)).label("source_versions"),
        func.sum(case((PlatformMigrationStagedRow.resolution_action == "SKIP", 1), else_=0)).label("skipped_rows"),
    ).filter(
        PlatformMigrationStagedRow.run_id == run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.source_id.isnot(None),
        PlatformMigrationStagedRow.source_id != "",
    )
    if resource is not None:
        base = base.filter(PlatformMigrationStagedRow.resource == resource)
    grouped = base.group_by(
        PlatformMigrationStagedRow.resource,
        PlatformMigrationStagedRow.source_id,
    ).having(func.count(PlatformMigrationStagedRow.id) > 1)
    total = db.query(func.count()).select_from(grouped.subquery()).scalar() or 0
    groups = grouped.order_by(
        PlatformMigrationStagedRow.resource.asc(),
        PlatformMigrationStagedRow.source_id.asc(),
    ).offset(offset).limit(limit).all()
    collisions = []
    for group in groups:
        # Row identity is enough for a reviewer to navigate to its source
        # upload. Never return raw staged values, names or credentials.
        refs = db.query(
            PlatformMigrationStagedRow.id,
            PlatformMigrationStagedRow.upload_id,
            PlatformMigrationStagedRow.row_number,
            PlatformMigrationStagedRow.disposition,
            PlatformMigrationStagedRow.resolution_action,
            PlatformMigrationStagedRow.correction_evidence,
        ).filter(
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.organization_id == run.organization_id,
            PlatformMigrationStagedRow.provider == "YARDI",
            PlatformMigrationStagedRow.resource == group.resource,
            PlatformMigrationStagedRow.source_id == group.source_id,
        ).order_by(PlatformMigrationStagedRow.id.asc()).limit(10).all()
        skipped_rows = int(group.skipped_rows or 0)
        remaining_rows = group.row_count - skipped_rows
        # Count all versions, not just the ten sampled row references.
        # One unskipped version still requires separate explicit identity review.
        disposition_status = (
            "ALL_SKIPPED" if remaining_rows == 0
            else "ONE_UNSKIPPED" if remaining_rows == 1
            else "UNRESOLVED_MULTIPLE"
        )
        collisions.append({
            "resource": group.resource, "source_id": group.source_id,
            "skipped_rows": skipped_rows,
            "remaining_unskipped_rows": remaining_rows,
            "disposition_status": disposition_status,
            "row_count": group.row_count, "upload_count": group.upload_count,
            "source_versions": group.source_versions,
            "conflicting_source_versions": group.source_versions > 1,
            "sampled_rows": [
                {"staged_row_id": r.id, "upload_id": r.upload_id,
                 "row_number": r.row_number, "disposition": r.disposition,
                 "resolution_action": r.resolution_action,
                 "skip_reason_code": next((
                     entry.get("reason_code")
                     for entry in reversed(r.correction_evidence or [])
                     if isinstance(entry, dict) and entry.get("action") == "SKIP"
                     and entry.get("reason_code") in {
                         "NOT_IN_SCOPE", "DUPLICATE_SOURCE",
                         "ALREADY_HANDLED", "UNSUPPORTED_SOURCE",
                     }
                 ), None) if r.resolution_action == "SKIP" else None}
                for r in refs
            ],
            "sample_truncated": group.row_count > len(refs),
            "requires_manual_reconciliation": True,
        })
    response.headers["Cache-Control"] = "no-store"
    return {
        "run_id": run.id, "organization_id": run.organization_id,
        "provider": "YARDI", "total": total, "offset": offset,
        "limit": limit, "items": collisions,
        "read_only": True, "auto_merge_enabled": False,
        "customer_business_mutation": False,
    }


def _yardi_unresolved_identity_sources(db: Session, run) -> set[tuple[str, str]]:
    """Unskipped same-run Yardi identity versions require explicit disposition.

    Count all staged versions, not just reviewed ones or a paginated preview.
    A durable mapping never silently resolves a newly uploaded duplicate.
    """
    row = PlatformMigrationStagedRow
    conflicts = db.query(row.resource, row.source_id).filter(
        row.run_id == run.id,
        row.organization_id == run.organization_id,
        row.provider == "YARDI",
        row.resource.in_(("PROPERTIES", "UNITS", "OWNERS", "VENDORS", "TENANTS")),
        row.source_id.isnot(None),
        row.source_id != "",
        or_(row.resolution_action.is_(None), row.resolution_action != "SKIP"),
    ).group_by(row.resource, row.source_id).having(func.count(row.id) > 1).all()
    return {(resource, source_id) for resource, source_id in conflicts}


@router.get("/runs/{run_id}/lease-relationships")
def list_yardi_lease_relationships(
    run_id: int,
    response: Response,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Page through source lease identity dependencies; never create an occupancy.

    This endpoint only describes reviewed identity-map coverage and current
    organization-scoped targets. It cannot authorize a lease, rent or financial
    transaction even when every source relationship is accounted for.
    """
    run = _run(db, run_id=run_id, current_user=current_user, write=False)
    query = db.query(PlatformMigrationStagedRow).filter(
        PlatformMigrationStagedRow.run_id == run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource == "LEASE_OCCUPANCY",
    )
    total = query.count()
    staged = query.order_by(
        PlatformMigrationStagedRow.id.asc(),
    ).offset(offset).limit(limit).all()
    mappings = db.query(PlatformMigrationItem).filter(
        PlatformMigrationItem.run_id == run.id,
        PlatformMigrationItem.organization_id == run.organization_id,
        PlatformMigrationItem.provider == "YARDI",
        PlatformMigrationItem.resource.in_(("PROPERTIES", "UNITS", "TENANTS")),
    ).all()
    by_source = {(m.resource, m.source_id): m for m in mappings}
    identity_collisions = _yardi_unresolved_identity_sources(db, run)
    property_targets = {
        item.target_id for item in mappings
        if item.resource == "PROPERTIES" and item.target_entity == "PROPERTY"
    }
    unit_targets = {
        item.target_id for item in mappings
        if item.resource == "UNITS" and item.target_entity == "UNIT"
    }
    tenant_targets = {
        item.target_id for item in mappings
        if item.resource == "TENANTS" and item.target_entity == "TENANT_USER"
    }
    valid_properties = {
        p.id for p in db.query(Property.id).filter(
            Property.id.in_(property_targets),
            Property.organization_id == run.organization_id,
            Property.is_active.is_(True),
            Property.deleted_at.is_(None),
        ).all()
    }
    valid_units = {
        u.id: u.property_id for u in db.query(Unit.id, Unit.property_id).join(
            Property, Unit.property_id == Property.id,
        ).filter(
            Unit.id.in_(unit_targets),
            Property.organization_id == run.organization_id,
            Property.is_active.is_(True), Property.deleted_at.is_(None),
            Unit.is_active.is_(True), Unit.deleted_at.is_(None),
        ).all()
    }
    valid_tenants = {
        u.id for u in db.query(User.id).filter(
            User.id.in_(tenant_targets),
            User.organization_id == run.organization_id,
            User.role == UserRole.TENANT,
            User.is_active.is_(True), User.deleted_at.is_(None),
        ).all()
    }
    reviewed_unit_rows = db.query(PlatformMigrationStagedRow).filter(
        PlatformMigrationStagedRow.run_id == run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource == "UNITS",
        PlatformMigrationStagedRow.resolution_action == "MATCH_EXISTING",
    ).order_by(PlatformMigrationStagedRow.id.asc()).all()
    # Only exact reviewed source fingerprint + destination Unit evidence is
    # acceptable. A similarly named Unit or another run's staging is not proof.
    # Preserve every exact reviewed Unit parent record. A dict comprehension
    # silently overwrote conflicting versions, which could incorrectly make
    # a stale accepted lease relationship look current when the last row matched.
    reviewed_unit_sources = {}
    for reviewed_row in reviewed_unit_rows:
        key = (
            reviewed_row.source_id, reviewed_row.row_fingerprint,
            reviewed_row.resolution_target_unit_id,
        )
        parent_evidence = (
            str((reviewed_row.normalized_data or {}).get("source_property_id") or "").strip()
            if not reviewed_row.errors and reviewed_row.disposition != "INVALID"
            else None
        )
        reviewed_unit_sources.setdefault(key, []).append(parent_evidence)
    # The same run may contain conflicting lease revisions from multiple
    # uploads. Reviewed acceptance is only current when competing versions
    # remain explicitly skipped, including versions outside this page.
    competing_sources = db.query(
        PlatformMigrationStagedRow.id,
        PlatformMigrationStagedRow.source_id,
        PlatformMigrationStagedRow.resolution_action,
    ).filter(
        PlatformMigrationStagedRow.run_id == run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource == "LEASE_OCCUPANCY",
        PlatformMigrationStagedRow.source_id.isnot(None),
    ).all()
    non_skipped_lease_source_counts = {}
    for _, source_id, decision in competing_sources:
        if decision != "SKIP":
            non_skipped_lease_source_counts[source_id] = (
                non_skipped_lease_source_counts.get(source_id, 0) + 1
            )
    # Scope all retained reviewed Property/Unit/Tenant customer-target claims
    # once, including historical reviews whose provider source ID is NULL.
    # The paginated preview must not issue up to three claim lookups per Lease.
    reviewed_claim_sources = {}
    reviewed_claims = db.query(
        PlatformMigrationStagedRow.resource,
        PlatformMigrationStagedRow.source_id,
        PlatformMigrationStagedRow.resolution_target_id,
        PlatformMigrationStagedRow.resolution_target_unit_id,
        PlatformMigrationStagedRow.resolution_target_tenant_user_id,
    ).filter(
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource.in_(("PROPERTIES", "UNITS", "TENANTS")),
        PlatformMigrationStagedRow.resolution_action == "MATCH_EXISTING",
    ).all()
    for resource, source_id, property_target, unit_target, tenant_target in reviewed_claims:
        target = {
            "PROPERTIES": property_target,
            "UNITS": unit_target,
            "TENANTS": tenant_target,
        }[resource]
        if target is not None:
            reviewed_claim_sources.setdefault((resource, target), set()).add(source_id)
    results = []
    for staged_row in staged:
        blockers = []
        unit_source_parent_matches_lease = None
        current_identity_targets = None
        if (staged_row.errors or staged_row.disposition == "INVALID"
                or staged_row.resolution_action == "SKIP"):
            blockers.append("INVALID_OR_SKIPPED")
        else:
            source = staged_row.normalized_data or {}
            prop = by_source.get((
                "PROPERTIES", str(source.get("source_property_id") or "").strip(),
            ))
            unit = by_source.get((
                "UNITS", str(source.get("source_unit_id") or "").strip(),
            ))
            tenant = by_source.get((
                "TENANTS", str(source.get("source_tenant_id") or "").strip(),
            ))
            property_id = (
                prop.target_id if prop is not None
                and prop.target_entity == "PROPERTY"
                and prop.target_id in valid_properties else None
            )
            unit_id = (
                unit.target_id if unit is not None
                and unit.target_entity == "UNIT"
                and unit.target_id in valid_units else None
            )
            tenant_id = (
                tenant.target_id if tenant is not None
                and tenant.target_entity == "TENANT_USER"
                and tenant.target_id in valid_tenants else None
            )
            current_identity_targets = (property_id, unit_id, tenant_id)
            for resource, source_field, target_id, blocker in (
                ("PROPERTIES", "source_property_id", property_id, "PROPERTY_TARGET_REVIEW_COLLISION"),
                ("UNITS", "source_unit_id", unit_id, "UNIT_TARGET_REVIEW_COLLISION"),
                ("TENANTS", "source_tenant_id", tenant_id, "TENANT_TARGET_REVIEW_COLLISION"),
            ):
                if target_id is None:
                    continue
                source_id = str(source.get(source_field) or "").strip()
                if any(
                    reviewed_source_id != source_id
                    for reviewed_source_id in reviewed_claim_sources.get(
                        (resource, target_id), ()
                    )
                ):
                    blockers.append(blocker)
            for resource, source_field, blocker in (
                ("PROPERTIES", "source_property_id", "PROPERTY_SOURCE_ID_COLLISION"),
                ("UNITS", "source_unit_id", "UNIT_SOURCE_ID_COLLISION"),
                ("TENANTS", "source_tenant_id", "TENANT_SOURCE_ID_COLLISION"),
            ):
                if (resource, str(source.get(source_field) or "").strip()) in identity_collisions:
                    blockers.append(blocker)
            if property_id is None:
                blockers.append("PROPERTY_IDENTITY_UNMAPPED_OR_INACTIVE")
            if unit_id is None:
                blockers.append("UNIT_IDENTITY_UNMAPPED_OR_INACTIVE")
            if tenant_id is None:
                blockers.append("TENANT_IDENTITY_UNMAPPED_OR_INACTIVE")
            if property_id is not None and unit_id is not None:
                if valid_units[unit_id] != property_id:
                    blockers.append("UNIT_PROPERTY_MISMATCH")
            if unit is not None and unit_id is not None and unit.target_entity == "UNIT":
                reviewed_parents = reviewed_unit_sources.get((
                    unit.source_id, unit.source_fingerprint, unit.target_id,
                ))
                if reviewed_parents:
                    lease_parent_source = str(
                        source.get("source_property_id") or ""
                    ).strip()
                    # Mirror acceptance: EVERY exact reviewed parent must be valid
                    # and identical to the source Property of the lease.
                    unit_source_parent_matches_lease = (
                        None not in reviewed_parents
                        and set(reviewed_parents) == {lease_parent_source}
                    )
                    if not unit_source_parent_matches_lease:
                        blockers.append("UNIT_SOURCE_PARENT_MISMATCH")
        is_accepted = staged_row.resolution_action == "ACCEPT_RELATIONSHIP"
        if (staged_row.source_id
                and non_skipped_lease_source_counts.get(staged_row.source_id, 0) > 1):
            blockers.append("LEASE_SOURCE_ID_COLLISION")
        if is_accepted:
            stored_targets = (
                staged_row.resolution_target_id,
                staged_row.resolution_target_unit_id,
                staged_row.resolution_target_tenant_user_id,
            )
            if (current_identity_targets is None
                    or stored_targets != current_identity_targets
                    or unit_source_parent_matches_lease is not True):
                blockers.append("ACCEPTED_RELATIONSHIP_STALE")
        review_current = is_accepted and not blockers
        results.append({
            "staged_row_id": staged_row.id,
            "row_number": staged_row.row_number,
            "source_id": staged_row.source_id,
            "blockers": blockers,
            "identity_links_complete": not blockers,
            "relationship_review_recorded": is_accepted,
            "relationship_review_current": review_current,
            "unit_source_parent_matches_lease": unit_source_parent_matches_lease,
            "occupancy_or_lease_authorized": False,
        })
    response.headers["Cache-Control"] = "no-store"
    return {
        "run_id": run.id, "organization_id": run.organization_id,
        "provider": "YARDI", "total": total, "offset": offset, "limit": limit,
        "items": results,
        "read_only": True, "controlled_commit_enabled": False,
        "customer_business_mutation": False,
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


@router.get("/runs/{run_id}/reconciliation")
def get_yardi_reconciliation(
    run_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Read-only source coverage; does not authorize any migration commit."""
    run = _run(db, run_id=run_id, current_user=current_user, write=False)
    rows = db.query(PlatformMigrationStagedRow).filter(
        PlatformMigrationStagedRow.run_id == run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
    ).order_by(PlatformMigrationStagedRow.id.asc()).all()
    items = db.query(PlatformMigrationItem).filter(
        PlatformMigrationItem.run_id == run.id,
        PlatformMigrationItem.organization_id == run.organization_id,
        PlatformMigrationItem.provider == "YARDI",
    ).order_by(PlatformMigrationItem.id.asc()).all()
    existing = {(item.resource, item.source_id) for item in items}
    identity_collisions = _yardi_unresolved_identity_sources(db, run)
    # Read-only reconciliation rechecks historical staff target claims. A
    # repeated SAME provider source ID in another run is not a new identity.
    # One scoped projection covers all reviewed source claims instead of
    # issuing a competitor query for every staged identity row. A retained
    # review with a missing source ID remains a competing *unknown* identity:
    # SQL inequality would otherwise miss NULL and incorrectly mark ready.
    reviewed_claim_rows = db.query(
        PlatformMigrationStagedRow.resource,
        PlatformMigrationStagedRow.source_id,
        PlatformMigrationStagedRow.resolution_target_id,
        PlatformMigrationStagedRow.resolution_target_unit_id,
        PlatformMigrationStagedRow.resolution_target_owner_user_id,
        PlatformMigrationStagedRow.resolution_target_vendor_id,
        PlatformMigrationStagedRow.resolution_target_tenant_user_id,
    ).filter(
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resolution_action == "MATCH_EXISTING",
        PlatformMigrationStagedRow.resource.in_(
            ("PROPERTIES", "UNITS", "OWNERS", "VENDORS", "TENANTS")
        ),
    ).all()
    reviewed_claim_sources = {}
    for resource, source_id, property_id, unit_id, owner_id, vendor_id, tenant_id in reviewed_claim_rows:
        target = {
            "PROPERTIES": property_id, "UNITS": unit_id,
            "OWNERS": owner_id, "VENDORS": vendor_id,
            "TENANTS": tenant_id,
        }[resource]
        if target is not None:
            reviewed_claim_sources.setdefault((resource, target), set()).add(source_id)

    def claimed_by_other_review(row, target_id):
        return (
            target_id is not None
            and any(
                other_source_id != row.source_id
                for other_source_id in reviewed_claim_sources.get(
                    (row.resource, target_id), ()
                )
            )
        )

    resources: dict[str, dict[str, int]] = {}
    unresolved = invalid = skipped = 0
    # Exact per-row diagnostic status belongs in the private fingerprint
    # evidence: equal totals can hide a swap in WHICH identity is contested.
    row_readiness_evidence = []
    for row in rows:
        stats = resources.setdefault(row.resource, {
            "total": 0, "invalid": 0, "mapped": 0, "skipped": 0, "needs_review": 0,
            "matched_existing": 0, "accepted_relationship_review": 0,
        })
        stats["total"] += 1
        if row.resolution_action == "SKIP":
            skipped += 1
            stats["skipped"] += 1
            row_readiness_evidence.append((row.id, "SKIPPED"))
        elif row.errors or row.disposition == "INVALID":
            # A stale recorded decision is evidence, not validation: invalid
            # source rows can never count as matched or accepted readiness.
            invalid += 1
            stats["invalid"] += 1
            row_readiness_evidence.append((row.id, "INVALID"))
        elif row.resolution_action == "MATCH_EXISTING":
            if row.resource == "UNITS":
                parent_source = str((row.normalized_data or {}).get("source_property_id") or "").strip()
                parent = next((
                    item for item in items
                    if item.resource == "PROPERTIES" and item.source_id == parent_source
                    and item.target_entity == "PROPERTY"
                ), None)
                target_valid = (
                    parent is not None and row.resolution_target_unit_id is not None
                    and db.query(Unit.id).join(Property, Unit.property_id == Property.id).filter(
                        Unit.id == row.resolution_target_unit_id,
                        Unit.property_id == parent.target_id,
                        Unit.is_active.is_(True), Unit.deleted_at.is_(None),
                        Property.organization_id == run.organization_id,
                        Property.is_active.is_(True), Property.deleted_at.is_(None),
                    ).first() is not None
                )
            elif row.resource == "OWNERS":
                target_valid = row.resolution_target_owner_user_id is not None and db.query(User.id).filter(
                    User.id == row.resolution_target_owner_user_id,
                    User.organization_id == run.organization_id,
                    User.role == UserRole.OWNER,
                    User.is_active.is_(True),
                    User.deleted_at.is_(None),
                ).first() is not None
            elif row.resource == "TENANTS":
                target_valid = row.resolution_target_tenant_user_id is not None and db.query(User.id).filter(
                    User.id == row.resolution_target_tenant_user_id,
                    User.organization_id == run.organization_id,
                    User.role == UserRole.TENANT,
                    User.is_active.is_(True),
                    User.deleted_at.is_(None),
                ).first() is not None
            elif row.resource == "VENDORS":
                target_valid = row.resolution_target_vendor_id is not None and db.query(Vendor.id).filter(
                    Vendor.id == row.resolution_target_vendor_id,
                    Vendor.organization_id == run.organization_id,
                    Vendor.deleted_at.is_(None),
                ).first() is not None
            elif row.resource == "PROPERTIES":
                target_valid = row.resolution_target_id is not None and db.query(Property.id).filter(
                    Property.id == row.resolution_target_id,
                    Property.organization_id == run.organization_id,
                    Property.is_active.is_(True), Property.deleted_at.is_(None),
                ).first() is not None
            else:
                target_valid = False
            # A recorded review is not current if its durable source identity
            # now points to a different customer target or source fingerprint.
            # Do not inflate a run's ready count with historical conflicting
            # evidence. Keep the original reviewed action/audit unchanged.
            durable = next((
                item for item in items
                if item.resource == row.resource and item.source_id == row.source_id
            ), None)
            if durable is not None:
                reviewed_target = {
                    "PROPERTIES": row.resolution_target_id,
                    "UNITS": row.resolution_target_unit_id,
                    "OWNERS": row.resolution_target_owner_user_id,
                    "VENDORS": row.resolution_target_vendor_id,
                    "TENANTS": row.resolution_target_tenant_user_id,
                }.get(row.resource)
                target_valid = (
                    target_valid and reviewed_target == durable.target_id
                    and row.row_fingerprint == durable.source_fingerprint
                    and durable.target_entity == {
                        "PROPERTIES": "PROPERTY", "UNITS": "UNIT",
                        "OWNERS": "OWNER_USER", "VENDORS": "VENDOR",
                        "TENANTS": "TENANT_USER",
                    }.get(row.resource)
                )
            if (row.resource, row.source_id) in identity_collisions:
                # A historical match is not safe while another unskipped
                # upload claims the same provider identity, even if identical.
                target_valid = False
            reviewed_target = {
                "PROPERTIES": row.resolution_target_id,
                "UNITS": row.resolution_target_unit_id,
                "OWNERS": row.resolution_target_owner_user_id,
                "VENDORS": row.resolution_target_vendor_id,
                "TENANTS": row.resolution_target_tenant_user_id,
            }.get(row.resource)
            if target_valid and claimed_by_other_review(row, reviewed_target):
                target_valid = False
            if target_valid:
                stats["matched_existing"] += 1
                row_readiness_evidence.append((row.id, "REVIEWED_CURRENT"))
            else:
                unresolved += 1
                stats["needs_review"] += 1
                row_readiness_evidence.append((row.id, "REVIEWED_STALE"))
        elif row.resource == "LEASE_OCCUPANCY" and row.resolution_action == "ACCEPT_RELATIONSHIP":
            # This count means staff recorded identity review, NOT that lease,
            # occupancy, financial records or current targets are commit-ready.
            stats["accepted_relationship_review"] += 1
            row_readiness_evidence.append((row.id, "ACCEPTED_RELATIONSHIP_RECORDED"))
        elif (row.source_id and (row.resource, row.source_id) in existing
              and (row.resource, row.source_id) not in identity_collisions):
            # Source-ID equality alone cannot make an unreviewed staged version
            # ready: the durable identity must describe this exact export row.
            binding = next((
                item for item in items
                if item.resource == row.resource and item.source_id == row.source_id
            ), None)
            expected_entity = {
                "PROPERTIES": "PROPERTY", "UNITS": "UNIT",
                "OWNERS": "OWNER_USER", "VENDORS": "VENDOR",
                "TENANTS": "TENANT_USER",
            }.get(row.resource)
            target_current = False
            if (binding is not None and expected_entity
                    and binding.target_entity == expected_entity
                    and binding.source_fingerprint == row.row_fingerprint):
                if row.resource == "PROPERTIES":
                    target_current = db.query(Property.id).filter(
                        Property.id == binding.target_id,
                        Property.organization_id == run.organization_id,
                        Property.is_active.is_(True), Property.deleted_at.is_(None),
                    ).first() is not None
                elif row.resource == "UNITS":
                    source_parent = str((row.normalized_data or {}).get("source_property_id") or "").strip()
                    parent_binding = next((
                        item for item in items
                        if item.resource == "PROPERTIES"
                        and item.source_id == source_parent
                        and item.target_entity == "PROPERTY"
                    ), None)
                    target_current = (
                        bool(source_parent) and parent_binding is not None
                        and db.query(Unit.id).join(Property, Unit.property_id == Property.id).filter(
                            Unit.id == binding.target_id,
                            Unit.property_id == parent_binding.target_id,
                            Unit.is_active.is_(True), Unit.deleted_at.is_(None),
                            Property.organization_id == run.organization_id,
                            Property.is_active.is_(True), Property.deleted_at.is_(None),
                        ).first() is not None
                    )
                elif row.resource in ("OWNERS", "TENANTS"):
                    role = UserRole.OWNER if row.resource == "OWNERS" else UserRole.TENANT
                    target_current = db.query(User.id).filter(
                        User.id == binding.target_id,
                        User.organization_id == run.organization_id,
                        User.role == role, User.is_active.is_(True),
                        User.deleted_at.is_(None),
                    ).first() is not None
                elif row.resource == "VENDORS":
                    target_current = db.query(Vendor.id).filter(
                        Vendor.id == binding.target_id,
                        Vendor.organization_id == run.organization_id,
                        Vendor.deleted_at.is_(None),
                    ).first() is not None
            if target_current and claimed_by_other_review(row, binding.target_id):
                target_current = False
            if target_current:
                stats["mapped"] += 1
                row_readiness_evidence.append((row.id, "DURABLE_CURRENT"))
            else:
                unresolved += 1
                stats["needs_review"] += 1
                row_readiness_evidence.append((row.id, "DURABLE_STALE"))
        else:
            unresolved += 1
            stats["needs_review"] += 1
            row_readiness_evidence.append((row.id, "NEEDS_REVIEW"))
    # Read-only lease identity dependency coverage. A complete dependency set is
    # NOT evidence of an authorized lease, rent, occupancy or accounting import.
    lease_rows = [row for row in rows if row.resource == "LEASE_OCCUPANCY"]
    # A repeated unskipped provider lease source ID is a collision, even when
    # each row independently has valid Property / Unit / Tenant identity links.
    # The per-row preview already blocks them; align the aggregate coverage.
    unskipped_lease_sources = {}
    for lease in lease_rows:
        if lease.source_id and lease.resolution_action != "SKIP":
            unskipped_lease_sources[lease.source_id] = (
                unskipped_lease_sources.get(lease.source_id, 0) + 1
            )
    lease_links = {(item.resource, item.source_id): item for item in items}
    mapped_properties = {item.target_id for item in items
                         if item.resource == "PROPERTIES" and item.target_entity == "PROPERTY"}
    mapped_units = {item.target_id for item in items
                    if item.resource == "UNITS" and item.target_entity == "UNIT"}
    mapped_tenants = {item.target_id for item in items
                      if item.resource == "TENANTS" and item.target_entity == "TENANT_USER"}
    valid_properties = {record.id for record in db.query(Property.id).filter(
        Property.id.in_(mapped_properties),
        Property.organization_id == run.organization_id,
        Property.is_active.is_(True),
        Property.deleted_at.is_(None),
    ).all()}
    valid_units = {record.id: record.property_id for record in db.query(
        Unit.id, Unit.property_id,
    ).join(Property, Unit.property_id == Property.id).filter(
        Unit.id.in_(mapped_units),
        Property.organization_id == run.organization_id,
        Unit.is_active.is_(True),
        Unit.deleted_at.is_(None),
        Property.is_active.is_(True),
        Property.deleted_at.is_(None),
    ).all()}
    valid_tenants = {record.id for record in db.query(User.id).filter(
        User.id.in_(mapped_tenants),
        User.organization_id == run.organization_id,
        User.role == UserRole.TENANT,
        User.is_active.is_(True),
        User.deleted_at.is_(None),
    ).all()}
    # Aggregate readiness must consider every exact-reviewed Unit source parent.
    # Never hide conflicting versions by overwriting the last matching key.
    reviewed_lease_unit_parent_sources = {}
    for unit_row in rows:
        if unit_row.resource != "UNITS" or unit_row.resolution_action != "MATCH_EXISTING":
            continue
        key = (unit_row.source_id, unit_row.row_fingerprint, unit_row.resolution_target_unit_id)
        parent_source = (
            str((unit_row.normalized_data or {}).get("source_property_id") or "").strip()
            if not unit_row.errors and unit_row.disposition != "INVALID"
            else None
        )
        reviewed_lease_unit_parent_sources.setdefault(key, []).append(parent_source)
    lease_relationship_readiness = {
        "staged": len(lease_rows), "complete_identity_links": 0,
        "missing_property": 0, "missing_unit": 0, "missing_tenant": 0,
        "unit_property_mismatch": 0, "unit_source_parent_mismatch": 0,
        "lease_source_id_collisions": 0, "identity_source_id_collisions": 0,
        "identity_target_review_collisions": 0,
        "accepted_relationship_stale": 0,
        "invalid_or_skipped": 0,
        "controlled_commit_enabled": False, "customer_business_mutation": False,
    }
    lease_row_readiness_evidence = []
    for lease_row in lease_rows:
        if lease_row.errors or lease_row.disposition == "INVALID" or lease_row.resolution_action == "SKIP":
            lease_relationship_readiness["invalid_or_skipped"] += 1
            lease_row_readiness_evidence.append((lease_row.id, "INVALID_OR_SKIPPED"))
            continue
        data = lease_row.normalized_data or {}
        property_link = lease_links.get(("PROPERTIES", str(data.get("source_property_id") or "").strip()))
        unit_link = lease_links.get(("UNITS", str(data.get("source_unit_id") or "").strip()))
        tenant_link = lease_links.get(("TENANTS", str(data.get("source_tenant_id") or "").strip()))
        property_id = (
            property_link.target_id if property_link and property_link.target_entity == "PROPERTY"
            and property_link.target_id in valid_properties else None
        )
        unit_id = (
            unit_link.target_id if unit_link and unit_link.target_entity == "UNIT"
            and unit_link.target_id in valid_units else None
        )
        tenant_id = (
            tenant_link.target_id if tenant_link and tenant_link.target_entity == "TENANT_USER"
            and tenant_link.target_id in valid_tenants else None
        )
        if property_id is None:
            lease_relationship_readiness["missing_property"] += 1
        if unit_id is None:
            lease_relationship_readiness["missing_unit"] += 1
        if tenant_id is None:
            lease_relationship_readiness["missing_tenant"] += 1
        identity_collision = any(
            (resource, str(data.get(field) or "").strip()) in identity_collisions
            for resource, field in (
                ("PROPERTIES", "source_property_id"),
                ("UNITS", "source_unit_id"),
                ("TENANTS", "source_tenant_id"),
            )
        )
        if identity_collision:
            lease_relationship_readiness["identity_source_id_collisions"] += 1
        target_review_collision = False
        # Reuse the existing organization-scoped reviewed-claim projection,
        # not an extra SELECT for each mapped identity on every staged Lease.
        for resource, field, target_id in (
            ("PROPERTIES", "source_property_id", property_id),
            ("UNITS", "source_unit_id", unit_id),
            ("TENANTS", "source_tenant_id", tenant_id),
        ):
            if target_id is None:
                continue
            source_id = str(data.get(field) or "").strip()
            if any(
                reviewed_source_id != source_id
                for reviewed_source_id in reviewed_claim_sources.get(
                    (resource, target_id), ()
                )
            ):
                target_review_collision = True
                break
        if target_review_collision:
            lease_relationship_readiness["identity_target_review_collisions"] += 1
        source_parent_conflicts = False
        source_parent_current = False
        if unit_link is not None and unit_id is not None and unit_link.target_entity == "UNIT":
            reviewed_parents = reviewed_lease_unit_parent_sources.get((
                unit_link.source_id, unit_link.source_fingerprint, unit_link.target_id,
            ))
            if reviewed_parents:
                source_parent_current = (
                    None not in reviewed_parents
                    and set(reviewed_parents) == {
                        str(data.get("source_property_id") or "").strip()
                    }
                )
                if not source_parent_current:
                    source_parent_conflicts = True
                    lease_relationship_readiness["unit_source_parent_mismatch"] += 1
        target_parent_conflicts = (
            property_id is not None and unit_id is not None
            and valid_units[unit_id] != property_id
        )
        if target_parent_conflicts:
            lease_relationship_readiness["unit_property_mismatch"] += 1
        source_id_collision = (
            bool(lease_row.source_id)
            and unskipped_lease_sources.get(lease_row.source_id, 0) > 1
        )
        if source_id_collision:
            lease_relationship_readiness["lease_source_id_collisions"] += 1
        # Acceptance is an auditable snapshot. A later *valid* mapping change
        # may leave all dependency IDs resolvable while invalidating review.
        accepted_review_stale = (
            lease_row.resolution_action == "ACCEPT_RELATIONSHIP"
            and (
                (lease_row.resolution_target_id,
                 lease_row.resolution_target_unit_id,
                 lease_row.resolution_target_tenant_user_id)
                != (property_id, unit_id, tenant_id)
                or not source_parent_current or identity_collision
                or target_review_collision
            )
        )
        if accepted_review_stale:
            lease_relationship_readiness["accepted_relationship_stale"] += 1
        if (property_id is not None and unit_id is not None and tenant_id is not None
                and not source_parent_conflicts and not target_parent_conflicts
                and not source_id_collision and not identity_collision
                and not target_review_collision and not accepted_review_stale):
            lease_relationship_readiness["complete_identity_links"] += 1
        # A cross-run target review can move from lease A to lease B without
        # changing the aggregate stale/complete counts. Fingerprint each
        # source lease's readiness, not just the run-level totals.
        lease_row_readiness_evidence.append((
            lease_row.id, property_id, unit_id, tenant_id,
            bool(identity_collision), bool(target_review_collision),
            bool(source_parent_conflicts), bool(source_parent_current),
            bool(target_parent_conflicts), bool(source_id_collision),
            bool(accepted_review_stale),
        ))

    evidence = {
        "identity_row_readiness": row_readiness_evidence,
        "lease_row_readiness": lease_row_readiness_evidence,
        "staged": [(r.id, r.resource, r.source_id, r.row_fingerprint, r.disposition,
                    r.resolution_action, r.resolution_target_id, r.resolution_target_unit_id,
                    r.resolution_target_vendor_id, r.resolution_target_tenant_user_id,
                    r.resolution_target_owner_user_id) for r in rows],
        "mapped": [(i.id, i.resource, i.source_id, i.target_entity, i.target_id,
                    i.source_fingerprint) for i in items],
        "lease_dependency_coverage": lease_relationship_readiness,
        "lease_unit_parent_relationships": sorted(valid_units.items()),
        # Current target validity can change independently of historical
        # staged/mapped evidence. Invalidate saved review dry-runs when active
        # or soft-delete status changes a resource's readiness counters.
        "resource_coverage": resources,
    }
    digest = hashlib.sha256(
        json.dumps(evidence, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()
    response.headers["Cache-Control"] = "no-store"
    return {
        "run_id": run.id, "provider": "YARDI",
        "resource_coverage": resources,
        "lease_relationship_readiness": lease_relationship_readiness,
        "staged_rows": len(rows), "durable_mapping_count": len(items),
        "invalid_rows": invalid, "unresolved_rows": unresolved,
        "skipped_rows": skipped,
        "review_fingerprint": digest,
        "controlled_commit_enabled": False,
        "customer_business_mutation": False,
    }


class YardiRowSkipIn(BaseModel):
    reason_code: Literal["NOT_IN_SCOPE", "DUPLICATE_SOURCE", "ALREADY_HANDLED", "UNSUPPORTED_SOURCE"]


@router.post("/runs/{run_id}/staged-rows/{row_id}/skip")
def skip_yardi_staged_row(
    run_id: int,
    row_id: int,
    payload: YardiRowSkipIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Explicit skip review only; cannot create or change customer records."""
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    row = db.query(PlatformMigrationStagedRow).filter(
        PlatformMigrationStagedRow.id == row_id,
        PlatformMigrationStagedRow.run_id == run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Yardi staged row not found.")
    already_mapped = db.query(PlatformMigrationItem).filter(
        PlatformMigrationItem.run_id == run.id,
        PlatformMigrationItem.organization_id == run.organization_id,
        PlatformMigrationItem.provider == "YARDI",
        PlatformMigrationItem.resource == row.resource,
        PlatformMigrationItem.source_id == row.source_id,
    ).first() if row.source_id else None
    # Allow a reason-coded SKIP of a *new, unreviewed* duplicate only when
    # another exact reviewed row independently anchors the durable binding.
    # Skipping the mapped review itself, inventing a review for an orphan
    # binding, or changing a prior non-SKIP decision remains forbidden.
    retained_review = None
    if already_mapped:
        target_column = {
            "PROPERTIES": PlatformMigrationStagedRow.resolution_target_id,
            "UNITS": PlatformMigrationStagedRow.resolution_target_unit_id,
            "OWNERS": PlatformMigrationStagedRow.resolution_target_owner_user_id,
            "VENDORS": PlatformMigrationStagedRow.resolution_target_vendor_id,
            "TENANTS": PlatformMigrationStagedRow.resolution_target_tenant_user_id,
        }.get(row.resource)
        if target_column is not None and row.resolution_action in (None, "SKIP"):
            candidates = db.query(PlatformMigrationStagedRow).filter(
                PlatformMigrationStagedRow.run_id == run.id,
                PlatformMigrationStagedRow.organization_id == run.organization_id,
                PlatformMigrationStagedRow.provider == "YARDI",
                PlatformMigrationStagedRow.resource == row.resource,
                PlatformMigrationStagedRow.source_id == row.source_id,
                PlatformMigrationStagedRow.id != row.id,
                PlatformMigrationStagedRow.row_fingerprint == already_mapped.source_fingerprint,
                PlatformMigrationStagedRow.resolution_action == "MATCH_EXISTING",
                target_column == already_mapped.target_id,
            ).all()
            retained_review = next(
                (candidate for candidate in candidates
                 if not candidate.errors and candidate.disposition != "INVALID"),
                None,
            )
        if retained_review is None:
            raise HTTPException(
                status_code=409,
                detail="Durably mapped source cannot be skipped without another exact reviewed binding.",
            )
    if row.resolution_action not in (None, "SKIP"):
        raise HTTPException(status_code=409, detail="A different review decision already exists.")
    evidence = list(row.correction_evidence or [])
    if row.resolution_action == "SKIP":
        previous_reasons = [e.get("reason_code") for e in (row.correction_evidence or []) if isinstance(e, dict) and e.get("action") == "SKIP"]
        if not previous_reasons or previous_reasons[-1] != payload.reason_code:
            raise HTTPException(status_code=409, detail="SKIP review reason differs from recorded decision.")
        return {
            "id": row.id, "run_id": run.id, "action": "SKIP",
            "replayed": True,
        }
    row.resolution_action = "SKIP"
    row.resolved_by_platform_user_id = current_user.id
    row.resolved_at = datetime.utcnow()
    evidence.append({"action": "SKIP", "reason_code": payload.reason_code})
    row.correction_evidence = evidence
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    append_audit_log(
        db,
        platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_staged_row",
        entity_id=row.id,
        action="yardi_row_skipped",
        new_value={
            "run_id": run.id, "resource": row.resource,
            "reason_code": payload.reason_code,
            "durable_mapping_preserved": already_mapped is not None,
            "retained_reviewed_staged_row_id": (
                retained_review.id if retained_review is not None else None
            ),
            "customer_business_mutation": False,
        },
    )
    db.commit()
    return {"id": row.id, "run_id": run.id, "action": "SKIP", "replayed": False}


@router.post("/runs/{run_id}/staged-rows/{row_id}/accept-lease-relationship")
def accept_yardi_staged_lease_relationship(
    run_id: int,
    row_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Review exact source identities only. No Lease, occupancy or money mutation."""
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    row = db.query(PlatformMigrationStagedRow).filter(
        PlatformMigrationStagedRow.id == row_id,
        PlatformMigrationStagedRow.run_id == run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource == "LEASE_OCCUPANCY",
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Yardi lease source row not found.")
    if row.errors or row.disposition == "INVALID" or not row.source_id:
        raise HTTPException(status_code=409, detail="Invalid or unidentified lease row cannot be accepted.")
    if row.resolution_action not in (None, "ACCEPT_RELATIONSHIP"):
        raise HTTPException(status_code=409, detail="Conflicting source review decision already recorded.")
    duplicate = db.query(PlatformMigrationStagedRow.id).filter(
        PlatformMigrationStagedRow.run_id == run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource == "LEASE_OCCUPANCY",
        PlatformMigrationStagedRow.source_id == row.source_id,
        PlatformMigrationStagedRow.id != row.id,
        or_(PlatformMigrationStagedRow.resolution_action.is_(None),
            PlatformMigrationStagedRow.resolution_action != "SKIP"),
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="Repeated lease source ID requires explicit duplicate review.")
    source = row.normalized_data or {}
    source_ids = {
        "PROPERTIES": str(source.get("source_property_id") or "").strip(),
        "UNITS": str(source.get("source_unit_id") or "").strip(),
        "TENANTS": str(source.get("source_tenant_id") or "").strip(),
    }
    if not all(source_ids.values()):
        raise HTTPException(status_code=409, detail="Lease source IDs must identify Property, Unit and Tenant.")
    collisions = _yardi_unresolved_identity_sources(db, run)
    if any((resource, source_id) in collisions for resource, source_id in source_ids.items()):
        raise HTTPException(
            status_code=409,
            detail="Repeated Property, Unit or Tenant source ID requires explicit duplicate review.",
        )
    mappings = {}
    expected = {"PROPERTIES": "PROPERTY", "UNITS": "UNIT", "TENANTS": "TENANT_USER"}
    for resource, source_id in source_ids.items():
        mapped = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "YARDI",
            PlatformMigrationItem.resource == resource,
            PlatformMigrationItem.source_id == source_id,
            PlatformMigrationItem.target_entity == expected[resource],
        ).first()
        if mapped is None:
            raise HTTPException(status_code=409, detail="Durable Property, Unit and Tenant identity mappings are required.")
        mappings[resource] = mapped
    property_id = mappings["PROPERTIES"].target_id
    unit_id = mappings["UNITS"].target_id
    tenant_id = mappings["TENANTS"].target_id
    current_property = db.query(Property.id).filter(
        Property.id == property_id, Property.organization_id == run.organization_id,
        Property.is_active.is_(True), Property.deleted_at.is_(None),
    ).first()
    current_unit = db.query(Unit.id, Unit.property_id).join(
        Property, Unit.property_id == Property.id,
    ).filter(
        Unit.id == unit_id,
        Unit.is_active.is_(True), Unit.deleted_at.is_(None),
        Property.organization_id == run.organization_id,
        Property.is_active.is_(True), Property.deleted_at.is_(None),
    ).first()
    current_tenant = db.query(User.id).filter(
        User.id == tenant_id, User.organization_id == run.organization_id,
        User.role == UserRole.TENANT, User.is_active.is_(True),
        User.deleted_at.is_(None),
    ).first()
    if not current_property or not current_unit or not current_tenant:
        raise HTTPException(status_code=409, detail="Reviewed lease identity target is inactive or outside organization.")
    if current_unit.property_id != property_id:
        raise HTTPException(status_code=409, detail="Mapped Unit no longer belongs to mapped Property.")
    # Any competing, differently identified staff claim makes new and
    # replayed source-relationship acceptance unsafe, without altering history.
    for resource, source_id, target_id, target_column in (
        ("PROPERTIES", source_ids["PROPERTIES"], property_id, PlatformMigrationStagedRow.resolution_target_id),
        ("UNITS", source_ids["UNITS"], unit_id, PlatformMigrationStagedRow.resolution_target_unit_id),
        ("TENANTS", source_ids["TENANTS"], tenant_id, PlatformMigrationStagedRow.resolution_target_tenant_user_id),
    ):
        claim = db.query(PlatformMigrationStagedRow.id).filter(
            PlatformMigrationStagedRow.organization_id == run.organization_id,
            PlatformMigrationStagedRow.provider == "YARDI",
            PlatformMigrationStagedRow.resource == resource,
            PlatformMigrationStagedRow.source_id.is_distinct_from(source_id),
            PlatformMigrationStagedRow.resolution_action == "MATCH_EXISTING",
            target_column == target_id,
        ).first()
        if claim:
            raise HTTPException(status_code=409, detail="Competing Yardi identity review blocks lease source acceptance.")
    verified_unit_rows = db.query(PlatformMigrationStagedRow).filter(
        PlatformMigrationStagedRow.run_id == run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource == "UNITS",
        PlatformMigrationStagedRow.source_id == source_ids["UNITS"],
        PlatformMigrationStagedRow.row_fingerprint == mappings["UNITS"].source_fingerprint,
        PlatformMigrationStagedRow.resolution_action == "MATCH_EXISTING",
        PlatformMigrationStagedRow.resolution_target_unit_id == unit_id,
    ).all()
    if not verified_unit_rows or any(
        item.errors or item.disposition == "INVALID" for item in verified_unit_rows
    ):
        raise HTTPException(status_code=409, detail="Exact reviewed Unit original source-parent evidence is required.")
    verified_parent_sources = {
        str((item.normalized_data or {}).get("source_property_id") or "").strip()
        for item in verified_unit_rows
    }
    if verified_parent_sources != {source_ids["PROPERTIES"]}:
        raise HTTPException(status_code=409, detail="Lease and reviewed Unit original Yardi source parents conflict.")
    stored = (row.resolution_target_id, row.resolution_target_unit_id,
              row.resolution_target_tenant_user_id)
    current = (property_id, unit_id, tenant_id)
    if row.resolution_action == "ACCEPT_RELATIONSHIP":
        if stored != current:
            raise HTTPException(status_code=409, detail="Accepted lease source identity is stale.")
        return {"row_id": row.id, "action": "ACCEPT_RELATIONSHIP",
                "replayed": True, "customer_business_mutation": False}
    row.resolution_action = "ACCEPT_RELATIONSHIP"
    row.resolution_target_id = property_id
    row.resolution_target_unit_id = unit_id
    row.resolution_target_tenant_user_id = tenant_id
    row.resolved_by_platform_user_id = current_user.id
    row.resolved_at = datetime.utcnow()
    row.correction_evidence = list(row.correction_evidence or []) + [
        {"action": "ACCEPT_RELATIONSHIP", "property_id": property_id,
         "unit_id": unit_id, "tenant_user_id": tenant_id},
    ]
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    append_audit_log(
        db, platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_staged_row", entity_id=row.id,
        action="yardi_lease_source_relationship_accepted",
        new_value={"run_id": run.id, "property_id": property_id,
                   "unit_id": unit_id, "tenant_user_id": tenant_id,
                   "customer_business_mutation": False,
                   "lease_created": False, "accounting_posted": False},
    )
    db.commit()
    return {"row_id": row.id, "action": "ACCEPT_RELATIONSHIP",
            "replayed": False, "customer_business_mutation": False}


@router.post("/runs/{run_id}/review-dry-run")
def dry_run_yardi_review(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Record a reviewed Yardi source snapshot; never authorize target commit."""
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    review = get_yardi_reconciliation(run_id, Response(), db, current_user)
    if review["staged_rows"] == 0:
        raise HTTPException(status_code=422, detail="No Yardi source rows are staged.")
    summary = {
        "provider": "YARDI", "staged_rows": review["staged_rows"],
        "invalid_rows": review["invalid_rows"],
        "unresolved_rows": review["unresolved_rows"],
        "skipped_rows": review["skipped_rows"],
        "durable_mapping_count": review["durable_mapping_count"],
        "requires_explicit_review": bool(review["invalid_rows"] or review["unresolved_rows"]),
        "customer_business_mutation": False,
        "controlled_commit_enabled": False,
    }
    fingerprint = review["review_fingerprint"]
    replayed = (
        run.last_dry_run_fingerprint == fingerprint
        and run.last_dry_run_summary == summary
    )
    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = summary
        append_audit_log(
            db, platform_user_id=current_user.id,
            organization_id=run.organization_id,
            entity_type="platform_migration_run", entity_id=run.id,
            action="yardi_review_dry_run",
            new_value={
                "review_fingerprint": fingerprint,
                "invalid_rows": review["invalid_rows"],
                "unresolved_rows": review["unresolved_rows"],
                "controlled_commit_enabled": False,
                "customer_business_mutation": False,
            },
        )
        db.commit()
    return {"run_id": run.id, "review_fingerprint": fingerprint,
            "replayed": replayed, **summary}


@router.get("/runs/{run_id}/review-dry-run")
def get_yardi_review_dry_run_status(
    run_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Recheck saved review evidence against current staging, not cached metadata."""
    run = _run(db, run_id=run_id, current_user=current_user, write=False)
    review = get_yardi_reconciliation(run_id, Response(), db, current_user)
    saved = run.last_dry_run_fingerprint
    current = review["review_fingerprint"]
    response.headers["Cache-Control"] = "no-store"
    return {
        "run_id": run.id,
        "provider": "YARDI",
        "saved_review_fingerprint": saved,
        "current_review_fingerprint": current,
        "has_saved_dry_run": saved is not None,
        "is_current": saved is not None and saved == current,
        "controlled_commit_enabled": False,
        "customer_business_mutation": False,
    }


class YardiPropertyMatchIn(BaseModel):
    target_property_id: int


def _locked_yardi_review_target(db: Session, *, organization_id: int, property_id: int):
    """Serialize competing Yardi review claims on one Property in PostgreSQL."""
    return db.query(Property.id).filter(
        Property.id == property_id,
        Property.organization_id == organization_id,
        Property.is_active.is_(True),
        Property.deleted_at.is_(None),
    ).with_for_update().first()


@router.post("/runs/{run_id}/staged-rows/{row_id}/match-property")
def match_yardi_staged_property(
    run_id: int,
    row_id: int,
    payload: YardiPropertyMatchIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Record an explicit property match decision, never mutate the property."""
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    row = db.query(PlatformMigrationStagedRow).filter(
        PlatformMigrationStagedRow.id == row_id,
        PlatformMigrationStagedRow.run_id == run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource == "PROPERTIES",
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Yardi property row not found.")
    if row.errors or row.disposition == "INVALID" or not row.source_id:
        raise HTTPException(status_code=422, detail="Invalid property source row cannot be matched.")
    if (row.resource, row.source_id) in _yardi_unresolved_identity_sources(db, run):
        raise HTTPException(
            status_code=409,
            detail="Repeated Yardi source ID requires explicit duplicate disposition before identity review.",
        )
    if row.resolution_action is not None:
        if (row.resolution_action == "MATCH_EXISTING"
                and row.resolution_target_id == payload.target_property_id):
            if _locked_yardi_review_target(db, organization_id=run.organization_id,
                                           property_id=payload.target_property_id) is None:
                raise HTTPException(status_code=409, detail="Previously reviewed Property target is inactive or archived.")
            # Revalidate recorded Property review against later durable claims.
            stale = db.query(PlatformMigrationItem.id).filter(
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "YARDI",
                PlatformMigrationItem.resource == "PROPERTIES",
                or_(
                    (PlatformMigrationItem.run_id == run.id)
                    & (PlatformMigrationItem.source_id == row.source_id)
                    & or_(
                        PlatformMigrationItem.target_entity != "PROPERTY",
                        PlatformMigrationItem.target_id != payload.target_property_id,
                        PlatformMigrationItem.source_fingerprint != row.row_fingerprint,
                    ),
                    (PlatformMigrationItem.target_entity == "PROPERTY")
                    & (PlatformMigrationItem.target_id == payload.target_property_id)
                    & or_(
                        PlatformMigrationItem.run_id != run.id,
                        PlatformMigrationItem.source_id != row.source_id,
                    ),
                ),
            ).first()
            other_review = db.query(PlatformMigrationStagedRow.id).filter(
                PlatformMigrationStagedRow.organization_id == run.organization_id,
                PlatformMigrationStagedRow.provider == "YARDI",
                PlatformMigrationStagedRow.resource == "PROPERTIES",
                PlatformMigrationStagedRow.id != row.id,
                PlatformMigrationStagedRow.resolution_action == "MATCH_EXISTING",
                PlatformMigrationStagedRow.resolution_target_id == payload.target_property_id,
            ).first()
            if stale or other_review:
                raise HTTPException(status_code=409, detail="Conflicting recorded Property identity.")
            return {"row_id": row.id, "action": "MATCH_EXISTING", "replayed": True}
        raise HTTPException(status_code=409, detail="Conflicting review decision exists.")
    if db.query(PlatformMigrationItem.id).filter(
        PlatformMigrationItem.run_id == run.id,
        PlatformMigrationItem.organization_id == run.organization_id,
        PlatformMigrationItem.provider == "YARDI",
        PlatformMigrationItem.resource == "PROPERTIES",
        PlatformMigrationItem.source_id == row.source_id,
    ).first():
        raise HTTPException(status_code=409, detail="Source is already durably mapped.")
    target = _locked_yardi_review_target(
        db, organization_id=run.organization_id,
        property_id=payload.target_property_id,
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Target property not found.")
    mapped_target_collision = db.query(PlatformMigrationItem.id).filter(
        PlatformMigrationItem.run_id == run.id,
        PlatformMigrationItem.organization_id == run.organization_id,
        PlatformMigrationItem.provider == "YARDI",
        PlatformMigrationItem.resource == "PROPERTIES",
        PlatformMigrationItem.target_entity == "PROPERTY",
        PlatformMigrationItem.target_id == payload.target_property_id,
        PlatformMigrationItem.source_id != row.source_id,
    ).first()
    if mapped_target_collision is not None:
        raise HTTPException(
            status_code=409,
            detail="Another Yardi Property source is already mapped to this target.",
        )
    cross_run_claim = db.query(PlatformMigrationItem.id).filter(
        PlatformMigrationItem.run_id != run.id,
        PlatformMigrationItem.organization_id == run.organization_id,
        PlatformMigrationItem.provider == "YARDI",
        PlatformMigrationItem.resource == "PROPERTIES",
        PlatformMigrationItem.target_entity == "PROPERTY",
        PlatformMigrationItem.target_id == payload.target_property_id,
    ).first()
    if cross_run_claim is not None:
        raise HTTPException(
            status_code=409,
            detail="Target Property is already durably mapped in another Yardi run.",
        )
    collision = db.query(PlatformMigrationStagedRow.id).filter(
        PlatformMigrationStagedRow.run_id == run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource == "PROPERTIES",
        PlatformMigrationStagedRow.id != row.id,
        PlatformMigrationStagedRow.resolution_action == "MATCH_EXISTING",
        PlatformMigrationStagedRow.resolution_target_id == payload.target_property_id,
    ).first()
    if collision is not None:
        raise HTTPException(
            status_code=409,
            detail="Another Yardi Property source already claims this target in this run.",
        )
    other_run_review_claim = db.query(PlatformMigrationStagedRow.id).filter(
        PlatformMigrationStagedRow.run_id != run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource == "PROPERTIES",
        PlatformMigrationStagedRow.resolution_action == "MATCH_EXISTING",
        PlatformMigrationStagedRow.resolution_target_id == payload.target_property_id,
    ).first()
    if other_run_review_claim is not None:
        raise HTTPException(
            status_code=409,
            detail="Target Property is already claimed by another Yardi review run.",
        )
    row.resolution_action = "MATCH_EXISTING"
    row.resolution_target_id = payload.target_property_id
    row.resolved_by_platform_user_id = current_user.id
    row.resolved_at = datetime.utcnow()
    row.correction_evidence = list(row.correction_evidence or []) + [{
        "action": "MATCH_EXISTING", "target_property_id": payload.target_property_id,
    }]
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    append_audit_log(
        db, platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_staged_row", entity_id=row.id,
        action="yardi_property_match_reviewed",
        new_value={"run_id": run.id, "target_property_id": payload.target_property_id,
                   "customer_business_mutation": False},
    )
    db.commit()
    return {"row_id": row.id, "action": "MATCH_EXISTING", "replayed": False}


class YardiOwnerMatchIn(BaseModel):
    target_owner_user_id: int


@router.post("/runs/{run_id}/staged-rows/{row_id}/match-owner")
def match_yardi_staged_owner(
    run_id: int,
    row_id: int,
    payload: YardiOwnerMatchIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Review an existing owner identity, without login or lease creation."""
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    row = db.query(PlatformMigrationStagedRow).filter(
        PlatformMigrationStagedRow.id == row_id,
        PlatformMigrationStagedRow.run_id == run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource == "OWNERS",
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Yardi Owner row not found.")
    if row.errors or row.disposition == "INVALID" or not row.source_id:
        raise HTTPException(status_code=422, detail="Invalid Owner source row cannot be matched.")
    if (row.resource, row.source_id) in _yardi_unresolved_identity_sources(db, run):
        raise HTTPException(
            status_code=409,
            detail="Repeated Yardi source ID requires explicit duplicate disposition before identity review.",
        )
    replay = (
        row.resolution_action == "MATCH_EXISTING"
        and row.resolution_target_owner_user_id == payload.target_owner_user_id
    )
    if row.resolution_action is not None and not replay:
        raise HTTPException(status_code=409, detail="Conflicting Owner review decision.")
    target = db.query(User.id).filter(
        User.id == payload.target_owner_user_id,
        User.organization_id == run.organization_id,
        User.role == UserRole.OWNER,
        User.is_active.is_(True),
        User.deleted_at.is_(None),
    ).with_for_update().first()
    if target is None:
        raise HTTPException(status_code=404, detail="Existing Owner user target unavailable.")
    collision = db.query(PlatformMigrationItem.id).filter(
        PlatformMigrationItem.organization_id == run.organization_id,
        PlatformMigrationItem.provider == "YARDI",
        PlatformMigrationItem.resource == "OWNERS",
        or_(
            (PlatformMigrationItem.target_entity == "OWNER_USER")
            & (PlatformMigrationItem.target_id == target.id)
            & ((PlatformMigrationItem.run_id != run.id)
               | (PlatformMigrationItem.source_id != row.source_id)),
            (PlatformMigrationItem.run_id == run.id)
            & (PlatformMigrationItem.source_id == row.source_id)
            & ((PlatformMigrationItem.target_entity != "OWNER_USER")
               | (PlatformMigrationItem.target_id != target.id)
               | (PlatformMigrationItem.source_fingerprint != row.row_fingerprint)),
        ),
    ).first()
    if collision:
        raise HTTPException(status_code=409, detail="Conflicting durable Yardi Owner mapping.")
    claimed = db.query(PlatformMigrationStagedRow.id).filter(
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource == "OWNERS",
        PlatformMigrationStagedRow.id != row.id,
        PlatformMigrationStagedRow.resolution_action == "MATCH_EXISTING",
        PlatformMigrationStagedRow.resolution_target_owner_user_id == target.id,
    ).first()
    if claimed:
        raise HTTPException(status_code=409, detail="Another Yardi Owner review claims this user.")
    # Historical reviews must not conceal a later competing staff claim.
    if replay:
        return {"row_id": row.id, "action": "MATCH_EXISTING", "replayed": True}
    row.resolution_action = "MATCH_EXISTING"
    row.resolution_target_owner_user_id = target.id
    row.resolved_by_platform_user_id = current_user.id
    row.resolved_at = datetime.utcnow()
    row.correction_evidence = list(row.correction_evidence or []) + [
        {"action": "MATCH_EXISTING", "target_owner_user_id": target.id},
    ]
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    append_audit_log(
        db, platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_staged_row", entity_id=row.id,
        action="yardi_owner_match_reviewed",
        new_value={"run_id": run.id, "target_owner_user_id": target.id,
                   "customer_business_mutation": False},
    )
    db.commit()
    return {"row_id": row.id, "action": "MATCH_EXISTING", "replayed": False}


class YardiTenantMatchIn(BaseModel):
    target_tenant_user_id: int


@router.post("/runs/{run_id}/staged-rows/{row_id}/match-tenant")
def match_yardi_staged_tenant(
    run_id: int,
    row_id: int,
    payload: YardiTenantMatchIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Review an existing tenant identity, without login or lease creation."""
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    row = db.query(PlatformMigrationStagedRow).filter(
        PlatformMigrationStagedRow.id == row_id,
        PlatformMigrationStagedRow.run_id == run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource == "TENANTS",
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Yardi Tenant row not found.")
    if row.errors or row.disposition == "INVALID" or not row.source_id:
        raise HTTPException(status_code=422, detail="Invalid Tenant source row cannot be matched.")
    if (row.resource, row.source_id) in _yardi_unresolved_identity_sources(db, run):
        raise HTTPException(
            status_code=409,
            detail="Repeated Yardi source ID requires explicit duplicate disposition before identity review.",
        )
    replay = (
        row.resolution_action == "MATCH_EXISTING"
        and row.resolution_target_tenant_user_id == payload.target_tenant_user_id
    )
    if row.resolution_action is not None and not replay:
        raise HTTPException(status_code=409, detail="Conflicting Tenant review decision.")
    target = db.query(User.id).filter(
        User.id == payload.target_tenant_user_id,
        User.organization_id == run.organization_id,
        User.role == UserRole.TENANT,
        User.is_active.is_(True),
        User.deleted_at.is_(None),
    ).with_for_update().first()
    if target is None:
        raise HTTPException(status_code=404, detail="Existing Tenant user target unavailable.")
    collision = db.query(PlatformMigrationItem.id).filter(
        PlatformMigrationItem.organization_id == run.organization_id,
        PlatformMigrationItem.provider == "YARDI",
        PlatformMigrationItem.resource == "TENANTS",
        or_(
            (PlatformMigrationItem.target_entity == "TENANT_USER")
            & (PlatformMigrationItem.target_id == target.id)
            & ((PlatformMigrationItem.run_id != run.id)
               | (PlatformMigrationItem.source_id != row.source_id)),
            (PlatformMigrationItem.run_id == run.id)
            & (PlatformMigrationItem.source_id == row.source_id)
            & ((PlatformMigrationItem.target_entity != "TENANT_USER")
               | (PlatformMigrationItem.target_id != target.id)
               | (PlatformMigrationItem.source_fingerprint != row.row_fingerprint)),
        ),
    ).first()
    if collision:
        raise HTTPException(status_code=409, detail="Conflicting durable Yardi Tenant mapping.")
    claimed = db.query(PlatformMigrationStagedRow.id).filter(
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource == "TENANTS",
        PlatformMigrationStagedRow.id != row.id,
        PlatformMigrationStagedRow.resolution_action == "MATCH_EXISTING",
        PlatformMigrationStagedRow.resolution_target_tenant_user_id == target.id,
    ).first()
    if claimed:
        raise HTTPException(status_code=409, detail="Another Yardi Tenant review claims this user.")
    # Historical reviews must not conceal a later competing staff claim.
    if replay:
        return {"row_id": row.id, "action": "MATCH_EXISTING", "replayed": True}
    row.resolution_action = "MATCH_EXISTING"
    row.resolution_target_tenant_user_id = target.id
    row.resolved_by_platform_user_id = current_user.id
    row.resolved_at = datetime.utcnow()
    row.correction_evidence = list(row.correction_evidence or []) + [
        {"action": "MATCH_EXISTING", "target_tenant_user_id": target.id},
    ]
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    append_audit_log(
        db, platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_staged_row", entity_id=row.id,
        action="yardi_tenant_match_reviewed",
        new_value={"run_id": run.id, "target_tenant_user_id": target.id,
                   "customer_business_mutation": False},
    )
    db.commit()
    return {"row_id": row.id, "action": "MATCH_EXISTING", "replayed": False}


class YardiVendorMatchIn(BaseModel):
    target_vendor_id: int


@router.post("/runs/{run_id}/staged-rows/{row_id}/match-vendor")
def match_yardi_staged_vendor(
    run_id: int,
    row_id: int,
    payload: YardiVendorMatchIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Explicitly review existing vendor identity; do not alter customer vendors."""
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    row = db.query(PlatformMigrationStagedRow).filter(
        PlatformMigrationStagedRow.id == row_id,
        PlatformMigrationStagedRow.run_id == run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource == "VENDORS",
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Yardi Vendor row not found.")
    if row.errors or row.disposition == "INVALID" or not row.source_id:
        raise HTTPException(status_code=422, detail="Invalid Vendor source row cannot be matched.")
    if (row.resource, row.source_id) in _yardi_unresolved_identity_sources(db, run):
        raise HTTPException(
            status_code=409,
            detail="Repeated Yardi source ID requires explicit duplicate disposition before identity review.",
        )
    replay = (
        row.resolution_action == "MATCH_EXISTING"
        and row.resolution_target_vendor_id == payload.target_vendor_id
    )
    if row.resolution_action is not None and not replay:
        raise HTTPException(status_code=409, detail="Conflicting Vendor review decision.")
    target = db.query(Vendor.id).filter(
        Vendor.id == payload.target_vendor_id,
        Vendor.organization_id == run.organization_id,
        Vendor.deleted_at.is_(None),
    ).with_for_update().first()
    if target is None:
        raise HTTPException(status_code=404, detail="Existing Vendor target unavailable in this organization.")
    conflicting = db.query(PlatformMigrationItem.id).filter(
        PlatformMigrationItem.organization_id == run.organization_id,
        PlatformMigrationItem.provider == "YARDI",
        PlatformMigrationItem.resource == "VENDORS",
        or_(
            (PlatformMigrationItem.target_entity == "VENDOR")
            & (PlatformMigrationItem.target_id == target.id)
            & ((PlatformMigrationItem.run_id != run.id)
               | (PlatformMigrationItem.source_id != row.source_id)),
            (PlatformMigrationItem.run_id == run.id)
            & (PlatformMigrationItem.source_id == row.source_id)
            & ((PlatformMigrationItem.target_entity != "VENDOR")
               | (PlatformMigrationItem.target_id != target.id)
               | (PlatformMigrationItem.source_fingerprint != row.row_fingerprint)),
        ),
    ).first()
    if conflicting:
        raise HTTPException(status_code=409, detail="Conflicting durable Yardi Vendor mapping.")
    claim = db.query(PlatformMigrationStagedRow.id).filter(
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource == "VENDORS",
        PlatformMigrationStagedRow.id != row.id,
        PlatformMigrationStagedRow.resolution_action == "MATCH_EXISTING",
        PlatformMigrationStagedRow.resolution_target_vendor_id == target.id,
    ).first()
    if claim:
        raise HTTPException(status_code=409, detail="Another Yardi Vendor review claims this target.")
    # Historical reviews must not conceal a later competing staff claim.
    if replay:
        return {"row_id": row.id, "action": "MATCH_EXISTING", "replayed": True}
    row.resolution_action = "MATCH_EXISTING"
    row.resolution_target_vendor_id = target.id
    row.resolved_by_platform_user_id = current_user.id
    row.resolved_at = datetime.utcnow()
    row.correction_evidence = list(row.correction_evidence or []) + [
        {"action": "MATCH_EXISTING", "target_vendor_id": target.id},
    ]
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    append_audit_log(
        db, platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_staged_row", entity_id=row.id,
        action="yardi_vendor_match_reviewed",
        new_value={"run_id": run.id, "target_vendor_id": target.id,
                   "customer_business_mutation": False},
    )
    db.commit()
    return {"row_id": row.id, "action": "MATCH_EXISTING", "replayed": False}


class YardiUnitMatchIn(BaseModel):
    target_unit_id: int


@router.post("/runs/{run_id}/staged-rows/{row_id}/match-unit")
def match_yardi_staged_unit(
    run_id: int,
    row_id: int,
    payload: YardiUnitMatchIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Review an existing Unit identity; never mutate customer Unit records."""
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    row = db.query(PlatformMigrationStagedRow).filter(
        PlatformMigrationStagedRow.id == row_id,
        PlatformMigrationStagedRow.run_id == run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource == "UNITS",
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Yardi Unit row not found.")
    if row.errors or row.disposition == "INVALID" or not row.source_id:
        raise HTTPException(status_code=422, detail="Invalid Unit source row cannot be matched.")
    if (row.resource, row.source_id) in _yardi_unresolved_identity_sources(db, run):
        raise HTTPException(
            status_code=409,
            detail="Repeated Yardi source ID requires explicit duplicate disposition before identity review.",
        )
    replay = row.resolution_action == "MATCH_EXISTING" and row.resolution_target_unit_id == payload.target_unit_id
    if row.resolution_action is not None and not replay:
        raise HTTPException(status_code=409, detail="Conflicting Unit review decision.")
    source_property_id = str((row.normalized_data or {}).get("source_property_id") or "").strip()
    parent = db.query(PlatformMigrationItem).filter(
        PlatformMigrationItem.run_id == run.id,
        PlatformMigrationItem.organization_id == run.organization_id,
        PlatformMigrationItem.provider == "YARDI",
        PlatformMigrationItem.resource == "PROPERTIES",
        PlatformMigrationItem.source_id == source_property_id,
        PlatformMigrationItem.target_entity == "PROPERTY",
    ).first()
    if parent is None:
        raise HTTPException(status_code=409, detail="Verified same-run parent Property binding required.")
    target = db.query(Unit).join(Property, Unit.property_id == Property.id).filter(
        Unit.id == payload.target_unit_id,
        Unit.property_id == parent.target_id,
        Property.organization_id == run.organization_id,
        Unit.is_active.is_(True), Unit.deleted_at.is_(None),
        Property.is_active.is_(True), Property.deleted_at.is_(None),
    ).with_for_update(of=Unit).first()
    if target is None:
        raise HTTPException(status_code=404, detail="Unit target is not in the mapped parent Property.")
    claim = db.query(PlatformMigrationStagedRow.id).filter(
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource == "UNITS",
        PlatformMigrationStagedRow.id != row.id,
        PlatformMigrationStagedRow.resolution_action == "MATCH_EXISTING",
        PlatformMigrationStagedRow.resolution_target_unit_id == target.id,
    ).first()
    if claim is not None:
        raise HTTPException(status_code=409, detail="Existing Yardi Unit review already claims target.")
    # A replay also rechecks the current exact source and every staff claim.
    if replay:
        conflict = db.query(PlatformMigrationItem.id).filter(
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "YARDI",
            PlatformMigrationItem.resource == "UNITS",
            or_(
                (PlatformMigrationItem.run_id == run.id)
                & (PlatformMigrationItem.source_id == row.source_id)
                & or_(
                    PlatformMigrationItem.target_entity != "UNIT",
                    PlatformMigrationItem.target_id != target.id,
                    PlatformMigrationItem.source_fingerprint != row.row_fingerprint,
                ),
                (PlatformMigrationItem.target_entity == "UNIT")
                & (PlatformMigrationItem.target_id == target.id)
                & or_(PlatformMigrationItem.run_id != run.id,
                      PlatformMigrationItem.source_id != row.source_id),
            ),
        ).first()
        if conflict:
            raise HTTPException(status_code=409, detail="Replayed Unit target has conflicting durable mapping.")
        return {"row_id": row.id, "action": "MATCH_EXISTING", "replayed": True}
    conflict = db.query(PlatformMigrationItem.id).filter(
        PlatformMigrationItem.organization_id == run.organization_id,
        PlatformMigrationItem.provider == "YARDI",
        PlatformMigrationItem.resource == "UNITS",
        or_(
            (PlatformMigrationItem.run_id == run.id) & (PlatformMigrationItem.source_id == row.source_id),
            (PlatformMigrationItem.target_entity == "UNIT") & (PlatformMigrationItem.target_id == target.id),
        ),
    ).first()
    if conflict is not None:
        raise HTTPException(status_code=409, detail="Conflicting durable Unit source or target mapping.")
    row.resolution_action = "MATCH_EXISTING"
    row.resolution_target_unit_id = target.id
    row.resolved_by_platform_user_id = current_user.id
    row.resolved_at = datetime.utcnow()
    row.correction_evidence = list(row.correction_evidence or []) + [{"action": "MATCH_EXISTING", "target_unit_id": target.id}]
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    append_audit_log(
        db, platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_staged_row", entity_id=row.id,
        action="yardi_unit_match_reviewed",
        new_value={"run_id": run.id, "target_unit_id": target.id, "customer_business_mutation": False},
    )
    db.commit()
    return {"row_id": row.id, "action": "MATCH_EXISTING", "replayed": False}


class YardiReviewedPropertyBindingIn(BaseModel):
    review_fingerprint: str


@router.post("/runs/{run_id}/bind-reviewed-units")
def bind_yardi_reviewed_unit_matches(
    run_id: int,
    payload: YardiReviewedPropertyBindingIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Persist reviewed Unit identity mappings only; never write customer Units."""
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    rows = db.query(PlatformMigrationStagedRow).filter(
        PlatformMigrationStagedRow.run_id == run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource == "UNITS",
    ).order_by(PlatformMigrationStagedRow.id.asc()).all()
    if not rows:
        raise HTTPException(status_code=422, detail="No Yardi Units are staged.")
    matches, sources, targets = [], set(), set()
    for row in rows:
        # An explicitly reason-coded SKIP excludes a rejected source version.
        # Only non-skipped invalid rows must block durable identity binding.
        if row.resolution_action == "SKIP":
            continue
        if row.errors or row.disposition == "INVALID":
            raise HTTPException(status_code=409, detail="Invalid Unit staging blocks binding.")
        if row.resolution_action != "MATCH_EXISTING" or not row.source_id or row.resolution_target_unit_id is None:
            raise HTTPException(status_code=409, detail="Every non-skipped Unit requires explicit review.")
        if row.source_id in sources or row.resolution_target_unit_id in targets:
            raise HTTPException(status_code=409, detail="Duplicate Unit source or target.")
        sources.add(row.source_id)
        targets.add(row.resolution_target_unit_id)
        matches.append(row)
    if not matches:
        raise HTTPException(status_code=422, detail="No reviewed Units to bind.")
    already = 0
    for row in matches:
        mapped = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "YARDI",
            PlatformMigrationItem.resource == "UNITS",
            PlatformMigrationItem.source_id == row.source_id,
        ).first()
        if mapped:
            if (mapped.target_entity != "UNIT" or mapped.target_id != row.resolution_target_unit_id
                    or mapped.source_fingerprint != row.row_fingerprint):
                raise HTTPException(status_code=409, detail="Conflicting durable Unit source mapping.")
            already += 1
    if already and already != len(matches):
        raise HTTPException(status_code=409, detail="Partial Unit bindings require reconciliation.")
    if not already:
        current = get_yardi_reconciliation(run_id, Response(), db, current_user)["review_fingerprint"]
        if (not run.last_dry_run_fingerprint or payload.review_fingerprint != current
                or run.last_dry_run_fingerprint != current):
            raise HTTPException(status_code=409, detail="Current exact-fingerprint Unit dry run required.")
    ordered = sorted(matches, key=lambda row: row.resolution_target_unit_id)
    for row in ordered:
        parent_source = str((row.normalized_data or {}).get("source_property_id") or "").strip()
        parent = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "YARDI",
            PlatformMigrationItem.resource == "PROPERTIES",
            PlatformMigrationItem.source_id == parent_source,
            PlatformMigrationItem.target_entity == "PROPERTY",
        ).first()
        if parent is None:
            raise HTTPException(status_code=409, detail="Durable same-run parent Property mapping missing.")
        target = db.query(Unit.id).join(Property, Unit.property_id == Property.id).filter(
            Unit.id == row.resolution_target_unit_id,
            Unit.property_id == parent.target_id,
            Property.organization_id == run.organization_id,
            Unit.is_active.is_(True), Unit.deleted_at.is_(None),
            Property.is_active.is_(True), Property.deleted_at.is_(None),
        ).with_for_update(of=Unit).first()
        if target is None:
            raise HTTPException(status_code=409, detail="Reviewed Unit target or parent changed.")
        staff_claim = db.query(PlatformMigrationStagedRow.id).filter(
            PlatformMigrationStagedRow.organization_id == run.organization_id,
            PlatformMigrationStagedRow.provider == "YARDI",
            PlatformMigrationStagedRow.resource == "UNITS",
            PlatformMigrationStagedRow.source_id.is_distinct_from(row.source_id),
            PlatformMigrationStagedRow.resolution_action == "MATCH_EXISTING",
            PlatformMigrationStagedRow.resolution_target_unit_id == target.id,
        ).first()
        if staff_claim:
            raise HTTPException(status_code=409, detail="Another Yardi Unit review claims this target.")
        collision = db.query(PlatformMigrationItem.id).filter(
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "YARDI",
            PlatformMigrationItem.resource == "UNITS",
            PlatformMigrationItem.target_entity == "UNIT",
            PlatformMigrationItem.target_id == row.resolution_target_unit_id,
            or_(PlatformMigrationItem.run_id != run.id,
                PlatformMigrationItem.source_id != row.source_id),
        ).first()
        if collision:
            raise HTTPException(status_code=409, detail="Unit target already bound to another source.")
    if already:
        return {"run_id": run.id, "provider": "YARDI", "bound": 0,
                "replayed": True, "customer_business_mutation": False}
    for row in ordered:
        db.add(PlatformMigrationItem(
            run_id=run.id, organization_id=run.organization_id,
            provider="YARDI", resource="UNITS",
            source_id=row.source_id, target_entity="UNIT",
            target_id=row.resolution_target_unit_id,
            source_fingerprint=row.row_fingerprint,
            created_by_platform_user_id=current_user.id,
        ))
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    append_audit_log(
        db, platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_run", entity_id=run.id,
        action="yardi_unit_existing_bindings_committed",
        new_value={"matched_existing": len(matches), "customer_business_mutation": False},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Durable Unit mapping conflicted.") from exc
    return {"run_id": run.id, "provider": "YARDI", "bound": len(matches),
            "replayed": False, "customer_business_mutation": False}


@router.post("/runs/{run_id}/bind-reviewed-vendors")
def bind_yardi_reviewed_vendor_matches(
    run_id: int,
    payload: YardiReviewedPropertyBindingIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Commit reviewed source-to-existing-Vendor metadata only."""
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    rows = db.query(PlatformMigrationStagedRow).filter(
        PlatformMigrationStagedRow.run_id == run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource == "VENDORS",
    ).order_by(PlatformMigrationStagedRow.id.asc()).all()
    if not rows:
        raise HTTPException(status_code=422, detail="No Yardi Vendor rows staged.")
    matches, sources, targets = [], set(), set()
    for row in rows:
        # An explicitly reason-coded SKIP excludes a rejected source version.
        # Only non-skipped invalid rows must block durable identity binding.
        if row.resolution_action == "SKIP":
            continue
        if row.errors or row.disposition == "INVALID":
            raise HTTPException(status_code=409, detail="Invalid Vendor source staging blocks binding.")
        target_id = row.resolution_target_vendor_id
        if row.resolution_action != "MATCH_EXISTING" or not row.source_id or target_id is None:
            raise HTTPException(status_code=409, detail="All non-skipped Vendors require explicit review.")
        if row.source_id in sources or target_id in targets:
            raise HTTPException(status_code=409, detail="Duplicate Vendor source or target.")
        sources.add(row.source_id)
        targets.add(target_id)
        matches.append(row)
    if not matches:
        raise HTTPException(status_code=422, detail="No reviewed existing Vendors to bind.")
    already = 0
    for row in matches:
        mapped = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "YARDI",
            PlatformMigrationItem.resource == "VENDORS",
            PlatformMigrationItem.source_id == row.source_id,
        ).first()
        if mapped:
            if (mapped.target_entity != "VENDOR" or mapped.target_id != row.resolution_target_vendor_id
                    or mapped.source_fingerprint != row.row_fingerprint):
                raise HTTPException(status_code=409, detail="Conflicting durable Vendor source mapping.")
            already += 1
    if already and already != len(matches):
        raise HTTPException(status_code=409, detail="Partial Vendor bindings require reconciliation.")
    if not already:
        current = get_yardi_reconciliation(run_id, Response(), db, current_user)["review_fingerprint"]
        if (not run.last_dry_run_fingerprint or payload.review_fingerprint != current
                or run.last_dry_run_fingerprint != current):
            raise HTTPException(status_code=409, detail="Current exact-fingerprint Vendor dry run required.")
    ordered = sorted(matches, key=lambda row: row.resolution_target_vendor_id)
    for row in ordered:
        target = db.query(Vendor.id).filter(
            Vendor.id == row.resolution_target_vendor_id,
            Vendor.organization_id == run.organization_id,
            Vendor.deleted_at.is_(None),
        ).with_for_update().first()
        if not target:
            raise HTTPException(status_code=409, detail="Reviewed Vendor target no longer exists.")
        # A later reviewed source may claim this same customer target after
        # the original review or durable binding. Check on first bind and replay.
        staff_claim = db.query(PlatformMigrationStagedRow.id).filter(
            PlatformMigrationStagedRow.organization_id == run.organization_id,
            PlatformMigrationStagedRow.provider == "YARDI",
            PlatformMigrationStagedRow.resource == "VENDORS",
            PlatformMigrationStagedRow.source_id.is_distinct_from(row.source_id),
            PlatformMigrationStagedRow.resolution_action == "MATCH_EXISTING",
            PlatformMigrationStagedRow.resolution_target_vendor_id == target.id,
        ).first()
        if staff_claim:
            raise HTTPException(status_code=409, detail="Another Yardi Vendor review claims this target.")
        collision = db.query(PlatformMigrationItem.id).filter(
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "YARDI",
            PlatformMigrationItem.resource == "VENDORS",
            PlatformMigrationItem.target_entity == "VENDOR",
            PlatformMigrationItem.target_id == target.id,
            or_(PlatformMigrationItem.run_id != run.id,
                PlatformMigrationItem.source_id != row.source_id),
        ).first()
        if collision:
            raise HTTPException(status_code=409, detail="Vendor target has conflicting source binding.")
    if already:
        return {"run_id": run.id, "provider": "YARDI", "bound": 0,
                "replayed": True, "customer_business_mutation": False}
    for row in ordered:
        db.add(PlatformMigrationItem(
            run_id=run.id, organization_id=run.organization_id,
            provider="YARDI", resource="VENDORS",
            source_id=row.source_id, target_entity="VENDOR",
            target_id=row.resolution_target_vendor_id,
            source_fingerprint=row.row_fingerprint,
            created_by_platform_user_id=current_user.id,
        ))
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    append_audit_log(
        db, platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_run", entity_id=run.id,
        action="yardi_vendor_existing_bindings_committed",
        new_value={"matched_existing": len(matches), "customer_business_mutation": False},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Durable Vendor mapping conflicted.") from exc
    return {"run_id": run.id, "provider": "YARDI", "bound": len(matches),
            "replayed": False, "customer_business_mutation": False}


@router.post("/runs/{run_id}/bind-reviewed-owners")
def bind_yardi_reviewed_owner_matches(
    run_id: int,
    payload: YardiReviewedPropertyBindingIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Persist owner-user identity mapping metadata without changing users or leases."""
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    rows = db.query(PlatformMigrationStagedRow).filter(
        PlatformMigrationStagedRow.run_id == run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource == "OWNERS",
    ).order_by(PlatformMigrationStagedRow.id.asc()).all()
    if not rows:
        raise HTTPException(status_code=422, detail="No Yardi Owner rows staged.")
    matches, sources, targets = [], set(), set()
    for row in rows:
        # An explicitly reason-coded SKIP excludes a rejected source version.
        # Only non-skipped invalid rows must block durable identity binding.
        if row.resolution_action == "SKIP":
            continue
        if row.errors or row.disposition == "INVALID":
            raise HTTPException(status_code=409, detail="Invalid Owner source staging blocks binding.")
        target_id = row.resolution_target_owner_user_id
        if row.resolution_action != "MATCH_EXISTING" or not row.source_id or target_id is None:
            raise HTTPException(status_code=409, detail="All non-skipped Owners require explicit review.")
        if row.source_id in sources or target_id in targets:
            raise HTTPException(status_code=409, detail="Duplicate Owner source or target.")
        sources.add(row.source_id)
        targets.add(target_id)
        matches.append(row)
    if not matches:
        raise HTTPException(status_code=422, detail="No reviewed existing Owners to bind.")
    already = 0
    for row in matches:
        mapped = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "YARDI",
            PlatformMigrationItem.resource == "OWNERS",
            PlatformMigrationItem.source_id == row.source_id,
        ).first()
        if mapped:
            if (mapped.target_entity != "OWNER_USER" or mapped.target_id != row.resolution_target_owner_user_id
                    or mapped.source_fingerprint != row.row_fingerprint):
                raise HTTPException(status_code=409, detail="Conflicting durable Owner source mapping.")
            already += 1
    if already and already != len(matches):
        raise HTTPException(status_code=409, detail="Partial Owner bindings require reconciliation.")
    if not already:
        current = get_yardi_reconciliation(run_id, Response(), db, current_user)["review_fingerprint"]
        if (not run.last_dry_run_fingerprint or payload.review_fingerprint != current
                or run.last_dry_run_fingerprint != current):
            raise HTTPException(status_code=409, detail="Current exact-fingerprint Owner dry run required.")
    ordered = sorted(matches, key=lambda row: row.resolution_target_owner_user_id)
    for row in ordered:
        target = db.query(User.id).filter(
            User.id == row.resolution_target_owner_user_id,
            User.organization_id == run.organization_id,
            User.role == UserRole.OWNER,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        ).with_for_update().first()
        if target is None:
            raise HTTPException(status_code=409, detail="Reviewed Owner user unavailable.")
        # A later reviewed source may claim this same customer target after
        # the original review or durable binding. Check on first bind and replay.
        staff_claim = db.query(PlatformMigrationStagedRow.id).filter(
            PlatformMigrationStagedRow.organization_id == run.organization_id,
            PlatformMigrationStagedRow.provider == "YARDI",
            PlatformMigrationStagedRow.resource == "OWNERS",
            PlatformMigrationStagedRow.source_id.is_distinct_from(row.source_id),
            PlatformMigrationStagedRow.resolution_action == "MATCH_EXISTING",
            PlatformMigrationStagedRow.resolution_target_owner_user_id == target.id,
        ).first()
        if staff_claim:
            raise HTTPException(status_code=409, detail="Another Yardi Owner review claims this target.")
        collision = db.query(PlatformMigrationItem.id).filter(
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "YARDI",
            PlatformMigrationItem.resource == "OWNERS",
            PlatformMigrationItem.target_entity == "OWNER_USER",
            PlatformMigrationItem.target_id == target.id,
            or_(PlatformMigrationItem.run_id != run.id,
                PlatformMigrationItem.source_id != row.source_id),
        ).first()
        if collision:
            raise HTTPException(status_code=409, detail="Owner user has conflicting source binding.")
    if already:
        return {"run_id": run.id, "provider": "YARDI", "bound": 0,
                "replayed": True, "customer_business_mutation": False}
    for row in ordered:
        db.add(PlatformMigrationItem(
            run_id=run.id, organization_id=run.organization_id,
            provider="YARDI", resource="OWNERS",
            source_id=row.source_id, target_entity="OWNER_USER",
            target_id=row.resolution_target_owner_user_id,
            source_fingerprint=row.row_fingerprint,
            created_by_platform_user_id=current_user.id,
        ))
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    append_audit_log(
        db, platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_run", entity_id=run.id,
        action="yardi_owner_existing_bindings_committed",
        new_value={"matched_existing": len(matches), "customer_business_mutation": False},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Durable Owner mapping conflicted.") from exc
    return {"run_id": run.id, "provider": "YARDI", "bound": len(matches),
            "replayed": False, "customer_business_mutation": False}


@router.post("/runs/{run_id}/bind-reviewed-tenants")
def bind_yardi_reviewed_tenant_matches(
    run_id: int,
    payload: YardiReviewedPropertyBindingIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Persist tenant-user identity mapping metadata without changing users or leases."""
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    rows = db.query(PlatformMigrationStagedRow).filter(
        PlatformMigrationStagedRow.run_id == run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource == "TENANTS",
    ).order_by(PlatformMigrationStagedRow.id.asc()).all()
    if not rows:
        raise HTTPException(status_code=422, detail="No Yardi Tenant rows staged.")
    matches, sources, targets = [], set(), set()
    for row in rows:
        # An explicitly reason-coded SKIP excludes a rejected source version.
        # Only non-skipped invalid rows must block durable identity binding.
        if row.resolution_action == "SKIP":
            continue
        if row.errors or row.disposition == "INVALID":
            raise HTTPException(status_code=409, detail="Invalid Tenant source staging blocks binding.")
        target_id = row.resolution_target_tenant_user_id
        if row.resolution_action != "MATCH_EXISTING" or not row.source_id or target_id is None:
            raise HTTPException(status_code=409, detail="All non-skipped Tenants require explicit review.")
        if row.source_id in sources or target_id in targets:
            raise HTTPException(status_code=409, detail="Duplicate Tenant source or target.")
        sources.add(row.source_id)
        targets.add(target_id)
        matches.append(row)
    if not matches:
        raise HTTPException(status_code=422, detail="No reviewed existing Tenants to bind.")
    already = 0
    for row in matches:
        mapped = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "YARDI",
            PlatformMigrationItem.resource == "TENANTS",
            PlatformMigrationItem.source_id == row.source_id,
        ).first()
        if mapped:
            if (mapped.target_entity != "TENANT_USER" or mapped.target_id != row.resolution_target_tenant_user_id
                    or mapped.source_fingerprint != row.row_fingerprint):
                raise HTTPException(status_code=409, detail="Conflicting durable Tenant source mapping.")
            already += 1
    if already and already != len(matches):
        raise HTTPException(status_code=409, detail="Partial Tenant bindings require reconciliation.")
    if not already:
        current = get_yardi_reconciliation(run_id, Response(), db, current_user)["review_fingerprint"]
        if (not run.last_dry_run_fingerprint or payload.review_fingerprint != current
                or run.last_dry_run_fingerprint != current):
            raise HTTPException(status_code=409, detail="Current exact-fingerprint Tenant dry run required.")
    ordered = sorted(matches, key=lambda row: row.resolution_target_tenant_user_id)
    for row in ordered:
        target = db.query(User.id).filter(
            User.id == row.resolution_target_tenant_user_id,
            User.organization_id == run.organization_id,
            User.role == UserRole.TENANT,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        ).with_for_update().first()
        if target is None:
            raise HTTPException(status_code=409, detail="Reviewed Tenant user unavailable.")
        # A later reviewed source may claim this same customer target after
        # the original review or durable binding. Check on first bind and replay.
        staff_claim = db.query(PlatformMigrationStagedRow.id).filter(
            PlatformMigrationStagedRow.organization_id == run.organization_id,
            PlatformMigrationStagedRow.provider == "YARDI",
            PlatformMigrationStagedRow.resource == "TENANTS",
            PlatformMigrationStagedRow.source_id.is_distinct_from(row.source_id),
            PlatformMigrationStagedRow.resolution_action == "MATCH_EXISTING",
            PlatformMigrationStagedRow.resolution_target_tenant_user_id == target.id,
        ).first()
        if staff_claim:
            raise HTTPException(status_code=409, detail="Another Yardi Tenant review claims this target.")
        collision = db.query(PlatformMigrationItem.id).filter(
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "YARDI",
            PlatformMigrationItem.resource == "TENANTS",
            PlatformMigrationItem.target_entity == "TENANT_USER",
            PlatformMigrationItem.target_id == target.id,
            or_(PlatformMigrationItem.run_id != run.id,
                PlatformMigrationItem.source_id != row.source_id),
        ).first()
        if collision:
            raise HTTPException(status_code=409, detail="Tenant user has conflicting source binding.")
    if already:
        return {"run_id": run.id, "provider": "YARDI", "bound": 0,
                "replayed": True, "customer_business_mutation": False}
    for row in ordered:
        db.add(PlatformMigrationItem(
            run_id=run.id, organization_id=run.organization_id,
            provider="YARDI", resource="TENANTS",
            source_id=row.source_id, target_entity="TENANT_USER",
            target_id=row.resolution_target_tenant_user_id,
            source_fingerprint=row.row_fingerprint,
            created_by_platform_user_id=current_user.id,
        ))
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    append_audit_log(
        db, platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_run", entity_id=run.id,
        action="yardi_tenant_existing_bindings_committed",
        new_value={"matched_existing": len(matches), "customer_business_mutation": False},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Durable Tenant mapping conflicted.") from exc
    return {"run_id": run.id, "provider": "YARDI", "bound": len(matches),
            "replayed": False, "customer_business_mutation": False}


@router.post("/runs/{run_id}/properties/bind-reviewed-matches")
def bind_yardi_reviewed_property_matches(
    run_id: int,
    payload: YardiReviewedPropertyBindingIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    """Bind explicitly reviewed Yardi Property source IDs to existing targets only.

    No Property rows are created, modified or deleted. Source-to-target mappings
    are migration metadata, and a fresh reviewed snapshot is mandatory.
    """
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    rows = db.query(PlatformMigrationStagedRow).filter(
        PlatformMigrationStagedRow.run_id == run.id,
        PlatformMigrationStagedRow.organization_id == run.organization_id,
        PlatformMigrationStagedRow.provider == "YARDI",
        PlatformMigrationStagedRow.resource == "PROPERTIES",
    ).order_by(PlatformMigrationStagedRow.id.asc()).all()
    if not rows:
        raise HTTPException(status_code=422, detail="No Yardi Property rows are staged.")
    matches = []
    seen_sources = set()
    seen_targets = set()
    for row in rows:
        # An explicitly reason-coded SKIP excludes a rejected source version.
        # Only non-skipped invalid rows must block durable identity binding.
        if row.resolution_action == "SKIP":
            continue
        if row.errors or row.disposition == "INVALID":
            raise HTTPException(status_code=409, detail="Invalid Property staging blocks binding.")
        if row.resolution_action != "MATCH_EXISTING" or not row.source_id or row.resolution_target_id is None:
            raise HTTPException(status_code=409, detail="All non-skipped Properties require explicit existing-target review.")
        if row.source_id in seen_sources or row.resolution_target_id in seen_targets:
            raise HTTPException(status_code=409, detail="Duplicate source or target Property identity blocks binding.")
        seen_sources.add(row.source_id)
        seen_targets.add(row.resolution_target_id)
        matches.append(row)
    if not matches:
        raise HTTPException(status_code=422, detail="No reviewed existing Property matches to bind.")
    already = 0
    for row in matches:
        mapped = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "YARDI",
            PlatformMigrationItem.resource == "PROPERTIES",
            PlatformMigrationItem.source_id == row.source_id,
        ).first()
        if mapped is not None:
            if (mapped.target_entity != "PROPERTY" or mapped.target_id != row.resolution_target_id
                    or mapped.source_fingerprint != row.row_fingerprint):
                raise HTTPException(status_code=409, detail="Conflicting durable Property source mapping.")
            already += 1
    if already == len(matches):
        # Even an idempotent replay must not report a valid binding to a deleted target.
        for row in sorted(matches, key=lambda item: item.resolution_target_id):
            if _locked_yardi_review_target(
                db, organization_id=run.organization_id,
                property_id=row.resolution_target_id,
            ) is None:
                raise HTTPException(status_code=409, detail="Previously mapped Property target no longer exists.")
            staff_claim = db.query(PlatformMigrationStagedRow.id).filter(
                PlatformMigrationStagedRow.organization_id == run.organization_id,
                PlatformMigrationStagedRow.provider == "YARDI",
                PlatformMigrationStagedRow.resource == "PROPERTIES",
                PlatformMigrationStagedRow.source_id.is_distinct_from(row.source_id),
                PlatformMigrationStagedRow.resolution_action == "MATCH_EXISTING",
                PlatformMigrationStagedRow.resolution_target_id == row.resolution_target_id,
            ).first()
            if staff_claim:
                raise HTTPException(status_code=409, detail="Another Yardi Property review claims this target.")
            competing = db.query(PlatformMigrationItem.id).filter(
                PlatformMigrationItem.organization_id == run.organization_id,
                PlatformMigrationItem.provider == "YARDI",
                PlatformMigrationItem.resource == "PROPERTIES",
                PlatformMigrationItem.target_entity == "PROPERTY",
                PlatformMigrationItem.target_id == row.resolution_target_id,
                or_(
                    PlatformMigrationItem.run_id != run.id,
                    PlatformMigrationItem.source_id != row.source_id,
                ),
            ).first()
            if competing is not None:
                raise HTTPException(status_code=409, detail="Replayed Property target has a conflicting source binding.")
        return {"run_id": run.id, "provider": "YARDI", "bound": 0,
                "matched_existing": len(matches), "replayed": True,
                "customer_business_mutation": False}
    if already:
        raise HTTPException(status_code=409, detail="Partial existing bindings require reconciliation.")
    current = get_yardi_reconciliation(run_id, Response(), db, current_user)["review_fingerprint"]
    if not run.last_dry_run_fingerprint or payload.review_fingerprint != current or run.last_dry_run_fingerprint != current:
        raise HTTPException(status_code=409, detail="A current exact-fingerprint review dry run is required.")
    # Acquire target row locks in a stable order to avoid cross-run lock inversion.
    ordered_matches = sorted(matches, key=lambda candidate: candidate.resolution_target_id)
    for row in ordered_matches:
        target = _locked_yardi_review_target(
            db, organization_id=run.organization_id,
            property_id=row.resolution_target_id,
        )
        if target is None:
            raise HTTPException(status_code=409, detail="Reviewed Property target no longer exists.")
        staff_claim = db.query(PlatformMigrationStagedRow.id).filter(
            PlatformMigrationStagedRow.organization_id == run.organization_id,
            PlatformMigrationStagedRow.provider == "YARDI",
            PlatformMigrationStagedRow.resource == "PROPERTIES",
            PlatformMigrationStagedRow.source_id.is_distinct_from(row.source_id),
            PlatformMigrationStagedRow.resolution_action == "MATCH_EXISTING",
            PlatformMigrationStagedRow.resolution_target_id == target.id,
        ).first()
        if staff_claim:
            raise HTTPException(status_code=409, detail="Another Yardi Property review claims this target.")
        conflicting = db.query(PlatformMigrationItem.id).filter(
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "YARDI",
            PlatformMigrationItem.resource == "PROPERTIES",
            PlatformMigrationItem.target_entity == "PROPERTY",
            PlatformMigrationItem.target_id == row.resolution_target_id,
        ).first()
        if conflicting is not None:
            raise HTTPException(status_code=409, detail="Property target has a conflicting durable source mapping.")
    # Validate every locked target before staging any durable mapping.
    for row in ordered_matches:
        db.add(PlatformMigrationItem(
            run_id=run.id, organization_id=run.organization_id,
            provider="YARDI", resource="PROPERTIES",
            source_id=row.source_id, target_entity="PROPERTY",
            target_id=row.resolution_target_id,
            source_fingerprint=row.row_fingerprint,
            created_by_platform_user_id=current_user.id,
        ))
    run.last_dry_run_fingerprint = None
    run.last_dry_run_summary = None
    append_audit_log(
        db, platform_user_id=current_user.id,
        organization_id=run.organization_id,
        entity_type="platform_migration_run", entity_id=run.id,
        action="yardi_property_existing_bindings_committed",
        new_value={"matched_existing": len(matches), "target_overwrite": False,
                   "customer_business_mutation": False},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Durable Yardi Property mapping conflicted.") from exc
    return {"run_id": run.id, "provider": "YARDI", "bound": len(matches),
            "matched_existing": len(matches), "replayed": False,
            "customer_business_mutation": False}
