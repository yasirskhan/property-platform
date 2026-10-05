"""Buildium lease-ledger payment reconciliation routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.platform_user import PlatformUser
from app.routers.buildium_migrations import _run
from app.routers.platform_auth import get_current_platform_user
from app.schemas.buildium_lease_payment_migration import (
    BuildiumLeasePaymentCommitIn,
    BuildiumLeasePaymentCommitOut,
    BuildiumLeasePaymentDryRunIn,
    BuildiumLeasePaymentDryRunOut,
)
from app.services.audit import append_audit_log
from app.services.buildium_lease_payment_migration import (
    BuildiumLeasePaymentMigrationError,
    commit_lease_payments,
    dry_run_lease_payments,
)


router = APIRouter(
    prefix="/api/platform/migrations/buildium",
    tags=["Platform Buildium Migration"],
)


@router.post(
    "/runs/{run_id}/lease-payments/dry-run",
    response_model=BuildiumLeasePaymentDryRunOut,
)
def dry_run_buildium_lease_payments(
    run_id: int,
    payload: BuildiumLeasePaymentDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        result = dry_run_lease_payments(
            db, run=run, records=payload.records, resolutions=resolutions
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="buildium_lease_payments_dry_run",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "LEASE_PAYMENTS",
                    "fingerprint": result.fingerprint,
                    "total": result.total,
                    "reviewable": result.reviewable,
                    "skipped_review": result.skipped_review,
                    "invalid": result.invalid,
                    "warning_count": result.warning_count,
                    "target_receipt_created": False,
                    "accounting_mutation": False,
                    "provider_credentials_stored": False,
                },
            )
            db.commit()
    except BuildiumLeasePaymentMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return BuildiumLeasePaymentDryRunOut(
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
    "/runs/{run_id}/lease-payments/commit",
    response_model=BuildiumLeasePaymentCommitOut,
)
def commit_buildium_lease_payments(
    run_id: int,
    payload: BuildiumLeasePaymentCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        result = commit_lease_payments(
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
                action="buildium_lease_payments_reconciled",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "LEASE_PAYMENTS",
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "target_receipt_created": False,
                    "accounting_mutation": False,
                    "provider_credentials_stored": False,
                },
            )
        db.commit()
    except BuildiumLeasePaymentMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return BuildiumLeasePaymentCommitOut(
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
