"""Platform-run AppFolio migration foundation.

This phase intentionally has no outbound AppFolio transport yet. The public
AppFolio API surface is known, but customer-specific credentials/provider
authorization are not stored or guessed here. Platform staff can establish a
target run and dry-run Property records supplied by a future verified adapter.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.platform_migration import PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.user import Organization
from app.routers.platform_auth import get_current_platform_user
from app.schemas.platform_migration import (
    AppFolioMigrationRunCreateIn,
    AppFolioMigrationRunOut,
    AppFolioPropertyDryRunIn,
    AppFolioPropertyDryRunOut,
)
from app.services.appfolio_migration import dry_run_properties
from app.services.audit import append_audit_log


router = APIRouter(
    prefix="/api/platform/migrations/appfolio",
    tags=["Platform AppFolio Migration"],
)

_VIEW_ROLES = {
    PlatformUserRole.PLATFORM_ADMIN,
    PlatformUserRole.PLATFORM_TECH,
    PlatformUserRole.PLATFORM_SUPPORT,
    PlatformUserRole.PLATFORM_DEV,
}
_WRITE_ROLES = {
    PlatformUserRole.PLATFORM_ADMIN,
    PlatformUserRole.PLATFORM_TECH,
    PlatformUserRole.PLATFORM_DEV,
}


def _require_role(
    user: PlatformUser,
    allowed: set[PlatformUserRole],
    detail: str,
) -> None:
    if user.role not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _target_org(db: Session, organization_id: int) -> Organization:
    row = (
        db.query(Organization)
        .filter(
            Organization.id == organization_id,
            Organization.is_active.is_(True),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Target organization not found.")
    return row


def _run(
    db: Session,
    *,
    run_id: int,
    current_user: PlatformUser,
    write: bool,
) -> PlatformMigrationRun:
    _require_role(
        current_user,
        _WRITE_ROLES if write else _VIEW_ROLES,
        "Platform migration access required.",
    )
    row = (
        db.query(PlatformMigrationRun)
        .filter(
            PlatformMigrationRun.id == run_id,
            PlatformMigrationRun.provider == "APPFOLIO",
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="AppFolio migration run not found.")
    _target_org(db, row.organization_id)
    return row


@router.get("/runs", response_model=list[AppFolioMigrationRunOut])
def list_runs(
    response: Response,
    organization_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    _require_role(current_user, _VIEW_ROLES, "Platform migration access required.")
    query = db.query(PlatformMigrationRun).filter(
        PlatformMigrationRun.provider == "APPFOLIO"
    )
    if organization_id is not None:
        _target_org(db, organization_id)
        query = query.filter(PlatformMigrationRun.organization_id == organization_id)
    rows = (
        query.order_by(
            PlatformMigrationRun.created_at.desc(),
            PlatformMigrationRun.id.desc(),
        )
        .limit(limit)
        .all()
    )
    response.headers["Cache-Control"] = "no-store"
    return rows


@router.get("/runs/{run_id}", response_model=AppFolioMigrationRunOut)
def get_run(
    run_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=False)
    response.headers["Cache-Control"] = "no-store"
    return row


@router.post(
    "/runs",
    response_model=AppFolioMigrationRunOut,
    status_code=status.HTTP_201_CREATED,
)
def create_run(
    payload: AppFolioMigrationRunCreateIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    _require_role(
        current_user,
        _WRITE_ROLES,
        "Platform admin, tech, or dev role required for migrations.",
    )
    org = _target_org(db, payload.organization_id)
    row = PlatformMigrationRun(
        organization_id=org.id,
        provider="APPFOLIO",
        source_account_ref=payload.source_account_ref,
        status="DRAFT",
        created_by_platform_user_id=current_user.id,
    )
    db.add(row)
    db.flush()
    append_audit_log(
        db,
        platform_user_id=current_user.id,
        organization_id=org.id,
        entity_type="platform_migration_run",
        entity_id=row.id,
        action="created",
        new_value={
            "provider": "APPFOLIO",
            "source_account_ref": row.source_account_ref,
            "status": row.status,
            "credentials_stored": False,
        },
    )
    db.commit()
    db.refresh(row)
    return row


@router.post(
    "/runs/{run_id}/properties/dry-run",
    response_model=AppFolioPropertyDryRunOut,
)
def dry_run_appfolio_properties(
    run_id: int,
    payload: AppFolioPropertyDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    result = dry_run_properties(
        db,
        run=row,
        include_hidden=payload.include_hidden,
        records=payload.records,
    )
    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=row.organization_id,
            entity_type="platform_migration_run",
            entity_id=row.id,
            action="appfolio_properties_dry_run",
            new_value={
                "fingerprint": result.fingerprint,
                **result.summary,
                "raw_payload_stored": False,
                "target_mutation": False,
            },
        )
        db.commit()
        db.refresh(row)

    return AppFolioPropertyDryRunOut(
        run_id=row.id,
        organization_id=row.organization_id,
        provider=row.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        total=result.total,
        importable=result.importable,
        skipped_hidden=result.skipped_hidden,
        invalid=result.invalid,
        warning_count=result.warning_count,
        rows=result.rows,
    )
