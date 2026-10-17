"""Buildium Budget migration endpoints for Phase 4.14.

These endpoints reuse the existing Buildium PlatformMigrationRun and
PlatformMigrationItem architecture. They do not accept provider credentials
or mutate customer budget lines.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.platform_user import PlatformUser
from app.routers.buildium_migrations import _run, _transport_http_error
from app.routers.platform_auth import get_current_platform_user
from app.schemas.buildium_budget_migration import (
    BuildiumApiBudgetCommitIn,
    BuildiumApiBudgetDryRunIn,
    BuildiumBudgetCommitIn,
    BuildiumBudgetCommitOut,
    BuildiumBudgetDryRunIn,
    BuildiumBudgetDryRunOut,
)
from app.services.audit import append_audit_log
from app.services.buildium_api_transport import (
    BuildiumApiTransportError,
    fetch_budgets,
)
from app.services.buildium_budget_migration import (
    BuildiumBudgetMigrationError,
    commit_budgets,
    dry_run_budgets,
)


router = APIRouter(
    prefix="/api/platform/migrations/buildium",
    tags=["Platform Buildium Migration"],
)


@router.post("/runs/{run_id}/budgets/api-dry-run", response_model=BuildiumBudgetDryRunOut)
def api_dry_run_buildium_budgets(
    run_id: int,
    payload: BuildiumApiBudgetDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        fetched = fetch_budgets(expected_source_account_ref=run.source_account_ref)
        result = dry_run_budgets(
            db,
            run=run,
            records=fetched.records,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
    except BuildiumApiTransportError as exc:
        db.rollback()
        raise _transport_http_error(exc) from exc
    except BuildiumBudgetMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=run.organization_id,
            entity_type="platform_migration_run",
            entity_id=run.id,
            action="buildium_budgets_api_dry_run",
            new_value={
                "fingerprint": result.fingerprint,
                **result.summary,
                "customer_budget_mutation": False,
                "gl_history_created": False,
                "transport": "SERVER_TO_SERVER",
                "transport_mode": fetched.mode.upper(),
                "transport_request_count": fetched.request_count,
                "transport_budget_count": len(fetched.records),
                "credentials_stored": False,
                "raw_response_stored": False,
                "provider_budget_name_stored": False,
            },
        )
        db.commit()
        db.refresh(run)

    return BuildiumBudgetDryRunOut(
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


@router.post("/runs/{run_id}/budgets/api-commit", response_model=BuildiumBudgetCommitOut)
def api_commit_buildium_budgets(
    run_id: int,
    payload: BuildiumApiBudgetCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        fetched = fetch_budgets(expected_source_account_ref=run.source_account_ref)
        result = commit_budgets(
            db,
            run=run,
            records=fetched.records,
            expected_fingerprint=payload.fingerprint,
            platform_user_id=current_user.id,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="buildium_budgets_api_reconciled",
                new_value={
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "warning_count": result.warning_count,
                    "target_property_budget_line_ids": [
                        item["target_property_budget_line_id"] for item in result.rows
                    ],
                    "customer_budget_mutation": False,
                    "gl_history_created": False,
                    "transport": "SERVER_TO_SERVER",
                    "transport_mode": fetched.mode.upper(),
                    "transport_request_count": fetched.request_count,
                    "transport_budget_count": len(fetched.records),
                    "credentials_stored": False,
                    "raw_response_stored": False,
                    "provider_budget_name_stored": False,
                },
            )
        db.commit()
        db.refresh(run)
    except BuildiumApiTransportError as exc:
        db.rollback()
        raise _transport_http_error(exc) from exc
    except (BuildiumBudgetMigrationError, IntegrityError) as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return BuildiumBudgetCommitOut(
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


@router.post("/runs/{run_id}/budgets/dry-run", response_model=BuildiumBudgetDryRunOut)
def dry_run_buildium_budgets(
    run_id: int,
    payload: BuildiumBudgetDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = dry_run_budgets(
            db,
            run=run,
            records=payload.records,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
    except BuildiumBudgetMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=run.organization_id,
            entity_type="platform_migration_run",
            entity_id=run.id,
            action="buildium_budgets_dry_run",
            new_value={
                "fingerprint": result.fingerprint,
                **result.summary,
                "customer_budget_mutation": False,
                "gl_history_created": False,
                "raw_payload_stored": False,
                "provider_credentials_stored": False,
            },
        )
        db.commit()
        db.refresh(run)

    return BuildiumBudgetDryRunOut(
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


@router.post("/runs/{run_id}/budgets/commit", response_model=BuildiumBudgetCommitOut)
def commit_buildium_budgets(
    run_id: int,
    payload: BuildiumBudgetCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    run = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = commit_budgets(
            db,
            run=run,
            records=payload.records,
            expected_fingerprint=payload.fingerprint,
            platform_user_id=current_user.id,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=run.organization_id,
                entity_type="platform_migration_run",
                entity_id=run.id,
                action="buildium_budgets_reconciled",
                new_value={
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "target_property_budget_line_ids": [
                        item["target_property_budget_line_id"] for item in result.rows
                    ],
                    "customer_budget_mutation": False,
                    "gl_history_created": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
        db.commit()
        db.refresh(run)
    except BuildiumBudgetMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Budget mapping conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumBudgetCommitOut(
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
