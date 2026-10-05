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
from app.models.property import Property, PropertyOwner, Unit
from app.models.property_group import PropertyGroup
from app.models.property_budget import PropertyBudgetLine
from app.models.lease import Lease
from app.models.gl_account import GLAccount
from app.models.vendor import Vendor
from app.models.work_order import WorkOrder
from app.models.bill import Bill
from app.models.bank_account import BankAccount
from app.models.bank_reconciliation import BankReconciliation
from app.models.check import Check
from app.models.charge import Charge
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
    BuildiumLeaseCommitIn,
    BuildiumLeaseCommitOut,
    BuildiumLeaseDryRunIn,
    BuildiumLeaseDryRunOut,
    BuildiumGLAccountCommitIn,
    BuildiumGLAccountCommitOut,
    BuildiumGLAccountDryRunIn,
    BuildiumGLAccountDryRunOut,
    BuildiumWorkOrderCommitIn,
    BuildiumWorkOrderCommitOut,
    BuildiumWorkOrderDryRunIn,
    BuildiumWorkOrderDryRunOut,
    BuildiumBillCommitIn,
    BuildiumBillCommitOut,
    BuildiumBillDryRunIn,
    BuildiumBillDryRunOut,
    BuildiumBankAccountCommitIn,
    BuildiumBankAccountCommitOut,
    BuildiumBankAccountDryRunIn,
    BuildiumBankAccountDryRunOut,
    BuildiumBillPaymentCommitIn,
    BuildiumBillPaymentCommitOut,
    BuildiumBillPaymentDryRunIn,
    BuildiumBillPaymentDryRunOut,
    BuildiumOwnerPropertyCommitIn,
    BuildiumOwnerPropertyCommitOut,
    BuildiumOwnerPropertyDryRunIn,
    BuildiumOwnerPropertyDryRunOut,
    BuildiumPropertyGroupCommitIn,
    BuildiumPropertyGroupCommitOut,
    BuildiumPropertyGroupDryRunIn,
    BuildiumPropertyGroupDryRunOut,
    BuildiumPropertyReserveCommitIn,
    BuildiumPropertyReserveCommitOut,
    BuildiumPropertyReserveDryRunIn,
    BuildiumPropertyReserveDryRunOut,
    BuildiumLeaseChargeCommitIn,
    BuildiumLeaseChargeCommitOut,
    BuildiumLeaseChargeDryRunIn,
    BuildiumLeaseChargeDryRunOut,
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
from app.services.buildium_lease_migration import (
    BuildiumLeaseMigrationError,
    commit_leases,
    dry_run_leases,
)
from app.services.buildium_gl_account_migration import (
    BuildiumGLAccountMigrationError,
    commit_gl_accounts,
    dry_run_gl_accounts,
)
from app.services.buildium_work_order_migration import (
    BuildiumWorkOrderMigrationError,
    commit_work_orders,
    dry_run_work_orders,
)
from app.services.buildium_bill_migration import (
    BuildiumBillMigrationError,
    commit_bills,
    dry_run_bills,
)
from app.services.buildium_bank_account_migration import (
    BuildiumBankAccountMigrationError,
    commit_bank_accounts,
    dry_run_bank_accounts,
)
from app.services.buildium_bill_payment_migration import (
    BuildiumBillPaymentMigrationError,
    commit_bill_payments,
    dry_run_bill_payments,
)
from app.services.buildium_owner_property_migration import (
    BuildiumOwnerPropertyMigrationError,
    commit_owner_property_relationships,
    dry_run_owner_property_relationships,
)
from app.services.buildium_property_group_migration import (
    BuildiumPropertyGroupMigrationError,
    commit_property_groups,
    dry_run_property_groups,
)
from app.services.buildium_property_reserve_migration import (
    BuildiumPropertyReserveMigrationError,
    commit_property_reserves,
    dry_run_property_reserves,
)
from app.services.buildium_lease_charge_migration import (
    BuildiumLeaseChargeMigrationError,
    commit_lease_charges,
    dry_run_lease_charges,
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



@router.post(
    "/runs/{run_id}/leases/dry-run",
    response_model=BuildiumLeaseDryRunOut,
)
def dry_run_buildium_leases(
    run_id: int,
    payload: BuildiumLeaseDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = dry_run_leases(
            db,
            run=row,
            records=payload.records,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
    except BuildiumLeaseMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=row.organization_id,
            entity_type="platform_migration_run",
            entity_id=row.id,
            action="buildium_leases_dry_run",
            new_value={
                "fingerprint": result.fingerprint,
                **result.summary,
                "target_mutation": False,
            },
        )
        db.commit()
        db.refresh(row)

    return BuildiumLeaseDryRunOut(
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
    "/runs/{run_id}/leases/commit",
    response_model=BuildiumLeaseCommitOut,
)
def commit_buildium_leases(
    run_id: int,
    payload: BuildiumLeaseCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = commit_leases(
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
                action="buildium_leases_reconciled",
                new_value={
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "warning_count": result.warning_count,
                    "target_lease_ids": [
                        item["target_lease_id"] for item in result.rows
                    ],
                    "leases_created": False,
                    "leases_updated": False,
                    "occupancy_inferred": False,
                    "rent_or_deposit_created": False,
                    "charges_created": False,
                    "payments_created": False,
                    "gl_history_created": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
            db.commit()
            db.refresh(row)
    except BuildiumLeaseMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Lease relationship mapping conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumLeaseCommitOut(
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
    "/runs/{run_id}/gl-accounts/dry-run",
    response_model=BuildiumGLAccountDryRunOut,
)
def dry_run_buildium_gl_accounts(
    run_id: int,
    payload: BuildiumGLAccountDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = dry_run_gl_accounts(
            db,
            run=row,
            include_inactive=payload.include_inactive,
            records=payload.records,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
    except BuildiumGLAccountMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=row.organization_id,
            entity_type="platform_migration_run",
            entity_id=row.id,
            action="buildium_gl_accounts_dry_run",
            new_value={
                "fingerprint": result.fingerprint,
                **result.summary,
                "target_mutation": False,
            },
        )
        db.commit()
        db.refresh(row)

    return BuildiumGLAccountDryRunOut(
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
    "/runs/{run_id}/gl-accounts/commit",
    response_model=BuildiumGLAccountCommitOut,
)
def commit_buildium_gl_accounts(
    run_id: int,
    payload: BuildiumGLAccountCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = commit_gl_accounts(
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
                action="buildium_gl_accounts_mapped",
                new_value={
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_inactive": result.skipped_inactive,
                    "skipped_review": result.skipped_review,
                    "warning_count": result.warning_count,
                    "target_gl_account_ids": [
                        item["target_gl_account_id"] for item in result.rows
                    ],
                    "gl_accounts_created": False,
                    "gl_accounts_updated": False,
                    "balances_created": False,
                    "transactions_created": False,
                    "bank_accounts_created": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
            db.commit()
            db.refresh(row)
    except BuildiumGLAccountMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium GL account mapping conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumGLAccountCommitOut(
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
    "/runs/{run_id}/work-orders/dry-run",
    response_model=BuildiumWorkOrderDryRunOut,
)
def dry_run_buildium_work_orders(
    run_id: int,
    payload: BuildiumWorkOrderDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = dry_run_work_orders(
            db,
            run=row,
            records=payload.records,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
    except BuildiumWorkOrderMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=row.organization_id,
            entity_type="platform_migration_run",
            entity_id=row.id,
            action="buildium_work_orders_dry_run",
            new_value={
                "fingerprint": result.fingerprint,
                **result.summary,
                "target_mutation": False,
            },
        )
        db.commit()
        db.refresh(row)

    return BuildiumWorkOrderDryRunOut(
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
    "/runs/{run_id}/work-orders/commit",
    response_model=BuildiumWorkOrderCommitOut,
)
def commit_buildium_work_orders(
    run_id: int,
    payload: BuildiumWorkOrderCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = commit_work_orders(
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
                action="buildium_work_orders_reconciled",
                new_value={
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "warning_count": result.warning_count,
                    "target_work_order_ids": [
                        item["target_work_order_id"] for item in result.rows
                    ],
                    "work_orders_created": False,
                    "work_orders_updated": False,
                    "tenant_inferred": False,
                    "assignment_mutation": False,
                    "status_mutation": False,
                    "cost_mutation": False,
                    "bills_created": False,
                    "gl_history_created": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
            db.commit()
            db.refresh(row)
    except BuildiumWorkOrderMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Work Order relationship mapping conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumWorkOrderCommitOut(
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
    "/runs/{run_id}/bills/dry-run",
    response_model=BuildiumBillDryRunOut,
)
def dry_run_buildium_bills(
    run_id: int,
    payload: BuildiumBillDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = dry_run_bills(
            db,
            run=row,
            records=payload.records,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
    except BuildiumBillMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=row.organization_id,
            entity_type="platform_migration_run",
            entity_id=row.id,
            action="buildium_bills_dry_run",
            new_value={
                "fingerprint": result.fingerprint,
                **result.summary,
                "target_mutation": False,
            },
        )
        db.commit()
        db.refresh(row)

    return BuildiumBillDryRunOut(
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
    "/runs/{run_id}/bills/commit",
    response_model=BuildiumBillCommitOut,
)
def commit_buildium_bills(
    run_id: int,
    payload: BuildiumBillCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = commit_bills(
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
                action="buildium_bills_reconciled",
                new_value={
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "warning_count": result.warning_count,
                    "target_bill_ids": [item["target_bill_id"] for item in result.rows],
                    "bills_created": False,
                    "bills_updated": False,
                    "bill_lines_created": False,
                    "payable_posting_created": False,
                    "payments_created": False,
                    "checks_created": False,
                    "bank_movement_created": False,
                    "vendor_credits_created": False,
                    "gl_history_created": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
            db.commit()
            db.refresh(row)
    except BuildiumBillMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Bill relationship mapping conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumBillCommitOut(
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
    "/runs/{run_id}/bank-accounts/dry-run",
    response_model=BuildiumBankAccountDryRunOut,
)
def dry_run_buildium_bank_accounts(
    run_id: int,
    payload: BuildiumBankAccountDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = dry_run_bank_accounts(
            db,
            run=row,
            include_inactive=payload.include_inactive,
            records=payload.records,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
    except BuildiumBankAccountMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=row.organization_id,
            entity_type="platform_migration_run",
            entity_id=row.id,
            action="buildium_bank_accounts_dry_run",
            new_value={
                "fingerprint": result.fingerprint,
                **result.summary,
                "target_mutation": False,
            },
        )
        db.commit()
        db.refresh(row)

    return BuildiumBankAccountDryRunOut(
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
    "/runs/{run_id}/bank-accounts/commit",
    response_model=BuildiumBankAccountCommitOut,
)
def commit_buildium_bank_accounts(
    run_id: int,
    payload: BuildiumBankAccountCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = commit_bank_accounts(
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
                action="buildium_bank_accounts_reconciled",
                new_value={
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_inactive": result.skipped_inactive,
                    "skipped_review": result.skipped_review,
                    "warning_count": result.warning_count,
                    "target_bank_account_ids": [
                        item["target_bank_account_id"] for item in result.rows
                    ],
                    "bank_accounts_created": False,
                    "bank_accounts_updated": False,
                    "account_numbers_copied": False,
                    "routing_numbers_copied": False,
                    "balances_imported": False,
                    "reconciliation_state_imported": False,
                    "bank_movement_created": False,
                    "gl_history_created": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
            db.commit()
            db.refresh(row)
    except BuildiumBankAccountMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Bank Account mapping conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumBankAccountCommitOut(
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
    "/runs/{run_id}/bill-payments/dry-run",
    response_model=BuildiumBillPaymentDryRunOut,
)
def dry_run_buildium_bill_payments(
    run_id: int,
    payload: BuildiumBillPaymentDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = dry_run_bill_payments(
            db,
            run=row,
            records=payload.records,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
    except BuildiumBillPaymentMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=row.organization_id,
            entity_type="platform_migration_run",
            entity_id=row.id,
            action="buildium_bill_payments_dry_run",
            new_value={
                "fingerprint": result.fingerprint,
                **result.summary,
                "target_mutation": False,
            },
        )
        db.commit()
        db.refresh(row)

    return BuildiumBillPaymentDryRunOut(
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
    "/runs/{run_id}/bill-payments/commit",
    response_model=BuildiumBillPaymentCommitOut,
)
def commit_buildium_bill_payments(
    run_id: int,
    payload: BuildiumBillPaymentCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = commit_bill_payments(
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
                action="buildium_bill_payments_reconciled",
                new_value={
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "warning_count": result.warning_count,
                    "target_check_ids": [
                        item["target_check_id"] for item in result.rows
                    ],
                    "checks_created": False,
                    "checks_updated": False,
                    "bills_updated": False,
                    "payments_posted": False,
                    "bank_movements_created": False,
                    "vendor_credits_applied": False,
                    "gl_history_created": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
            db.commit()
            db.refresh(row)
    except BuildiumBillPaymentMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Bill Payment mapping conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumBillPaymentCommitOut(
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
    "/runs/{run_id}/owner-property-relationships/dry-run",
    response_model=BuildiumOwnerPropertyDryRunOut,
)
def dry_run_buildium_owner_property_relationships(
    run_id: int,
    payload: BuildiumOwnerPropertyDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = dry_run_owner_property_relationships(
            db,
            run=row,
            records=payload.records,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
    except BuildiumOwnerPropertyMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=row.organization_id,
            entity_type="platform_migration_run",
            entity_id=row.id,
            action="buildium_owner_properties_dry_run",
            new_value={
                "fingerprint": result.fingerprint,
                **result.summary,
                "target_mutation": False,
            },
        )
        db.commit()
        db.refresh(row)
    return BuildiumOwnerPropertyDryRunOut(
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
    "/runs/{run_id}/owner-property-relationships/commit",
    response_model=BuildiumOwnerPropertyCommitOut,
)
def commit_buildium_owner_property_relationships(
    run_id: int,
    payload: BuildiumOwnerPropertyCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = commit_owner_property_relationships(
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
                action="buildium_owner_properties_reconciled",
                new_value={
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "warning_count": result.warning_count,
                    "target_property_owner_ids": [
                        item["target_property_owner_id"] for item in result.rows
                    ],
                    "property_owner_rows_created": False,
                    "property_owner_rows_updated": False,
                    "ownership_percentage_imported": False,
                    "primary_owner_imported": False,
                    "tax_information_imported": False,
                    "gl_history_created": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
            db.commit()
            db.refresh(row)
    except BuildiumOwnerPropertyMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium owner/property mapping conflicted with an existing migration mapping.",
        ) from exc
    return BuildiumOwnerPropertyCommitOut(
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
    "/runs/{run_id}/property-groups/dry-run",
    response_model=BuildiumPropertyGroupDryRunOut,
)
def dry_run_buildium_property_groups(
    run_id: int,
    payload: BuildiumPropertyGroupDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = dry_run_property_groups(
            db,
            run=row,
            records=payload.records,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
    except BuildiumPropertyGroupMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=row.organization_id,
            entity_type="platform_migration_run",
            entity_id=row.id,
            action="buildium_property_groups_dry_run",
            new_value={
                "fingerprint": result.fingerprint,
                **result.summary,
                "target_mutation": False,
            },
        )
        db.commit()
        db.refresh(row)
    return BuildiumPropertyGroupDryRunOut(
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
    "/runs/{run_id}/property-groups/commit",
    response_model=BuildiumPropertyGroupCommitOut,
)
def commit_buildium_property_groups(
    run_id: int,
    payload: BuildiumPropertyGroupCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = commit_property_groups(
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
                action="buildium_property_groups_reconciled",
                new_value={
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "warning_count": result.warning_count,
                    "target_property_group_ids": [
                        item["target_property_group_id"] for item in result.rows
                    ],
                    "property_groups_created": False,
                    "property_groups_updated": False,
                    "property_group_memberships_changed": False,
                    "gl_history_created": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
            db.commit()
            db.refresh(row)
    except BuildiumPropertyGroupMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Property Group mapping conflicted with an existing migration mapping.",
        ) from exc
    return BuildiumPropertyGroupCommitOut(
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
        elif item.target_entity == "LEASE_RELATIONSHIP":
            target = (
                db.query(Lease)
                .join(Unit, Unit.id == Lease.unit_id)
                .join(Property, Property.id == Unit.property_id)
                .filter(
                    Lease.id == item.target_id,
                    Property.organization_id == row.organization_id,
                )
                .first()
            )
            if target is not None:
                target_exists = True
                target_label = f"Lease #{target.id}"
        elif item.target_entity == "WORK_ORDER_RELATIONSHIP":
            target = (
                db.query(WorkOrder)
                .join(Unit, Unit.id == WorkOrder.unit_id)
                .join(Property, Property.id == Unit.property_id)
                .filter(
                    WorkOrder.id == item.target_id,
                    WorkOrder.property_id == Property.id,
                    Property.organization_id == row.organization_id,
                )
                .first()
            )
            if target is not None:
                target_exists = True
                target_label = f"Work Order #{target.id}: {target.title}"
        elif item.target_entity == "BILL_RELATIONSHIP":
            target = (
                db.query(Bill)
                .filter(
                    Bill.id == item.target_id,
                    Bill.organization_id == row.organization_id,
                )
                .first()
            )
            if target is not None:
                target_exists = True
                target_label = f"Bill #{target.id}: {target.payee_name}"
        elif item.target_entity == "PROPERTY_OWNER_RELATIONSHIP":
            target = (
                db.query(PropertyOwner)
                .join(Property, Property.id == PropertyOwner.property_id)
                .filter(
                    PropertyOwner.id == item.target_id,
                    PropertyOwner.organization_id == row.organization_id,
                    Property.organization_id == row.organization_id,
                )
                .first()
            )
            if target is not None:
                target_exists = True
                target_label = f"PropertyOwner #{target.id}: property {target.property_id} / owner {target.user_id}"
        elif item.target_entity == "PROPERTY_GROUP":
            target = (
                db.query(PropertyGroup)
                .filter(
                    PropertyGroup.id == item.target_id,
                    PropertyGroup.organization_id == row.organization_id,
                )
                .first()
            )
            if target is not None:
                target_exists = True
                target_label = target.name
        elif item.target_entity == "CHECK_PAYMENT_RELATIONSHIP":
            target = (
                db.query(Check)
                .filter(
                    Check.id == item.target_id,
                    Check.organization_id == row.organization_id,
                )
                .first()
            )
            if target is not None:
                target_exists = True
                target_label = f"Check #{target.id}: {target.check_number or 'unnumbered'}"
        elif item.target_entity == "BANK_ACCOUNT":
            target = (
                db.query(BankAccount)
                .filter(
                    BankAccount.id == item.target_id,
                    BankAccount.organization_id == row.organization_id,
                )
                .first()
            )
            if target is not None:
                target_exists = True
                target_label = target.name
        elif item.target_entity == "BANK_RECONCILIATION":
            target = (
                db.query(BankReconciliation)
                .filter(
                    BankReconciliation.id == item.target_id,
                    BankReconciliation.organization_id == row.organization_id,
                )
                .first()
            )
            if target is not None:
                target_exists = True
                target_label = (
                    f"Bank Reconciliation #{target.id}: {target.statement_date.isoformat()}"
                )
        elif item.target_entity == "GL_ACCOUNT":
            target = (
                db.query(GLAccount)
                .filter(
                    GLAccount.id == item.target_id,
                    GLAccount.organization_id == row.organization_id,
                )
                .first()
            )
            if target is not None:
                target_exists = True
                target_label = f"{target.gl_number} {target.name}"
        elif item.target_entity == "PROPERTY_BUDGET_LINE":
            target = (
                db.query(PropertyBudgetLine)
                .join(Property, Property.id == PropertyBudgetLine.property_id)
                .filter(
                    PropertyBudgetLine.id == item.target_id,
                    PropertyBudgetLine.organization_id == row.organization_id,
                    Property.organization_id == row.organization_id,
                )
                .first()
            )
            if target is not None:
                target_exists = True
                target_label = (
                    f"Budget {target.calendar_year}-{target.month:02d}: "
                    f"property {target.property_id} / GL {target.gl_account_id}"
                )
        elif item.target_entity == "CHARGE_RELATIONSHIP":
            target = (
                db.query(Charge)
                .filter(
                    Charge.id == item.target_id,
                    Charge.organization_id == row.organization_id,
                    Charge.is_active.is_(True),
                    Charge.deleted_at.is_(None),
                )
                .first()
            )
            if target is not None:
                target_exists = True
                target_label = f"Charge #{target.id}: {target.description}"
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



@router.post(
    "/runs/{run_id}/property-reserves/dry-run",
    response_model=BuildiumPropertyReserveDryRunOut,
)
def dry_run_buildium_property_reserves(
    run_id: int,
    payload: BuildiumPropertyReserveDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = dry_run_property_reserves(
            db,
            run=row,
            records=payload.records,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
    except BuildiumPropertyReserveMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=row.organization_id,
            entity_type="platform_migration_run",
            entity_id=row.id,
            action="buildium_property_reserves_dry_run",
            new_value={
                "fingerprint": result.fingerprint,
                **result.summary,
                "target_mutation": False,
                "reserve_amounts_audited": False,
            },
        )
        db.commit()
        db.refresh(row)

    return BuildiumPropertyReserveDryRunOut(
        run_id=row.id,
        organization_id=row.organization_id,
        provider=row.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        total=result.total,
        reviewable=result.reviewable,
        matched_existing=result.matched_existing,
        apply_source=result.apply_source,
        skipped_review=result.skipped_review,
        invalid=result.invalid,
        warning_count=result.warning_count,
        rows=result.rows,
    )


@router.post(
    "/runs/{run_id}/property-reserves/commit",
    response_model=BuildiumPropertyReserveCommitOut,
)
def commit_buildium_property_reserves(
    run_id: int,
    payload: BuildiumPropertyReserveCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = commit_property_reserves(
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
                action="buildium_property_reserves_committed",
                new_value={
                    "fingerprint": result.fingerprint,
                    "updated": result.updated,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "target_property_ids": [item["target_property_id"] for item in result.rows],
                    "explicit_review_required": True,
                    "reserve_amounts_audited": False,
                    "gl_history_created": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
            db.commit()
            db.refresh(row)
    except BuildiumPropertyReserveMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Property Reserve commit conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumPropertyReserveCommitOut(
        run_id=row.id,
        organization_id=row.organization_id,
        provider=row.provider,
        fingerprint=result.fingerprint,
        replayed=result.replayed,
        updated=result.updated,
        matched_existing=result.matched_existing,
        skipped_review=result.skipped_review,
        warning_count=result.warning_count,
        rows=result.rows,
    )



@router.post(
    "/runs/{run_id}/lease-charges/dry-run",
    response_model=BuildiumLeaseChargeDryRunOut,
)
def dry_run_buildium_lease_charges(
    run_id: int,
    payload: BuildiumLeaseChargeDryRunIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = dry_run_lease_charges(
            db,
            run=row,
            records=payload.records,
            resolutions=[item.model_dump() for item in payload.resolutions],
        )
    except BuildiumLeaseChargeMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if not result.replayed:
        append_audit_log(
            db,
            platform_user_id=current_user.id,
            organization_id=row.organization_id,
            entity_type="platform_migration_run",
            entity_id=row.id,
            action="buildium_lease_charges_dry_run",
            new_value={
                "fingerprint": result.fingerprint,
                **result.summary,
                "target_mutation": False,
                "raw_payload_stored": False,
                "provider_credentials_stored": False,
            },
        )
        db.commit()
        db.refresh(row)

    return BuildiumLeaseChargeDryRunOut(
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
    "/runs/{run_id}/lease-charges/commit",
    response_model=BuildiumLeaseChargeCommitOut,
)
def commit_buildium_lease_charges(
    run_id: int,
    payload: BuildiumLeaseChargeCommitIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    row = _run(db, run_id=run_id, current_user=current_user, write=True)
    try:
        result = commit_lease_charges(
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
                action="buildium_lease_charges_reconciled",
                new_value={
                    "fingerprint": result.fingerprint,
                    "matched_existing": result.matched_existing,
                    "skipped_review": result.skipped_review,
                    "target_charge_ids": [item["target_charge_id"] for item in result.rows],
                    "charge_created": False,
                    "charge_updated": False,
                    "payment_history_reconciled": False,
                    "gl_history_created": False,
                    "raw_payload_stored": False,
                    "provider_credentials_stored": False,
                },
            )
            db.commit()
            db.refresh(row)
    except BuildiumLeaseChargeMigrationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Buildium Lease Charge mapping conflicted with an existing migration mapping.",
        ) from exc

    return BuildiumLeaseChargeCommitOut(
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
