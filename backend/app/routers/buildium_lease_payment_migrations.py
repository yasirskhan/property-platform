"""Buildium lease-ledger payment reconciliation routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser
from app.routers.buildium_migrations import _run, _transport_http_error
from app.routers.platform_auth import get_current_platform_user
from app.schemas.buildium_lease_payment_migration import (
    BuildiumApiLeasePaymentCommitIn,
    BuildiumApiLeasePaymentDryRunIn,
    BuildiumLeasePaymentCommitIn,
    BuildiumLeasePaymentCommitOut,
    BuildiumLeasePaymentDryRunIn,
    BuildiumLeasePaymentDryRunOut,
)
from app.services.audit import append_audit_log
from app.services.buildium_api_transport import (
    BuildiumApiTransportError,
    MAX_LEASE_PAYMENT_PARENT_LEASES,
    fetch_lease_payments,
)
from app.services.buildium_lease_payment_migration import (
    BuildiumLeasePaymentMigrationError,
    commit_lease_payments,
    dry_run_lease_payments,
)


router = APIRouter(
    prefix="/api/platform/migrations/buildium",
    tags=["Platform Buildium Migration"],
)


def _lease_payment_api_parent_source_ids(
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
        .limit(MAX_LEASE_PAYMENT_PARENT_LEASES + 1)
        .all()
    )
    if len(mappings) > MAX_LEASE_PAYMENT_PARENT_LEASES:
        raise BuildiumApiTransportError(
            "source_too_large",
            "Buildium Lease Payment API migration exceeds the bounded "
            f"{MAX_LEASE_PAYMENT_PARENT_LEASES}-parent-Lease review scope.",
        )
    for mapping in mappings:
        if mapping.target_entity != "LEASE_RELATIONSHIP":
            raise BuildiumLeasePaymentMigrationError(
                "Buildium Lease mapping is inconsistent and cannot define Lease Payment parent scope."
            )
    return [mapping.source_id for mapping in mappings]


@router.post(
    "/runs/{run_id}/lease-payments/api-dry-run",
    response_model=BuildiumLeasePaymentDryRunOut,
)
def api_dry_run_buildium_lease_payments(
    run_id: int,
    payload: BuildiumApiLeasePaymentDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        parent_lease_ids = _lease_payment_api_parent_source_ids(db, run=run)
        fetched = fetch_lease_payments(
            expected_source_account_ref=run.source_account_ref,
            parent_lease_ids=parent_lease_ids,
        )
        result = dry_run_lease_payments(
            db, run=run, records=fetched.records, resolutions=resolutions
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="buildium_lease_payments_api_dry_run",
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
                    "transport": "SERVER_TO_SERVER",
                    "transport_mode": fetched.mode.upper(),
                    "transport_request_count": fetched.request_count,
                    "transport_parent_lease_count": fetched.parent_record_count,
                    "transport_lease_payment_count": len(fetched.records),
                    "parent_scope": "DURABLE_LEASE_MAPPINGS",
                    "provider_credentials_stored": False,
                    "raw_response_stored": False,
                    "provider_memo_stored": False,
                },
            )
            db.commit()
    except BuildiumApiTransportError as exc:
        db.rollback()
        raise _transport_http_error(exc) from exc
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
    "/runs/{run_id}/lease-payments/api-commit",
    response_model=BuildiumLeasePaymentCommitOut,
)
def api_commit_buildium_lease_payments(
    run_id: int,
    payload: BuildiumApiLeasePaymentCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        parent_lease_ids = _lease_payment_api_parent_source_ids(db, run=run)
        fetched = fetch_lease_payments(
            expected_source_account_ref=run.source_account_ref,
            parent_lease_ids=parent_lease_ids,
        )
        result = commit_lease_payments(
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
                action="buildium_lease_payments_api_reconciled",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "LEASE_PAYMENTS",
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "warning_count": result.warning_count,
                    "target_receipt_ids": [item["target_receipt_id"] for item in result.rows],
                    "target_receipt_created": False,
                    "target_receipt_updated": False,
                    "accounting_mutation": False,
                    "lease_balance_mutation": False,
                    "bank_movement_created": False,
                    "settlement_state_inferred": False,
                    "transport": "SERVER_TO_SERVER",
                    "transport_mode": fetched.mode.upper(),
                    "transport_request_count": fetched.request_count,
                    "transport_parent_lease_count": fetched.parent_record_count,
                    "transport_lease_payment_count": len(fetched.records),
                    "parent_scope": "DURABLE_LEASE_MAPPINGS",
                    "provider_credentials_stored": False,
                    "raw_response_stored": False,
                    "provider_memo_stored": False,
                },
            )
        db.commit()
    except BuildiumApiTransportError as exc:
        db.rollback()
        raise _transport_http_error(exc) from exc
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
