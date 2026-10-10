"""Buildium Association Owner identity reconciliation routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.platform_user import PlatformUser
from app.routers.buildium_migrations import _run, _transport_http_error
from app.routers.platform_auth import get_current_platform_user
from app.schemas.buildium_association_owner_migration import (
    BuildiumApiAssociationOwnerCommitIn,
    BuildiumApiAssociationOwnerDryRunIn,
    BuildiumAssociationOwnerCommitIn,
    BuildiumAssociationOwnerCommitOut,
    BuildiumAssociationOwnerDryRunIn,
    BuildiumAssociationOwnerDryRunOut,
)
from app.services.audit import append_audit_log
from app.services.buildium_api_transport import (
    BuildiumApiTransportError,
    fetch_association_owners,
)
from app.services.buildium_association_owner_migration import (
    BuildiumAssociationOwnerMigrationError,
    commit_association_owners,
    dry_run_association_owners,
)


router = APIRouter(
    prefix="/api/platform/migrations/buildium",
    tags=["Platform Buildium Migration"],
)


@router.post(
    "/runs/{run_id}/hoa-owners/api-dry-run",
    response_model=BuildiumAssociationOwnerDryRunOut,
)
def api_dry_run_buildium_association_owners(
    run_id: int,
    payload: BuildiumApiAssociationOwnerDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        fetched = fetch_association_owners(
            expected_source_account_ref=run.source_account_ref
        )
        result = dry_run_association_owners(
            db, run=run, records=fetched.records, resolutions=resolutions
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="buildium_hoa_owners_api_dry_run",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "HOA_OWNERS",
                    "fingerprint": result.fingerprint,
                    "total": result.total,
                    "reviewable": result.reviewable,
                    "skipped_review": result.skipped_review,
                    "invalid": result.invalid,
                    "warning_count": result.warning_count,
                    "owner_users_created": False,
                    "ownership_accounts_created": False,
                    "hoa_memberships_created": False,
                    "board_roles_created": False,
                    "dues_or_delinquency_imported": False,
                    "lease_or_occupancy_relationships_inferred": False,
                    "accounting_mutation": False,
                    "transport": "SERVER_TO_SERVER",
                    "transport_mode": fetched.mode.upper(),
                    "transport_request_count": fetched.request_count,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                    "provider_private_contact_data_stored": False,
                    "provider_board_data_stored": False,
                },
            )
            db.commit()
    except BuildiumApiTransportError as exc:
        db.rollback()
        raise _transport_http_error(exc) from exc
    except BuildiumAssociationOwnerMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return BuildiumAssociationOwnerDryRunOut(
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
    "/runs/{run_id}/hoa-owners/api-commit",
    response_model=BuildiumAssociationOwnerCommitOut,
)
def api_commit_buildium_association_owners(
    run_id: int,
    payload: BuildiumApiAssociationOwnerCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        fetched = fetch_association_owners(
            expected_source_account_ref=run.source_account_ref
        )
        result = commit_association_owners(
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
                action="buildium_hoa_owners_api_reconciled",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "HOA_OWNERS",
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "warning_count": result.warning_count,
                    "owner_users_created": False,
                    "ownership_accounts_created": False,
                    "hoa_memberships_created": False,
                    "board_roles_created": False,
                    "dues_or_delinquency_imported": False,
                    "lease_or_occupancy_relationships_inferred": False,
                    "accounting_mutation": False,
                    "transport": "SERVER_TO_SERVER",
                    "transport_mode": fetched.mode.upper(),
                    "transport_request_count": fetched.request_count,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                    "provider_private_contact_data_stored": False,
                    "provider_board_data_stored": False,
                },
            )
        db.commit()
    except BuildiumApiTransportError as exc:
        db.rollback()
        raise _transport_http_error(exc) from exc
    except BuildiumAssociationOwnerMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Association Owner API mapping conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumAssociationOwnerCommitOut(
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
    "/runs/{run_id}/hoa-owners/dry-run",
    response_model=BuildiumAssociationOwnerDryRunOut,
)
def dry_run_buildium_association_owners(
    run_id: int,
    payload: BuildiumAssociationOwnerDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        result = dry_run_association_owners(
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
                action="buildium_hoa_owners_dry_run",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "HOA_OWNERS",
                    "fingerprint": result.fingerprint,
                    **result.summary,
                },
            )
            db.commit()
    except BuildiumAssociationOwnerMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return BuildiumAssociationOwnerDryRunOut(
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
    "/runs/{run_id}/hoa-owners/commit",
    response_model=BuildiumAssociationOwnerCommitOut,
)
def commit_buildium_association_owners(
    run_id: int,
    payload: BuildiumAssociationOwnerCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        result = commit_association_owners(
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
                action="buildium_hoa_owners_reconciled",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "HOA_OWNERS",
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "owner_users_created": False,
                    "ownership_accounts_created": False,
                    "hoa_memberships_created": False,
                    "board_roles_created": False,
                    "dues_or_delinquency_imported": False,
                    "lease_or_occupancy_relationships_inferred": False,
                    "accounting_mutation": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
        db.commit()
    except BuildiumAssociationOwnerMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Association Owner mapping conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumAssociationOwnerCommitOut(
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
