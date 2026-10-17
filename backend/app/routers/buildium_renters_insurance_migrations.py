"""Buildium renters-insurance existing-target reconciliation routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser
from app.routers.buildium_migrations import _run, _transport_http_error
from app.routers.platform_auth import get_current_platform_user
from app.schemas.buildium_renters_insurance_migration import (
    BuildiumApiRentersInsuranceCommitIn,
    BuildiumApiRentersInsuranceDryRunIn,
    BuildiumRentersInsuranceCommitIn,
    BuildiumRentersInsuranceCommitOut,
    BuildiumRentersInsuranceDryRunIn,
    BuildiumRentersInsuranceDryRunOut,
)
from app.services.audit import append_audit_log
from app.services.buildium_api_transport import (
    BuildiumApiTransportError,
    MAX_RENTERS_INSURANCE_PARENT_LEASES,
    fetch_renters_insurance,
)
from app.services.buildium_renters_insurance_migration import (
    BuildiumRentersInsuranceMigrationError,
    commit_renters_insurance,
    dry_run_renters_insurance,
)


router = APIRouter(
    prefix="/api/platform/migrations/buildium",
    tags=["Platform Buildium Migration"],
)


def _renters_insurance_api_parent_source_ids(
    db: Session,
    *,
    run: PlatformMigrationRun,
) -> list[str]:
    mappings = (
        db.query(PlatformMigrationItem)
        .filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "BUILDIUM",
            PlatformMigrationItem.resource == "LEASES",
        )
        .order_by(PlatformMigrationItem.id.asc())
        .limit(MAX_RENTERS_INSURANCE_PARENT_LEASES + 1)
        .all()
    )
    if len(mappings) > MAX_RENTERS_INSURANCE_PARENT_LEASES:
        raise BuildiumApiTransportError(
            "source_too_large",
            "Buildium renters-insurance API migration exceeds the bounded "
            f"{MAX_RENTERS_INSURANCE_PARENT_LEASES}-parent-Lease review scope.",
        )
    for mapping in mappings:
        if mapping.target_entity != "LEASE_RELATIONSHIP":
            raise BuildiumRentersInsuranceMigrationError(
                "Buildium Lease mapping is inconsistent and cannot define renters-insurance parent scope."
            )
    return [mapping.source_id for mapping in mappings]


@router.post(
    "/runs/{run_id}/renters-insurance/api-dry-run",
    response_model=BuildiumRentersInsuranceDryRunOut,
)
def api_dry_run_buildium_renters_insurance(
    run_id: int,
    payload: BuildiumApiRentersInsuranceDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        fetched = fetch_renters_insurance(
            expected_source_account_ref=run.source_account_ref,
            parent_lease_ids=_renters_insurance_api_parent_source_ids(db, run=run),
        )
        result = dry_run_renters_insurance(
            db, run=run, records=fetched.records, resolutions=resolutions
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="buildium_renters_insurance_api_dry_run",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "RENTERS_INSURANCE",
                    "fingerprint": result.fingerprint,
                    "total": result.total,
                    "reviewable": result.reviewable,
                    "skipped_review": result.skipped_review,
                    "invalid": result.invalid,
                    "warning_count": result.warning_count,
                    "tenant_insurance_created": False,
                    "tenant_insurance_updated": False,
                    "documents_copied": False,
                    "financial_history_created": False,
                    "transport": "SERVER_TO_SERVER",
                    "transport_mode": fetched.mode.upper(),
                    "transport_request_count": fetched.request_count,
                    "transport_parent_lease_count": fetched.parent_record_count,
                    "transport_policy_count": len(fetched.records),
                    "parent_scope": "DURABLE_LEASE_MAPPINGS",
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
            db.commit()
    except BuildiumApiTransportError as exc:
        db.rollback()
        raise _transport_http_error(exc) from exc
    except BuildiumRentersInsuranceMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return BuildiumRentersInsuranceDryRunOut(
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
    "/runs/{run_id}/renters-insurance/api-commit",
    response_model=BuildiumRentersInsuranceCommitOut,
)
def api_commit_buildium_renters_insurance(
    run_id: int,
    payload: BuildiumApiRentersInsuranceCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        fetched = fetch_renters_insurance(
            expected_source_account_ref=run.source_account_ref,
            parent_lease_ids=_renters_insurance_api_parent_source_ids(db, run=run),
        )
        result = commit_renters_insurance(
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
                action="buildium_renters_insurance_api_reconciled",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "RENTERS_INSURANCE",
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "tenant_insurance_created": False,
                    "tenant_insurance_updated": False,
                    "documents_copied": False,
                    "financial_history_created": False,
                    "transport": "SERVER_TO_SERVER",
                    "transport_mode": fetched.mode.upper(),
                    "transport_request_count": fetched.request_count,
                    "transport_parent_lease_count": fetched.parent_record_count,
                    "transport_policy_count": len(fetched.records),
                    "parent_scope": "DURABLE_LEASE_MAPPINGS",
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
        db.commit()
    except BuildiumApiTransportError as exc:
        db.rollback()
        raise _transport_http_error(exc) from exc
    except BuildiumRentersInsuranceMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium renters-insurance API mapping conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumRentersInsuranceCommitOut(
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
    "/runs/{run_id}/renters-insurance/dry-run",
    response_model=BuildiumRentersInsuranceDryRunOut,
)
def dry_run_buildium_renters_insurance(
    run_id: int,
    payload: BuildiumRentersInsuranceDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        result = dry_run_renters_insurance(
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
                action="buildium_renters_insurance_dry_run",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "RENTERS_INSURANCE",
                    "fingerprint": result.fingerprint,
                    "total": result.total,
                    "reviewable": result.reviewable,
                    "skipped_review": result.skipped_review,
                    "invalid": result.invalid,
                    "warning_count": result.warning_count,
                    "tenant_insurance_created": False,
                    "tenant_insurance_updated": False,
                    "coverage_amount_inferred": False,
                    "verification_status_inferred": False,
                    "documents_copied": False,
                    "financial_history_created": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
            db.commit()
    except BuildiumRentersInsuranceMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return BuildiumRentersInsuranceDryRunOut(
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
    "/runs/{run_id}/renters-insurance/commit",
    response_model=BuildiumRentersInsuranceCommitOut,
)
def commit_buildium_renters_insurance(
    run_id: int,
    payload: BuildiumRentersInsuranceCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        result = commit_renters_insurance(
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
                action="buildium_renters_insurance_reconciled",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "RENTERS_INSURANCE",
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "tenant_insurance_created": False,
                    "tenant_insurance_updated": False,
                    "coverage_amount_inferred": False,
                    "verification_status_inferred": False,
                    "documents_copied": False,
                    "financial_history_created": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
        db.commit()
    except BuildiumRentersInsuranceMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Buildium renters-insurance mapping conflicted with an existing "
                "migration mapping."
            ),
        ) from exc

    return BuildiumRentersInsuranceCommitOut(
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
