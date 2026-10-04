"""Platform-run Buildium migration foundation for Phase 4.14.

The initial batch maps already-retrieved Buildium v1 rental-property records
through the existing platform migration run/mapping architecture. No Buildium
API key or secret is accepted or persisted here.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.property import Property, Unit
from app.models.vendor import Vendor
from app.models.user import Organization
from app.routers.platform_auth import get_current_platform_user
from app.schemas.buildium_migration import (
    BuildiumMigrationItemOut,
    BuildiumMigrationRunCreateIn,
    BuildiumMigrationRunOut,
    BuildiumPropertyCommitIn,
    BuildiumPropertyCommitOut,
    BuildiumPropertyDryRunIn,
    BuildiumPropertyDryRunOut,
    BuildiumUnitCommitIn,
    BuildiumUnitCommitOut,
    BuildiumUnitDryRunIn,
    BuildiumUnitDryRunOut,
    BuildiumOwnerCommitIn,
    BuildiumOwnerCommitOut,
    BuildiumOwnerDryRunIn,
    BuildiumOwnerDryRunOut,
    BuildiumVendorCommitIn,
    BuildiumVendorCommitOut,
    BuildiumVendorDryRunIn,
    BuildiumVendorDryRunOut,
    BuildiumTenantCommitIn,
    BuildiumTenantCommitOut,
    BuildiumTenantDryRunIn,
    BuildiumTenantDryRunOut,
)
from app.services.audit import append_audit_log
from app.services.buildium_migration import (
    BuildiumMigrationError,
    commit_properties,
    dry_run_properties,
)
from app.services.buildium_unit_migration import (
    BuildiumUnitMigrationError,
    commit_units,
    dry_run_units,
)
from app.services.buildium_owner_migration import (
    BuildiumOwnerMigrationError,
    commit_owners,
    dry_run_owners,
)
from app.services.buildium_vendor_migration import (
    BuildiumVendorMigrationError,
    commit_vendors,
    dry_run_vendors,
)
from app.services.buildium_tenant_migration import (
    BuildiumTenantMigrationError,
    commit_tenants,
    dry_run_tenants,
)


router = APIRouter(
    prefix="/api/platform/migrations/buildium",
    tags=["Platform Buildium Migration"],
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
            PlatformMigrationRun.provider == "BUILDIUM",
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Buildium migration run not found.")
    _target_org(db, row.organization_id)
    return row


@router.get("/runs", response_model=list[BuildiumMigrationRunOut])
def list_runs(
    response: Response,
    organization_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    _require_role(current_user, _VIEW_ROLES, "Platform migration access required.")
    query = db.query(PlatformMigrationRun).filter(
        PlatformMigrationRun.provider == "BUILDIUM"
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


@router.post(
    "/runs",
    response_model=BuildiumMigrationRunOut,
    status_code=status.HTTP_201_CREATED,
)
def create_run(
    payload: BuildiumMigrationRunCreateIn,
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
        provider="BUILDIUM",
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
            "provider": "BUILDIUM",
            "source_account_ref": row.source_account_ref,
            "status": row.status,
            "credentials_stored": False,
        },
    )
    db.commit()
    db.refresh(row)
    return row


@router.get("/runs/{run_id}", response_model=BuildiumMigrationRunOut)
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
    "/runs/{run_id}/properties/dry-run",
    response_model=BuildiumPropertyDryRunOut,
)
def dry_run_buildium_properties(
    run_id: int,
    payload: BuildiumPropertyDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = dry_run_properties(
            db,
            run=row,
            include_inactive=payload.include_inactive,
            records=payload.records,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
    except BuildiumMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=row.organization_id,
            entity_type="platform_migration_run",
            entity_id=row.id,
            action="buildium_properties_dry_run",
            new_value={
                "fingerprint": result.fingerprint,
                **result.summary,
                "target_mutation": False,
            },
        )
        db.commit()
        db.refresh(row)

    return BuildiumPropertyDryRunOut(
        run_id=row.id,
        organization_id=row.organization_id,
        provider=row.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        total=result.total,
        importable=result.importable,
        skipped_inactive=result.skipped_inactive,
        skipped_review=result.skipped_review,
        invalid=result.invalid,
        warning_count=result.warning_count,
        rows=result.rows,
    )


@router.post(
    "/runs/{run_id}/properties/commit",
    response_model=BuildiumPropertyCommitOut,
)
def commit_buildium_properties(
    run_id: int,
    payload: BuildiumPropertyCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = commit_properties(
            db,
            run=row,
            include_inactive=payload.include_inactive,
            records=payload.records,
            expected_fingerprint=payload.fingerprint,
            platform_user_id=current_user.id,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=row.organization_id,
                entity_type="platform_migration_run",
                entity_id=row.id,
                action="buildium_properties_committed",
                new_value={
                    "fingerprint": result.fingerprint,
                    "committed": result.committed,
                    "matched_existing": result.matched_existing,
                    "skipped_inactive": result.skipped_inactive,
                    "skipped_review": result.skipped_review,
                    "warning_count": result.warning_count,
                    "target_property_ids": [
                        item["target_property_id"] for item in result.rows
                    ],
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
            db.commit()
            db.refresh(row)
    except BuildiumMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium property commit conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumPropertyCommitOut(
        run_id=row.id,
        organization_id=row.organization_id,
        provider=row.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        committed=result.committed,
        matched_existing=result.matched_existing,
        skipped_inactive=result.skipped_inactive,
        skipped_review=result.skipped_review,
        warning_count=result.warning_count,
        rows=result.rows,
    )




@router.post(
    "/runs/{run_id}/units/dry-run",
    response_model=BuildiumUnitDryRunOut,
)
def dry_run_buildium_units(
    run_id: int,
    payload: BuildiumUnitDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = dry_run_units(
            db,
            run=row,
            records=payload.records,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
    except BuildiumUnitMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=row.organization_id,
            entity_type="platform_migration_run",
            entity_id=row.id,
            action="buildium_units_dry_run",
            new_value={
                "fingerprint": result.fingerprint,
                **result.summary,
                "target_mutation": False,
            },
        )
        db.commit()
        db.refresh(row)

    return BuildiumUnitDryRunOut(
        run_id=row.id,
        organization_id=row.organization_id,
        provider=row.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        total=result.total,
        importable=result.importable,
        skipped_review=result.skipped_review,
        invalid=result.invalid,
        warning_count=result.warning_count,
        rows=result.rows,
    )


@router.post(
    "/runs/{run_id}/units/commit",
    response_model=BuildiumUnitCommitOut,
)
def commit_buildium_units(
    run_id: int,
    payload: BuildiumUnitCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = commit_units(
            db,
            run=row,
            records=payload.records,
            expected_fingerprint=payload.fingerprint,
            platform_user_id=current_user.id,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=row.organization_id,
                entity_type="platform_migration_run",
                entity_id=row.id,
                action="buildium_units_committed",
                new_value={
                    "fingerprint": result.fingerprint,
                    "committed": result.committed,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "warning_count": result.warning_count,
                    "target_unit_ids": [
                        item["target_unit_id"] for item in result.rows
                    ],
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                    "occupancy_inferred": False,
                    "lease_mutation": False,
                },
            )
            db.commit()
            db.refresh(row)
    except BuildiumUnitMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Unit commit conflicted with an existing migration mapping or target Unit.",
        ) from exc

    return BuildiumUnitCommitOut(
        run_id=row.id,
        organization_id=row.organization_id,
        provider=row.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        committed=result.committed,
        matched_existing=result.matched_existing,
        skipped_review=result.skipped_review,
        warning_count=result.warning_count,
        rows=result.rows,
    )



@router.post(
    "/runs/{run_id}/owners/dry-run",
    response_model=BuildiumOwnerDryRunOut,
)
def dry_run_buildium_owners(
    run_id: int,
    payload: BuildiumOwnerDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = dry_run_owners(
            db,
            run=row,
            include_inactive=payload.include_inactive,
            records=payload.records,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
    except BuildiumOwnerMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=row.organization_id,
            entity_type="platform_migration_run",
            entity_id=row.id,
            action="buildium_owners_dry_run",
            new_value={
                "fingerprint": result.fingerprint,
                **result.summary,
                "target_mutation": False,
            },
        )
        db.commit()
        db.refresh(row)

    return BuildiumOwnerDryRunOut(
        run_id=row.id,
        organization_id=row.organization_id,
        provider=row.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        total=result.total,
        reviewable=result.reviewable,
        skipped_inactive=result.skipped_inactive,
        skipped_review=result.skipped_review,
        invalid=result.invalid,
        warning_count=result.warning_count,
        rows=result.rows,
    )


@router.post(
    "/runs/{run_id}/owners/commit",
    response_model=BuildiumOwnerCommitOut,
)
def commit_buildium_owners(
    run_id: int,
    payload: BuildiumOwnerCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = commit_owners(
            db,
            run=row,
            include_inactive=payload.include_inactive,
            records=payload.records,
            expected_fingerprint=payload.fingerprint,
            platform_user_id=current_user.id,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=row.organization_id,
                entity_type="platform_migration_run",
                entity_id=row.id,
                action="buildium_owners_mapped",
                new_value={
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_inactive": result.skipped_inactive,
                    "skipped_review": result.skipped_review,
                    "target_owner_user_ids": [
                        item["target_owner_user_id"] for item in result.rows
                    ],
                    "owner_users_created": False,
                    "property_owner_links_created": False,
                    "ownership_percentage_inferred": False,
                    "tax_data_stored": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
            db.commit()
            db.refresh(row)
    except BuildiumOwnerMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Owner mapping conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumOwnerCommitOut(
        run_id=row.id,
        organization_id=row.organization_id,
        provider=row.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        matched_existing=result.matched_existing,
        skipped_inactive=result.skipped_inactive,
        skipped_review=result.skipped_review,
        warning_count=result.warning_count,
        rows=result.rows,
    )



@router.post(
    "/runs/{run_id}/vendors/dry-run",
    response_model=BuildiumVendorDryRunOut,
)
def dry_run_buildium_vendors(
    run_id: int,
    payload: BuildiumVendorDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = dry_run_vendors(
            db,
            run=row,
            records=payload.records,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
    except BuildiumVendorMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=row.organization_id,
            entity_type="platform_migration_run",
            entity_id=row.id,
            action="buildium_vendors_dry_run",
            new_value={
                "fingerprint": result.fingerprint,
                **result.summary,
                "target_mutation": False,
            },
        )
        db.commit()
        db.refresh(row)

    return BuildiumVendorDryRunOut(
        run_id=row.id,
        organization_id=row.organization_id,
        provider=row.provider,
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
    "/runs/{run_id}/vendors/commit",
    response_model=BuildiumVendorCommitOut,
)
def commit_buildium_vendors(
    run_id: int,
    payload: BuildiumVendorCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = commit_vendors(
            db,
            run=row,
            records=payload.records,
            expected_fingerprint=payload.fingerprint,
            platform_user_id=current_user.id,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=row.organization_id,
                entity_type="platform_migration_run",
                entity_id=row.id,
                action="buildium_vendors_mapped",
                new_value={
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "target_vendor_ids": [item["target_vendor_id"] for item in result.rows],
                    "vendors_created": False,
                    "preferred_vendor_links_created": False,
                    "trade_inferred": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
            db.commit()
            db.refresh(row)
    except BuildiumVendorMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Vendor mapping conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumVendorCommitOut(
        run_id=row.id,
        organization_id=row.organization_id,
        provider=row.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        matched_existing=result.matched_existing,
        skipped_review=result.skipped_review,
        warning_count=result.warning_count,
        rows=result.rows,
    )



@router.post(
    "/runs/{run_id}/tenants/dry-run",
    response_model=BuildiumTenantDryRunOut,
)
def dry_run_buildium_tenants(
    run_id: int,
    payload: BuildiumTenantDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = dry_run_tenants(
            db,
            run=row,
            records=payload.records,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
    except BuildiumTenantMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=row.organization_id,
            entity_type="platform_migration_run",
            entity_id=row.id,
            action="buildium_tenants_dry_run",
            new_value={
                "fingerprint": result.fingerprint,
                **result.summary,
                "target_mutation": False,
            },
        )
        db.commit()
        db.refresh(row)

    return BuildiumTenantDryRunOut(
        run_id=row.id,
        organization_id=row.organization_id,
        provider=row.provider,
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
    "/runs/{run_id}/tenants/commit",
    response_model=BuildiumTenantCommitOut,
)
def commit_buildium_tenants(
    run_id: int,
    payload: BuildiumTenantCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = commit_tenants(
            db,
            run=row,
            records=payload.records,
            expected_fingerprint=payload.fingerprint,
            platform_user_id=current_user.id,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
        if not result.replayed:
            append_audit_log(
                db,
                platform_user_id=current_user.id,
                organization_id=row.organization_id,
                entity_type="platform_migration_run",
                entity_id=row.id,
                action="buildium_tenants_mapped",
                new_value={
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "target_tenant_user_ids": [
                        item["target_tenant_user_id"] for item in result.rows
                    ],
                    "tenant_users_created": False,
                    "leases_created": False,
                    "occupancy_inferred": False,
                    "tax_data_stored": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
            db.commit()
            db.refresh(row)
    except BuildiumTenantMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Tenant mapping conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumTenantCommitOut(
        run_id=row.id,
        organization_id=row.organization_id,
        provider=row.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        matched_existing=result.matched_existing,
        skipped_review=result.skipped_review,
        warning_count=result.warning_count,
        rows=result.rows,
    )

@router.get(
    "/runs/{run_id}/items",
    response_model=list[BuildiumMigrationItemOut],
)
def list_migration_items(
    run_id: int,
    response: Response,
    resource: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=False)

    inconsistent = (
        db.query(PlatformMigrationItem.id)
        .filter(
            PlatformMigrationItem.run_id == row.id,
            (
                (PlatformMigrationItem.organization_id != row.organization_id)
                | (PlatformMigrationItem.provider != "BUILDIUM")
            ),
        )
        .first()
    )
    if inconsistent is not None:
        raise HTTPException(status_code=404, detail="Buildium migration run not found.")

    query = db.query(PlatformMigrationItem).filter(
        PlatformMigrationItem.run_id == row.id,
        PlatformMigrationItem.organization_id == row.organization_id,
        PlatformMigrationItem.provider == "BUILDIUM",
    )
    if resource is not None:
        normalized = resource.strip().upper()
        if not normalized:
            raise HTTPException(status_code=422, detail="resource cannot be blank.")
        query = query.filter(PlatformMigrationItem.resource == normalized)

    items = (
        query.order_by(
            PlatformMigrationItem.resource.asc(),
            PlatformMigrationItem.source_id.asc(),
            PlatformMigrationItem.id.asc(),
        )
        .limit(limit)
        .all()
    )

    result: list[BuildiumMigrationItemOut] = []
    for item in items:
        target_exists = False
        target_label = None
        if item.target_entity == "PROPERTY":
            target = (
                db.query(Property)
                .filter(
                    Property.id == item.target_id,
                    Property.organization_id == row.organization_id,
                )
                .first()
            )
            if target is not None:
                target_exists = True
                target_label = target.name
        elif item.target_entity == "UNIT":
            target = (
                db.query(Unit)
                .join(Property, Property.id == Unit.property_id)
                .filter(
                    Unit.id == item.target_id,
                    Property.organization_id == row.organization_id,
                )
                .first()
            )
            if target is not None:
                target_exists = True
                target_label = target.unit_number
        elif item.target_entity == "OWNER_USER":
            from app.models.user import User, UserRole
            target = (
                db.query(User)
                .filter(
                    User.id == item.target_id,
                    User.organization_id == row.organization_id,
                    User.role == UserRole.OWNER,
                )
                .first()
            )
            if target is not None:
                target_exists = True
                target_label = target.email
        elif item.target_entity == "VENDOR":
            target = (
                db.query(Vendor)
                .filter(
                    Vendor.id == item.target_id,
                    Vendor.organization_id == row.organization_id,
                )
                .first()
            )
            if target is not None:
                target_exists = True
                target_label = target.company_name
        elif item.target_entity == "TENANT_USER":
            from app.models.user import User, UserRole
            target = (
                db.query(User)
                .filter(
                    User.id == item.target_id,
                    User.organization_id == row.organization_id,
                    User.role == UserRole.TENANT,
                )
                .first()
            )
            if target is not None:
                target_exists = True
                target_label = target.email
        result.append(
            BuildiumMigrationItemOut(
                id=item.id,
                run_id=item.run_id,
                organization_id=item.organization_id,
                provider=item.provider,
                resource=item.resource,
                source_id=item.source_id,
                target_entity=item.target_entity,
                target_id=item.target_id,
                target_exists=target_exists,
                target_label=target_label,
                source_fingerprint=item.source_fingerprint,
                created_by_platform_user_id=item.created_by_platform_user_id,
                created_at=item.created_at,
            )
        )
    response.headers["Cache-Control"] = "no-store"
    return result
