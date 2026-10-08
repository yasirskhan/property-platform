"""Buildium Rental Applicant identity reconciliation routes."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.platform_user import PlatformUser
from app.routers.buildium_migrations import _run, _transport_http_error
from app.routers.platform_auth import get_current_platform_user
from app.schemas.buildium_applicant_migration import (
    BuildiumApiApplicantCommitIn, BuildiumApiApplicantDryRunIn,
    BuildiumApplicantCommitIn, BuildiumApplicantCommitOut,
    BuildiumApplicantDryRunIn, BuildiumApplicantDryRunOut,
)
from app.services.audit import append_audit_log
from app.services.buildium_api_transport import (
    BuildiumApiTransportError, fetch_applicants,
)
from app.services.buildium_applicant_migration import (
    BuildiumApplicantMigrationError, commit_applicants, dry_run_applicants,
)

router = APIRouter(prefix="/api/platform/migrations/buildium", tags=["Platform Buildium Migration"])


@router.post("/runs/{run_id}/applicants/api-dry-run", response_model=BuildiumApplicantDryRunOut)
def api_dry_run_buildium_applicants(
    run_id: int, payload: BuildiumApiApplicantDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        fetched = fetch_applicants(expected_source_account_ref=run.source_account_ref)
        result = dry_run_applicants(db, run=run, records=fetched.records, resolutions=resolutions)
        if not result.replayed:
            append_audit_log(
                db, platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run", entity_id=run.id,
                action="buildium_applicants_api_dry_run",
                new_value={
                    "provider": "BUILDIUM", "resource": "APPLICANTS",
                    "fingerprint": result.fingerprint,
                    "total": result.total, "reviewable": result.reviewable,
                    "skipped_review": result.skipped_review, "invalid": result.invalid,
                    "warning_count": result.warning_count,
                    "applicant_users_created": False,
                    "rental_applications_created": False,
                    "screening_data_stored": False, "ssn_stored": False,
                    "payments_created": False, "leases_created": False,
                    "tenant_relationships_inferred": False,
                    "transport": "SERVER_TO_SERVER",
                    "transport_mode": fetched.mode.upper(),
                    "transport_request_count": fetched.request_count,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
            db.commit()
    except BuildiumApiTransportError as exc:
        db.rollback()
        raise _transport_http_error(exc) from exc
    except BuildiumApplicantMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return BuildiumApplicantDryRunOut(
        run_id=run.id, organization_id=run.organization_id, provider=run.provider,
        fingerprint=result.fingerprint, replayed=result.replayed, total=result.total,
        reviewable=result.reviewable, skipped_review=result.skipped_review,
        invalid=result.invalid, warning_count=result.warning_count, rows=result.rows,
    )


@router.post("/runs/{run_id}/applicants/api-commit", response_model=BuildiumApplicantCommitOut)
def api_commit_buildium_applicants(
    run_id: int, payload: BuildiumApiApplicantCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        fetched = fetch_applicants(expected_source_account_ref=run.source_account_ref)
        result = commit_applicants(
            db, run=run, records=fetched.records,
            expected_fingerprint=payload.fingerprint,
            platform_user_id=current_user.id, resolutions=resolutions,
        )
        if not result.replayed:
            append_audit_log(
                db, platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run", entity_id=run.id,
                action="buildium_applicants_api_reconciled",
                new_value={
                    "provider": "BUILDIUM", "resource": "APPLICANTS",
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "applicant_users_created": False,
                    "rental_applications_created": False,
                    "screening_data_stored": False, "ssn_stored": False,
                    "payments_created": False, "leases_created": False,
                    "tenant_relationships_inferred": False,
                    "transport": "SERVER_TO_SERVER",
                    "transport_mode": fetched.mode.upper(),
                    "transport_request_count": fetched.request_count,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
        db.commit()
    except BuildiumApiTransportError as exc:
        db.rollback()
        raise _transport_http_error(exc) from exc
    except BuildiumApplicantMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Applicant API mapping conflicted with an existing migration mapping.",
        ) from exc
    return BuildiumApplicantCommitOut(
        run_id=run.id, organization_id=run.organization_id, provider=run.provider,
        fingerprint=result.fingerprint, replayed=result.replayed,
        matched_existing=result.matched_existing,
        skipped_review=result.skipped_review,
        warning_count=result.warning_count, rows=result.rows,
    )


@router.post("/runs/{run_id}/applicants/dry-run", response_model=BuildiumApplicantDryRunOut)
def dry_run_buildium_applicants(
    run_id: int, payload: BuildiumApplicantDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        result = dry_run_applicants(db, run=run, records=payload.records, resolutions=resolutions)
        if not result.replayed:
            append_audit_log(
                db, platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run", entity_id=run.id,
                action="buildium_applicants_dry_run",
                new_value={"provider": "BUILDIUM", "resource": "APPLICANTS",
                           "fingerprint": result.fingerprint, **result.summary},
            )
            db.commit()
    except BuildiumApplicantMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return BuildiumApplicantDryRunOut(
        run_id=run.id, organization_id=run.organization_id, provider=run.provider,
        fingerprint=result.fingerprint, replayed=result.replayed, total=result.total,
        reviewable=result.reviewable, skipped_review=result.skipped_review,
        invalid=result.invalid, warning_count=result.warning_count, rows=result.rows,
    )

@router.post("/runs/{run_id}/applicants/commit", response_model=BuildiumApplicantCommitOut)
def commit_buildium_applicants(
    run_id: int, payload: BuildiumApplicantCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        result = commit_applicants(
            db, run=run, records=payload.records,
            expected_fingerprint=payload.fingerprint,
            platform_user_id=current_user.id, resolutions=resolutions,
        )
        if not result.replayed:
            append_audit_log(
                db, platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run", entity_id=run.id,
                action="buildium_applicants_reconciled",
                new_value={
                    "provider": "BUILDIUM", "resource": "APPLICANTS",
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "applicant_users_created": False,
                    "rental_applications_created": False,
                    "screening_data_stored": False, "ssn_stored": False,
                    "payments_created": False, "leases_created": False,
                    "tenant_relationships_inferred": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
        db.commit()
    except BuildiumApplicantMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Applicant mapping conflicted with an existing migration mapping.",
        ) from exc
    return BuildiumApplicantCommitOut(
        run_id=run.id, organization_id=run.organization_id, provider=run.provider,
        fingerprint=result.fingerprint, replayed=result.replayed,
        matched_existing=result.matched_existing,
        skipped_review=result.skipped_review,
        warning_count=result.warning_count, rows=result.rows,
    )
