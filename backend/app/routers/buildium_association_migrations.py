"""Buildium Association identity reconciliation routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.platform_user import PlatformUser
from app.routers.buildium_migrations import _run, _transport_http_error
from app.routers.platform_auth import get_current_platform_user
from app.schemas.buildium_association_migration import (
    BuildiumApiAssociationCommitIn,
    BuildiumApiAssociationDryRunIn,
    BuildiumAssociationCommitIn,
    BuildiumAssociationCommitOut,
    BuildiumAssociationDryRunIn,
    BuildiumAssociationDryRunOut,
)
from app.services.audit import append_audit_log
from app.services.buildium_api_transport import (
    BuildiumApiTransportError,
    fetch_associations,
)
from app.services.buildium_association_migration import (
    BuildiumAssociationMigrationError,
    commit_associations,
    dry_run_associations,
)


router = APIRouter(
    prefix="/api/platform/migrations/buildium",
    tags=["Platform Buildium Migration"],
)



@router.post(
    "/runs/{run_id}/hoa-associations/api-dry-run",
    response_model=BuildiumAssociationDryRunOut,
)
def api_dry_run_buildium_associations(
    run_id: int,
    payload: BuildiumApiAssociationDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        fetched = fetch_associations(
            expected_source_account_ref=run.source_account_ref
        )
        result = dry_run_associations(
            db, run=run, records=fetched.records, resolutions=resolutions
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="buildium_hoa_associations_api_dry_run",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "HOA_ASSOCIATIONS",
                    "fingerprint": result.fingerprint,
                    "total": result.total,
                    "reviewable": result.reviewable,
                    "skipped_review": result.skipped_review,
                    "invalid": result.invalid,
                    "warning_count": result.warning_count,
                    "hoa_associations_created": False,
                    "hoa_associations_updated": False,
                    "property_memberships_changed": False,
                    "owner_or_contact_relationships_changed": False,
                    "dues_or_assessments_created": False,
                    "reserve_or_bank_mapping_created": False,
                    "gl_history_created": False,
                    "transport": "SERVER_TO_SERVER",
                    "transport_mode": fetched.mode.upper(),
                    "transport_request_count": fetched.request_count,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                    "provider_sensitive_fields_stored": False,
                },
            )
            db.commit()
    except BuildiumApiTransportError as exc:
        db.rollback()
        raise _transport_http_error(exc) from exc
    except BuildiumAssociationMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return BuildiumAssociationDryRunOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        total=result.total,
        reviewable=result.reviewable,
        skipped_review=result.skipped_review,
        invalid=result.invalid,
        warning_count=result.warning_count,
        rows=result.rows,
    )


@router.post(
    "/runs/{run_id}/hoa-associations/api-commit",
    response_model=BuildiumAssociationCommitOut,
)
def api_commit_buildium_associations(
    run_id: int,
    payload: BuildiumApiAssociationCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        fetched = fetch_associations(
            expected_source_account_ref=run.source_account_ref
        )
        result = commit_associations(
            db,
            run=run,
            records=fetched.records,
            expected_fingerprint=payload.fingerprint,
            platform_user_id=current_user.id,
            resolutions=resolutions,
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="buildium_hoa_associations_api_reconciled",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "HOA_ASSOCIATIONS",
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "hoa_associations_created": False,
                    "hoa_associations_updated": False,
                    "property_memberships_changed": False,
                    "owner_or_contact_relationships_changed": False,
                    "dues_or_assessments_created": False,
                    "reserve_or_bank_mapping_created": False,
                    "gl_history_created": False,
                    "transport": "SERVER_TO_SERVER",
                    "transport_mode": fetched.mode.upper(),
                    "transport_request_count": fetched.request_count,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                    "provider_sensitive_fields_stored": False,
                },
            )
        db.commit()
    except BuildiumApiTransportError as exc:
        db.rollback()
        raise _transport_http_error(exc) from exc
    except BuildiumAssociationMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Association API mapping conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumAssociationCommitOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        matched_existing=result.matched_existing,
        skipped_review=result.skipped_review,
        warning_count=result.warning_count,
        rows=result.rows,
    )


@router.post(
    "/runs/{run_id}/hoa-associations/dry-run",
    response_model=BuildiumAssociationDryRunOut,
)
def dry_run_buildium_associations(
    run_id: int,
    payload: BuildiumAssociationDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        result = dry_run_associations(
            db,
            run=run,
            records=payload.records,
            resolutions=resolutions,
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="buildium_hoa_associations_dry_run",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "HOA_ASSOCIATIONS",
                    "fingerprint": result.fingerprint,
                    **result.summary,
                },
            )
            db.commit()
    except BuildiumAssociationMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return BuildiumAssociationDryRunOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        total=result.total,
        reviewable=result.reviewable,
        skipped_review=result.skipped_review,
        invalid=result.invalid,
        warning_count=result.warning_count,
        rows=result.rows,
    )


@router.post(
    "/runs/{run_id}/hoa-associations/commit",
    response_model=BuildiumAssociationCommitOut,
)
def commit_buildium_associations(
    run_id: int,
    payload: BuildiumAssociationCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        result = commit_associations(
            db,
            run=run,
            records=payload.records,
            expected_fingerprint=payload.fingerprint,
            platform_user_id=current_user.id,
            resolutions=resolutions,
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="buildium_hoa_associations_reconciled",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "HOA_ASSOCIATIONS",
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "hoa_associations_created": False,
                    "hoa_associations_updated": False,
                    "properties_created": False,
                    "property_memberships_changed": False,
                    "owner_or_contact_relationships_changed": False,
                    "dues_or_assessments_created": False,
                    "reserve_or_bank_mapping_created": False,
                    "gl_history_created": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
        db.commit()
    except BuildiumAssociationMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Association mapping conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumAssociationCommitOut(
        run_id=run.id,
        organization_id=run.organization_id,
        provider=run.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        matched_existing=result.matched_existing,
        skipped_review=result.skipped_review,
        warning_count=result.warning_count,
        rows=result.rows,
    )
