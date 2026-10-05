"""Buildium bank-transfer existing-target routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.platform_user import PlatformUser
from app.routers.buildium_migrations import _run
from app.routers.platform_auth import get_current_platform_user
from app.schemas.buildium_bank_transfer_migration import (
    BuildiumBankTransferCommitIn,
    BuildiumBankTransferCommitOut,
    BuildiumBankTransferDryRunIn,
    BuildiumBankTransferDryRunOut,
)
from app.services.audit import append_audit_log
from app.services.buildium_bank_transfer_migration import (
    BuildiumBankTransferMigrationError,
    commit_bank_transfers,
    dry_run_bank_transfers,
)

router = APIRouter(prefix="/api/platform/migrations/buildium", tags=["Platform Buildium Migration"])


@router.post("/runs/{run_id}/bank-transfers/dry-run", response_model=BuildiumBankTransferDryRunOut)
def dry_run_buildium_bank_transfers(
    run_id: int,
    payload: BuildiumBankTransferDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        result = dry_run_bank_transfers(db, run=run, records=payload.records, resolutions=resolutions)
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="buildium_bank_transfers_dry_run",
                new_value={
                    "provider": "BUILDIUM", "resource": "BANK_TRANSFERS",
                    "fingerprint": result.fingerprint, "total": result.total,
                    "reviewable": result.reviewable, "skipped_review": result.skipped_review,
                    "invalid": result.invalid, "warning_count": result.warning_count,
                    "target_transfers_created": False, "gl_history_created": False,
                    "bank_balances_changed": False, "clearing_state_changed": False,
                    "raw_payload_stored": False, "provider_credentials_stored": False,
                },
            )
            db.commit()
    except BuildiumBankTransferMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return BuildiumBankTransferDryRunOut(
        run_id=run.id, organization_id=run.organization_id, provider=run.provider,
        fingerprint=result.fingerprint, replayed=result.replayed, total=result.total,
        reviewable=result.reviewable, skipped_review=result.skipped_review,
        invalid=result.invalid, warning_count=result.warning_count, rows=result.rows,
    )


@router.post("/runs/{run_id}/bank-transfers/commit", response_model=BuildiumBankTransferCommitOut)
def commit_buildium_bank_transfers(
    run_id: int,
    payload: BuildiumBankTransferCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    resolutions = [item.model_dump() for item in payload.resolutions]
    try:
        result = commit_bank_transfers(
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
                action="buildium_bank_transfers_reconciled",
                new_value={
                    "provider": "BUILDIUM", "resource": "BANK_TRANSFERS",
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "target_transfers_created": False, "gl_history_created": False,
                    "bank_balances_changed": False, "clearing_state_changed": False,
                    "raw_payload_stored": False, "provider_credentials_stored": False,
                },
            )
        db.commit()
    except BuildiumBankTransferMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Buildium Bank Transfer mapping conflicted with an existing migration mapping.") from exc

    return BuildiumBankTransferCommitOut(
        run_id=run.id, organization_id=run.organization_id, provider=run.provider,
        fingerprint=result.fingerprint, replayed=result.replayed,
        matched_existing=result.matched_existing, skipped_review=result.skipped_review,
        warning_count=result.warning_count, rows=result.rows,
    )
