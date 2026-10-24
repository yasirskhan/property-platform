"""Yardi existing-Tenant identity review and metadata-only binding regressions."""
import pytest
from fastapi import HTTPException, Response

from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.user import User, UserRole
from app.routers.yardi_migrations import (
    YardiTenantMatchIn, YardiReviewedPropertyBindingIn,
    bind_yardi_reviewed_tenant_matches, dry_run_yardi_review,
    match_yardi_staged_tenant, get_yardi_reconciliation,
)
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _org, _platform_user, _session


def _seed(db, slug="yardi-tenant-reviewed"):
    actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
    org = _org(db, slug)
    tenant = User(
        organization_id=org.id, role=UserRole.TENANT,
        email=f"{slug}@example.test", hashed_password="preserved-hash",
        first_name="Existing", last_name="Tenant",
        is_active=True,
    )
    run = PlatformMigrationRun(
        organization_id=org.id, provider="YARDI",
        source_account_ref="resident-export", status="DRAFT",
    )
    db.add_all([tenant, run])
    db.commit()
    upload = stage_yardi_file(
        db, run=run, filename="residents.csv",
        content=b"Resident Ref,Full Name\nR-1,Source Resident\n",
        resource_override="TENANTS", sheet_name=None,
        explicit_mapping={"source_id": "Resident Ref", "name": "Full Name"},
        platform_user_id=actor.id,
    )
    db.commit()
    row = db.query(PlatformMigrationStagedRow).filter(
        PlatformMigrationStagedRow.upload_id == upload.upload.id
    ).one()
    return actor, org, tenant, run, row


def test_tenant_review_binding_fingerprint_replay_and_nonmutation():
    db, engine = _session()
    try:
        actor, org, tenant, run, row = _seed(db)
        from app.routers import yardi_migrations as yardi_api
        endpoints = {route.path: route.endpoint for route in yardi_api.router.routes if hasattr(route, "endpoint")}
        base = "/api/platform/migrations/yardi/runs/{run_id}"
        assert endpoints[base + "/staged-rows/{row_id}/match-tenant"] is match_yardi_staged_tenant
        assert endpoints[base + "/bind-reviewed-tenants"] is bind_yardi_reviewed_tenant_matches
        assert match_yardi_staged_tenant(
            run.id, row.id, YardiTenantMatchIn(target_tenant_user_id=tenant.id),
            db, actor,
        )["replayed"] is False
        report = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert report["resource_coverage"]["TENANTS"]["matched_existing"] == 1
        assert match_yardi_staged_tenant(
            run.id, row.id, YardiTenantMatchIn(target_tenant_user_id=tenant.id),
            db, actor,
        )["replayed"] is True
        dry_run = dry_run_yardi_review(run.id, db, actor)
        request = YardiReviewedPropertyBindingIn(
            review_fingerprint=dry_run["review_fingerprint"],
        )
        assert bind_yardi_reviewed_tenant_matches(run.id, request, db, actor)["bound"] == 1
        assert bind_yardi_reviewed_tenant_matches(run.id, request, db, actor)["replayed"] is True
        mapped = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "TENANTS",
        ).one()
        assert mapped.target_entity == "TENANT_USER"
        assert mapped.target_id == tenant.id and mapped.source_id == "R-1"
        assert mapped.source_fingerprint == row.row_fingerprint
        db.refresh(tenant)
        assert tenant.hashed_password == "preserved-hash"
        assert tenant.first_name == "Existing"
        assert db.query(User).filter(User.organization_id == org.id).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_tenant_review_rejects_wrong_role_org_and_inactive_replay():
    db, engine = _session()
    try:
        actor, org, tenant, run, row = _seed(db, "yardi-tenant-role")
        owner = User(
            organization_id=org.id, role=UserRole.OWNER,
            email="other-owner@example.test", hashed_password="owner-hash",
            first_name="Other", last_name="Owner", is_active=True,
        )
        other_org = _org(db, "yardi-tenant-other-org")
        outsider = User(
            organization_id=other_org.id, role=UserRole.TENANT,
            email="outsider@example.test", hashed_password="outsider-hash",
            first_name="Other", last_name="Tenant", is_active=True,
        )
        db.add_all([owner, outsider])
        db.commit()
        for invalid_id in (owner.id, outsider.id):
            with pytest.raises(HTTPException) as wrong:
                match_yardi_staged_tenant(
                    run.id, row.id,
                    YardiTenantMatchIn(target_tenant_user_id=invalid_id),
                    db, actor,
                )
            assert wrong.value.status_code == 404
        match_yardi_staged_tenant(
            run.id, row.id, YardiTenantMatchIn(target_tenant_user_id=tenant.id),
            db, actor,
        )
        tenant.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as deactivated:
            match_yardi_staged_tenant(
                run.id, row.id, YardiTenantMatchIn(target_tenant_user_id=tenant.id),
                db, actor,
            )
        assert deactivated.value.status_code == 404
    finally:
        db.close()
        engine.dispose()


def test_tenant_binding_rejects_stale_fingerprint_and_competing_source_target():
    db, engine = _session()
    try:
        actor, org, tenant, run, row = _seed(db, "yardi-tenant-collision")
        match_yardi_staged_tenant(
            run.id, row.id, YardiTenantMatchIn(target_tenant_user_id=tenant.id),
            db, actor,
        )
        dry_run = dry_run_yardi_review(run.id, db, actor)
        with pytest.raises(HTTPException) as stale:
            bind_yardi_reviewed_tenant_matches(
                run.id, YardiReviewedPropertyBindingIn(review_fingerprint="0" * 64),
                db, actor,
            )
        assert stale.value.status_code == 409
        other = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="other-resident-export", status="DRAFT",
        )
        db.add(other)
        db.flush()
        db.add(PlatformMigrationItem(
            run_id=other.id, organization_id=org.id, provider="YARDI",
            resource="TENANTS", source_id="R-other",
            target_entity="TENANT_USER", target_id=tenant.id,
            source_fingerprint="different-row",
        ))
        db.commit()
        with pytest.raises(HTTPException) as collision:
            bind_yardi_reviewed_tenant_matches(
                run.id, YardiReviewedPropertyBindingIn(
                    review_fingerprint=dry_run["review_fingerprint"],
                ), db, actor,
            )
        assert collision.value.status_code == 409
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "TENANTS",
        ).count() == 0
        db.refresh(tenant)
        assert tenant.hashed_password == "preserved-hash"
    finally:
        db.close()
        engine.dispose()
