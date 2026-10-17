"""Buildium Association Tenant identity reconciliation routes."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.platform_user import PlatformUser
from app.routers.buildium_migrations import _run, _transport_http_error
from app.routers.platform_auth import get_current_platform_user
from app.schemas.buildium_association_tenant_migration import (
    BuildiumApiAssociationTenantCommitIn, BuildiumApiAssociationTenantDryRunIn,
    BuildiumAssociationTenantCommitIn, BuildiumAssociationTenantCommitOut,
    BuildiumAssociationTenantDryRunIn, BuildiumAssociationTenantDryRunOut,
)
from app.services.audit import append_audit_log
from app.services.buildium_api_transport import (
    BuildiumApiTransportError, fetch_association_tenants,
)
from app.services.buildium_association_tenant_migration import (
    BuildiumAssociationTenantMigrationError, commit_association_tenants, dry_run_association_tenants,
)

router = APIRouter(prefix="/api/platform/migrations/buildium", tags=["Platform Buildium Migration"])


@router.post("/runs/{run_id}/hoa-tenants/api-dry-run", response_model=BuildiumAssociationTenantDryRunOut)
def api_dry_run_buildium_association_tenants(
    run_id: int, payload: BuildiumApiAssociationTenantDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        fetched = fetch_association_tenants(
            expected_source_account_ref=run.source_account_ref
        )
        result = dry_run_association_tenants(
            db, run=run, records=fetched.records, resolutions=resolutions
        )
        if not result.replayed:
            append_audit_log(
                db, platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run", entity_id=run.id,
                action="buildium_association_tenants_api_dry_run",
                new_value={
                    "provider": "BUILDIUM", "resource": "HOA_TENANTS",
                    "fingerprint": result.fingerprint,
                    "total": result.total, "reviewable": result.reviewable,
                    "skipped_review": result.skipped_review,
                    "invalid": result.invalid, "warning_count": result.warning_count,
                    "tenant_users_created": False,
                    "leases_created_from_identity": False,
                    "ownership_accounts_created": False,
                    "occupancy_created": False,
                    "charges_created": False,
                    "payments_created_from_identity": False,
                    "move_history_created": False,
                    "accounting_history_created": False,
                    "transport": "SERVER_TO_SERVER",
                    "transport_mode": fetched.mode.upper(),
                    "transport_request_count": fetched.request_count,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                    "provider_private_tenant_data_stored": False,
                    "provider_ownership_data_stored": False,
                    "provider_move_history_stored": False,
                },
            )
            db.commit()
    except BuildiumApiTransportError as exc:
        db.rollback()
        raise _transport_http_error(exc) from exc
    except BuildiumAssociationTenantMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return BuildiumAssociationTenantDryRunOut(
        run_id=run.id, organization_id=run.organization_id, provider=run.provider,
        fingerprint=result.fingerprint, replayed=result.replayed, total=result.total,
        reviewable=result.reviewable, skipped_review=result.skipped_review,
        invalid=result.invalid, warning_count=result.warning_count, rows=result.rows,
    )


@router.post("/runs/{run_id}/hoa-tenants/api-commit", response_model=BuildiumAssociationTenantCommitOut)
def api_commit_buildium_association_tenants(
    run_id: int, payload: BuildiumApiAssociationTenantCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        fetched = fetch_association_tenants(
            expected_source_account_ref=run.source_account_ref
        )
        result = commit_association_tenants(
            db, run=run, records=fetched.records,
            expected_fingerprint=payload.fingerprint,
            platform_user_id=current_user.id, resolutions=resolutions,
        )
        if not result.replayed:
            append_audit_log(
                db, platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run", entity_id=run.id,
                action="buildium_association_tenants_api_reconciled",
                new_value={
                    "provider": "BUILDIUM", "resource": "HOA_TENANTS",
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "warning_count": result.warning_count,
                    "tenant_users_created": False,
                    "leases_created_from_identity": False,
                    "ownership_accounts_created": False,
                    "occupancy_created": False,
                    "charges_created": False,
                    "payments_created_from_identity": False,
                    "move_history_created": False,
                    "accounting_history_created": False,
                    "transport": "SERVER_TO_SERVER",
                    "transport_mode": fetched.mode.upper(),
                    "transport_request_count": fetched.request_count,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                    "provider_private_tenant_data_stored": False,
                    "provider_ownership_data_stored": False,
                    "provider_move_history_stored": False,
                },
            )
        db.commit()
    except BuildiumApiTransportError as exc:
        db.rollback()
        raise _transport_http_error(exc) from exc
    except BuildiumAssociationTenantMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Association Tenant API mapping conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumAssociationTenantCommitOut(
        run_id=run.id, organization_id=run.organization_id, provider=run.provider,
        fingerprint=result.fingerprint, replayed=result.replayed,
        matched_existing=result.matched_existing,
        skipped_review=result.skipped_review,
        warning_count=result.warning_count, rows=result.rows,
    )

@router.post("/runs/{run_id}/hoa-tenants/dry-run", response_model=BuildiumAssociationTenantDryRunOut)
def dry_run_buildium_association_tenants(
    run_id: int, payload: BuildiumAssociationTenantDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        result = dry_run_association_tenants(db, run=run, records=payload.records, resolutions=resolutions)
        if not result.replayed:
            append_audit_log(
                db, platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run", entity_id=run.id,
                action="buildium_association_tenants_dry_run",
                new_value={"provider": "BUILDIUM", "resource": "HOA_TENANTS",
                           "fingerprint": result.fingerprint, **result.summary},
            )
            db.commit()
    except BuildiumAssociationTenantMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return BuildiumAssociationTenantDryRunOut(
        run_id=run.id, organization_id=run.organization_id, provider=run.provider,
        fingerprint=result.fingerprint, replayed=result.replayed, total=result.total,
        reviewable=result.reviewable, skipped_review=result.skipped_review,
        invalid=result.invalid, warning_count=result.warning_count, rows=result.rows,
    )

@router.post("/runs/{run_id}/hoa-tenants/commit", response_model=BuildiumAssociationTenantCommitOut)
def commit_buildium_association_tenants(
    run_id: int, payload: BuildiumAssociationTenantCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        result = commit_association_tenants(
            db, run=run, records=payload.records,
            expected_fingerprint=payload.fingerprint,
            platform_user_id=current_user.id, resolutions=resolutions,
        )
        if not result.replayed:
            append_audit_log(
                db, platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run", entity_id=run.id,
                action="buildium_association_tenants_reconciled",
                new_value={
                    "provider": "BUILDIUM", "resource": "HOA_TENANTS",
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "tenant_users_created": False,
                    "leases_created_from_identity": False,
                    "ownership_accounts_created": False, "occupancy_created": False,
                    "charges_created": False, "payments_created_from_identity": False,
                    "move_history_created": False, "accounting_history_created": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
        db.commit()
    except BuildiumAssociationTenantMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Association Tenant mapping conflicted with an existing migration mapping.",
        ) from exc
    return BuildiumAssociationTenantCommitOut(
        run_id=run.id, organization_id=run.organization_id, provider=run.provider,
        fingerprint=result.fingerprint, replayed=result.replayed,
        matched_existing=result.matched_existing,
        skipped_review=result.skipped_review,
        warning_count=result.warning_count, rows=result.rows,
    )
