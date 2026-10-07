"""Buildium bank-reconciliation existing-target routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser
from app.routers.buildium_migrations import _run, _transport_http_error
from app.routers.platform_auth import get_current_platform_user
from app.schemas.buildium_bank_reconciliation_migration import (
    BuildiumApiBankReconciliationCommitIn,
    BuildiumApiBankReconciliationDryRunIn,
    BuildiumBankReconciliationCommitIn,
    BuildiumBankReconciliationCommitOut,
    BuildiumBankReconciliationDryRunIn,
    BuildiumBankReconciliationDryRunOut,
)
from app.services.audit import append_audit_log
from app.services.buildium_api_transport import (
    BuildiumApiTransportError,
    MAX_BANK_RECONCILIATION_PARENT_BANK_ACCOUNTS,
    fetch_bank_reconciliations,
)
from app.services.buildium_bank_reconciliation_migration import (
    BuildiumBankReconciliationMigrationError,
    commit_bank_reconciliations,
    dry_run_bank_reconciliations,
)


router = APIRouter(
    prefix="/api/platform/migrations/buildium",
    tags=["Platform Buildium Migration"],
)


def _bank_reconciliation_api_parent_source_ids(
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
            PlatformMigrationItem.resource == "BANK_ACCOUNTS",
        )
        .order_by(PlatformMigrationItem.id.asc())
        .limit(MAX_BANK_RECONCILIATION_PARENT_BANK_ACCOUNTS + 1)
        .all()
    )
    if len(mappings) > MAX_BANK_RECONCILIATION_PARENT_BANK_ACCOUNTS:
        raise BuildiumApiTransportError(
            "source_too_large",
            "Buildium Bank Reconciliation API migration exceeds the bounded "
            f"{MAX_BANK_RECONCILIATION_PARENT_BANK_ACCOUNTS}-parent-Bank-Account review scope.",
        )
    for mapping in mappings:
        if mapping.target_entity != "BANK_ACCOUNT":
            raise BuildiumBankReconciliationMigrationError(
                "Buildium Bank Account mapping is inconsistent and cannot define Bank Reconciliation parent scope."
            )
    return [mapping.source_id for mapping in mappings]


@router.post(
    "/runs/{run_id}/bank-reconciliations/api-dry-run",
    response_model=BuildiumBankReconciliationDryRunOut,
)
def api_dry_run_buildium_bank_reconciliations(
    run_id: int,
    payload: BuildiumApiBankReconciliationDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        fetched = fetch_bank_reconciliations(
            expected_source_account_ref=run.source_account_ref,
            parent_bank_account_ids=_bank_reconciliation_api_parent_source_ids(db, run=run),
        )
        result = dry_run_bank_reconciliations(
            db, run=run, records=fetched.records, resolutions=resolutions
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="buildium_bank_reconciliations_api_dry_run",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "BANK_RECONCILIATIONS",
                    "fingerprint": result.fingerprint,
                    "total": result.total,
                    "reviewable": result.reviewable,
                    "skipped_review": result.skipped_review,
                    "invalid": result.invalid,
                    "warning_count": result.warning_count,
                    "target_reconciliations_created": False,
                    "clearing_state_changed": False,
                    "statement_lines_created": False,
                    "accounting_mutation": False,
                    "transport": "SERVER_TO_SERVER",
                    "transport_mode": fetched.mode.upper(),
                    "transport_request_count": fetched.request_count,
                    "transport_parent_bank_account_count": fetched.parent_record_count,
                    "transport_reconciliation_count": len(fetched.records),
                    "transport_balance_request_count": fetched.detail_request_count,
                    "parent_scope": "DURABLE_BANK_ACCOUNT_MAPPINGS",
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                    "provider_bank_metadata_stored": False,
                },
            )
            db.commit()
    except BuildiumApiTransportError as exc:
        db.rollback()
        raise _transport_http_error(exc) from exc
    except BuildiumBankReconciliationMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return BuildiumBankReconciliationDryRunOut(
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
    "/runs/{run_id}/bank-reconciliations/api-commit",
    response_model=BuildiumBankReconciliationCommitOut,
)
def api_commit_buildium_bank_reconciliations(
    run_id: int,
    payload: BuildiumApiBankReconciliationCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        fetched = fetch_bank_reconciliations(
            expected_source_account_ref=run.source_account_ref,
            parent_bank_account_ids=_bank_reconciliation_api_parent_source_ids(db, run=run),
        )
        result = commit_bank_reconciliations(
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
                action="buildium_bank_reconciliations_api_reconciled",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "BANK_RECONCILIATIONS",
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "warning_count": result.warning_count,
                    "target_reconciliation_ids": [
                        item["target_reconciliation_id"] for item in result.rows
                    ],
                    "target_reconciliations_created": False,
                    "target_reconciliations_updated": False,
                    "clearing_state_changed": False,
                    "statement_lines_created": False,
                    "accounting_mutation": False,
                    "bank_transaction_mutation": False,
                    "transport": "SERVER_TO_SERVER",
                    "transport_mode": fetched.mode.upper(),
                    "transport_request_count": fetched.request_count,
                    "transport_parent_bank_account_count": fetched.parent_record_count,
                    "transport_reconciliation_count": len(fetched.records),
                    "transport_balance_request_count": fetched.detail_request_count,
                    "parent_scope": "DURABLE_BANK_ACCOUNT_MAPPINGS",
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                    "provider_bank_metadata_stored": False,
                },
            )
        db.commit()
    except BuildiumApiTransportError as exc:
        db.rollback()
        raise _transport_http_error(exc) from exc
    except BuildiumBankReconciliationMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Bank Reconciliation API mapping conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumBankReconciliationCommitOut(
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
    "/runs/{run_id}/bank-reconciliations/dry-run",
    response_model=BuildiumBankReconciliationDryRunOut,
)
def dry_run_buildium_bank_reconciliations(
    run_id: int,
    payload: BuildiumBankReconciliationDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        result = dry_run_bank_reconciliations(
            db, run=run, records=payload.records, resolutions=resolutions
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="buildium_bank_reconciliations_dry_run",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "BANK_RECONCILIATIONS",
                    "fingerprint": result.fingerprint,
                    "total": result.total,
                    "reviewable": result.reviewable,
                    "skipped_review": result.skipped_review,
                    "invalid": result.invalid,
                    "warning_count": result.warning_count,
                    "target_reconciliations_created": False,
                    "clearing_state_changed": False,
                    "statement_lines_created": False,
                    "accounting_mutation": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
            db.commit()
    except BuildiumBankReconciliationMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return BuildiumBankReconciliationDryRunOut(
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
    "/runs/{run_id}/bank-reconciliations/commit",
    response_model=BuildiumBankReconciliationCommitOut,
)
def commit_buildium_bank_reconciliations(
    run_id: int,
    payload: BuildiumBankReconciliationCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        result = commit_bank_reconciliations(
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
                action="buildium_bank_reconciliations_reconciled",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "BANK_RECONCILIATIONS",
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "target_reconciliations_created": False,
                    "clearing_state_changed": False,
                    "statement_lines_created": False,
                    "accounting_mutation": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
        db.commit()
    except BuildiumBankReconciliationMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Bank Reconciliation mapping conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumBankReconciliationCommitOut(
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
