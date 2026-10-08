"""Buildium quick-deposit existing-target routes."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser
from app.routers.buildium_migrations import _run, _transport_http_error
from app.routers.platform_auth import get_current_platform_user
from app.schemas.buildium_quick_deposit_migration import (
    BuildiumApiQuickDepositCommitIn,
    BuildiumApiQuickDepositDryRunIn,
    BuildiumQuickDepositCommitIn,
    BuildiumQuickDepositCommitOut,
    BuildiumQuickDepositDryRunIn,
    BuildiumQuickDepositDryRunOut,
)
from app.services.audit import append_audit_log
from app.services.buildium_api_transport import (
    BuildiumApiTransportError,
    MAX_QUICK_DEPOSIT_PARENT_BANK_ACCOUNTS,
    fetch_quick_deposits,
)
from app.services.buildium_quick_deposit_migration import (
    BuildiumQuickDepositMigrationError,
    commit_quick_deposits,
    dry_run_quick_deposits,
)

router = APIRouter(prefix="/api/platform/migrations/buildium", tags=["Platform Buildium Migration"])


def _quick_deposit_api_parent_source_ids(
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
        .limit(MAX_QUICK_DEPOSIT_PARENT_BANK_ACCOUNTS + 1)
        .all()
    )
    if len(mappings) > MAX_QUICK_DEPOSIT_PARENT_BANK_ACCOUNTS:
        raise BuildiumApiTransportError(
            "source_too_large",
            "Buildium Quick Deposit API migration exceeds the bounded "
            f"{MAX_QUICK_DEPOSIT_PARENT_BANK_ACCOUNTS}-parent-Bank-Account review scope.",
        )
    for mapping in mappings:
        if mapping.target_entity != "BANK_ACCOUNT":
            raise BuildiumQuickDepositMigrationError(
                "Buildium Bank Account mapping is inconsistent and cannot define Quick Deposit parent scope."
            )
    return [mapping.source_id for mapping in mappings]


@router.post(
    "/runs/{run_id}/quick-deposits/api-dry-run",
    response_model=BuildiumQuickDepositDryRunOut,
)
def api_dry_run_buildium_quick_deposits(
    run_id: int,
    payload: BuildiumApiQuickDepositDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        fetched = fetch_quick_deposits(
            expected_source_account_ref=run.source_account_ref,
            parent_bank_account_ids=_quick_deposit_api_parent_source_ids(db, run=run),
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
        result = dry_run_quick_deposits(
            db, run=run, records=fetched.records, resolutions=resolutions
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="buildium_quick_deposits_api_dry_run",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "BANK_QUICK_DEPOSITS",
                    "fingerprint": result.fingerprint,
                    "total": result.total,
                    "reviewable": result.reviewable,
                    "skipped_review": result.skipped_review,
                    "invalid": result.invalid,
                    "warning_count": result.warning_count,
                    "target_adjustments_created": False,
                    "gl_history_created": False,
                    "bank_balances_changed": False,
                    "clearing_state_changed": False,
                    "transport": "SERVER_TO_SERVER",
                    "transport_mode": fetched.mode.upper(),
                    "transport_request_count": fetched.request_count,
                    "transport_parent_bank_account_count": fetched.parent_record_count,
                    "transport_quick_deposit_count": len(fetched.records),
                    "transport_start_date": payload.start_date.isoformat(),
                    "transport_end_date": payload.end_date.isoformat(),
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
    except BuildiumQuickDepositMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return BuildiumQuickDepositDryRunOut(
        run_id=run.id, organization_id=run.organization_id, provider=run.provider,
        fingerprint=result.fingerprint, replayed=result.replayed, total=result.total,
        reviewable=result.reviewable, skipped_review=result.skipped_review,
        invalid=result.invalid, warning_count=result.warning_count, rows=result.rows,
    )


@router.post(
    "/runs/{run_id}/quick-deposits/api-commit",
    response_model=BuildiumQuickDepositCommitOut,
)
def api_commit_buildium_quick_deposits(
    run_id: int,
    payload: BuildiumApiQuickDepositCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        fetched = fetch_quick_deposits(
            expected_source_account_ref=run.source_account_ref,
            parent_bank_account_ids=_quick_deposit_api_parent_source_ids(db, run=run),
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
        result = commit_quick_deposits(
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
                action="buildium_quick_deposits_api_reconciled",
                new_value={
                    "provider": "BUILDIUM",
                    "resource": "BANK_QUICK_DEPOSITS",
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "warning_count": result.warning_count,
                    "target_adjustments_created": False,
                    "gl_history_created": False,
                    "bank_balances_changed": False,
                    "clearing_state_changed": False,
                    "transport": "SERVER_TO_SERVER",
                    "transport_mode": fetched.mode.upper(),
                    "transport_request_count": fetched.request_count,
                    "transport_parent_bank_account_count": fetched.parent_record_count,
                    "transport_quick_deposit_count": len(fetched.records),
                    "transport_start_date": payload.start_date.isoformat(),
                    "transport_end_date": payload.end_date.isoformat(),
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
    except BuildiumQuickDepositMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Quick Deposit API mapping conflicted with an existing migration mapping.",
        ) from exc
    return BuildiumQuickDepositCommitOut(
        run_id=run.id, organization_id=run.organization_id, provider=run.provider,
        fingerprint=result.fingerprint, replayed=result.replayed,
        matched_existing=result.matched_existing, skipped_review=result.skipped_review,
        warning_count=result.warning_count, rows=result.rows,
    )


@router.post("/runs/{run_id}/quick-deposits/dry-run", response_model=BuildiumQuickDepositDryRunOut)
def dry_run_buildium_quick_deposits(
    run_id: int,
    payload: BuildiumQuickDepositDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        result = dry_run_quick_deposits(db, run=run, records=payload.records, resolutions=resolutions)
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="buildium_quick_deposits_dry_run",
                new_value={
                    "provider": "BUILDIUM", "resource": "BANK_QUICK_DEPOSITS",
                    "fingerprint": result.fingerprint, "total": result.total,
                    "reviewable": result.reviewable, "skipped_review": result.skipped_review,
                    "invalid": result.invalid, "warning_count": result.warning_count,
                    "target_adjustments_created": False, "gl_history_created": False,
                    "bank_balances_changed": False, "clearing_state_changed": False,
                    "raw_payload_stored": False, "provider_credentials_stored": False,
                },
            )
            db.commit()
    except BuildiumQuickDepositMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return BuildiumQuickDepositDryRunOut(
        run_id=run.id, organization_id=run.organization_id, provider=run.provider,
        fingerprint=result.fingerprint, replayed=result.replayed, total=result.total,
        reviewable=result.reviewable, skipped_review=result.skipped_review,
        invalid=result.invalid, warning_count=result.warning_count, rows=result.rows,
    )

@router.post("/runs/{run_id}/quick-deposits/commit", response_model=BuildiumQuickDepositCommitOut)
def commit_buildium_quick_deposits(
    run_id: int,
    payload: BuildiumQuickDepositCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        result = commit_quick_deposits(
            db, run=run, records=payload.records,
            expected_fingerprint=payload.fingerprint,
            platform_user_id=current_user.id, resolutions=resolutions,
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="buildium_quick_deposits_reconciled",
                new_value={
                    "provider": "BUILDIUM", "resource": "BANK_QUICK_DEPOSITS",
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "target_adjustments_created": False, "gl_history_created": False,
                    "bank_balances_changed": False, "clearing_state_changed": False,
                    "raw_payload_stored": False, "provider_credentials_stored": False,
                },
            )
        db.commit()
    except BuildiumQuickDepositMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Quick Deposit mapping conflicted with an existing migration mapping.",
        ) from exc
    return BuildiumQuickDepositCommitOut(
        run_id=run.id, organization_id=run.organization_id, provider=run.provider,
        fingerprint=result.fingerprint, replayed=result.replayed,
        matched_existing=result.matched_existing, skipped_review=result.skipped_review,
        warning_count=result.warning_count, rows=result.rows,
    )
