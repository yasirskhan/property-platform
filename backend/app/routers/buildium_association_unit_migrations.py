"""Buildium Association Unit existing-target reconciliation routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.platform_user import PlatformUser
from app.routers.buildium_migrations import _run, _transport_http_error
from app.routers.platform_auth import get_current_platform_user
from app.schemas.buildium_association_unit_migration import (
    BuildiumApiAssociationUnitCommitIn,
    BuildiumApiAssociationUnitDryRunIn,
    BuildiumAssociationUnitCommitIn,
    BuildiumAssociationUnitCommitOut,
    BuildiumAssociationUnitDryRunIn,
    BuildiumAssociationUnitDryRunOut,
)
from app.services.audit import append_audit_log
from app.services.buildium_api_transport import (
    BuildiumApiTransportError,
    fetch_association_units,
)
from app.services.buildium_association_unit_migration import (
    BuildiumAssociationUnitMigrationError,
    commit_association_units,
    dry_run_association_units,
)


router = APIRouter(
    prefix="/api/platform/migrations/buildium",
    tags=["Platform Buildium Migration"],
)



@router.post(
    "/runs/{run_id}/hoa-units/api-dry-run",
    response_model=BuildiumAssociationUnitDryRunOut,
)
def api_dry_run_buildium_association_units(
    run_id: int,
    payload: BuildiumApiAssociationUnitDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        fetched = fetch_association_units(
            expected_source_account_ref=run.source_account_ref
        )
        result = dry_run_association_units(
            db, run=run, records=fetched.records, resolutions=resolutions
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="buildium_hoa_units_api_dry_run",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "HOA_UNITS",
                    "fingerprint": result.fingerprint,
                    "total": result.total,
                    "reviewable": result.reviewable,
                    "skipped_review": result.skipped_review,
                    "invalid": result.invalid,
                    "warning_count": result.warning_count,
                    "units_created": False,
                    "units_updated": False,
                    "properties_created": False,
                    "property_memberships_created": False,
                    "property_memberships_updated": False,
                    "owner_or_tenant_relationships_changed": False,
                    "dues_or_assessments_created": False,
                    "reserve_or_bank_mapping_created": False,
                    "gl_history_created": False,
                    "transport": "SERVER_TO_SERVER",
                    "transport_mode": fetched.mode.upper(),
                    "transport_request_count": fetched.request_count,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                    "provider_address_promoted": False,
                },
            )
            db.commit()
    except BuildiumApiTransportError as exc:
        db.rollback()
        raise _transport_http_error(exc) from exc
    except BuildiumAssociationUnitMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return BuildiumAssociationUnitDryRunOut(
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
    "/runs/{run_id}/hoa-units/api-commit",
    response_model=BuildiumAssociationUnitCommitOut,
)
def api_commit_buildium_association_units(
    run_id: int,
    payload: BuildiumApiAssociationUnitCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        fetched = fetch_association_units(
            expected_source_account_ref=run.source_account_ref
        )
        result = commit_association_units(
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
                action="buildium_hoa_units_api_reconciled",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "HOA_UNITS",
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "units_created": False,
                    "units_updated": False,
                    "properties_created": False,
                    "property_memberships_created": False,
                    "property_memberships_updated": False,
                    "owner_or_tenant_relationships_changed": False,
                    "dues_or_assessments_created": False,
                    "reserve_or_bank_mapping_created": False,
                    "gl_history_created": False,
                    "transport": "SERVER_TO_SERVER",
                    "transport_mode": fetched.mode.upper(),
                    "transport_request_count": fetched.request_count,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                    "provider_address_promoted": False,
                },
            )
        db.commit()
    except BuildiumApiTransportError as exc:
        db.rollback()
        raise _transport_http_error(exc) from exc
    except BuildiumAssociationUnitMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Association Unit API mapping conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumAssociationUnitCommitOut(
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
    "/runs/{run_id}/hoa-units/dry-run",
    response_model=BuildiumAssociationUnitDryRunOut,
)
def dry_run_buildium_association_units(
    run_id: int,
    payload: BuildiumAssociationUnitDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        result = dry_run_association_units(
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
                action="buildium_hoa_units_dry_run",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "HOA_UNITS",
                    "fingerprint": result.fingerprint,
                    **result.summary,
                },
            )
            db.commit()
    except BuildiumAssociationUnitMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return BuildiumAssociationUnitDryRunOut(
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
    "/runs/{run_id}/hoa-units/commit",
    response_model=BuildiumAssociationUnitCommitOut,
)
def commit_buildium_association_units(
    run_id: int,
    payload: BuildiumAssociationUnitCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        result = commit_association_units(
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
                action="buildium_hoa_units_reconciled",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "HOA_UNITS",
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "units_created": False,
                    "units_updated": False,
                    "properties_created": False,
                    "property_memberships_created": False,
                    "property_memberships_updated": False,
                    "owner_or_tenant_relationships_changed": False,
                    "dues_or_assessments_created": False,
                    "reserve_or_bank_mapping_created": False,
                    "gl_history_created": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
        db.commit()
    except BuildiumAssociationUnitMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Association Unit mapping conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumAssociationUnitCommitOut(
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
