"""Yardi existing-Owner identity review and metadata-only binding regressions."""
import pytest
from fastapi import HTTPException, Response

from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.user import User, UserRole
from app.routers.yardi_migrations import (
    YardiOwnerMatchIn, YardiReviewedPropertyBindingIn,
    bind_yardi_reviewed_owner_matches, dry_run_yardi_review,
    match_yardi_staged_owner, get_yardi_reconciliation,
)
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _org, _platform_user, _session


def _seed(db, slug="yardi-owner-reviewed"):
    actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
    org = _org(db, slug)
    owner = User(
        organization_id=org.id, role=UserRole.OWNER,
        email=f"{slug}@example.test", hashed_password="preserved-hash",
        first_name="Existing", last_name="Owner",
        is_active=True,
    )
    run = PlatformMigrationRun(
        organization_id=org.id, provider="YARDI",
        source_account_ref="owner-export", status="DRAFT",
    )
    db.add_all([owner, run])
    db.commit()
    upload = stage_yardi_file(
        db, run=run, filename="owners.csv",
        content=b"Owner Ref,Full Name\nO-1,Source Owner\n",
        resource_override="OWNERS", sheet_name=None,
        explicit_mapping={"source_id": "Owner Ref", "name": "Full Name"},
        platform_user_id=actor.id,
    )
    db.commit()
    row = db.query(PlatformMigrationStagedRow).filter(
        PlatformMigrationStagedRow.upload_id == upload.upload.id
    ).one()
    return actor, org, owner, run, row


def test_owner_review_binding_fingerprint_replay_and_nonmutation():
    db, engine = _session()
    try:
        actor, org, owner, run, row = _seed(db)
        from app.main import app
        endpoints = {route.path: route.endpoint for route in app.routes if hasattr(route, "endpoint")}
        base = "/api/platform/migrations/yardi/runs/{run_id}"
        assert endpoints[base + "/staged-rows/{row_id}/match-owner"] is match_yardi_staged_owner
        assert endpoints[base + "/bind-reviewed-owners"] is bind_yardi_reviewed_owner_matches
        assert match_yardi_staged_owner(
            run.id, row.id, YardiOwnerMatchIn(target_owner_user_id=owner.id),
            db, actor,
        )["replayed"] is False
        report = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert report["resource_coverage"]["OWNERS"]["matched_existing"] == 1
        assert match_yardi_staged_owner(
            run.id, row.id, YardiOwnerMatchIn(target_owner_user_id=owner.id),
            db, actor,
        )["replayed"] is True
        dry_run = dry_run_yardi_review(run.id, db, actor)
        request = YardiReviewedPropertyBindingIn(
            review_fingerprint=dry_run["review_fingerprint"],
        )
        assert bind_yardi_reviewed_owner_matches(run.id, request, db, actor)["bound"] == 1
        assert bind_yardi_reviewed_owner_matches(run.id, request, db, actor)["replayed"] is True
        mapped = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "OWNERS",
        ).one()
        assert mapped.target_entity == "OWNER_USER"
        assert mapped.target_id == owner.id and mapped.source_id == "O-1"
        assert mapped.source_fingerprint == row.row_fingerprint
        db.refresh(owner)
        assert owner.hashed_password == "preserved-hash"
        assert owner.first_name == "Existing"
        assert db.query(User).filter(User.organization_id == org.id).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_owner_binding_rejects_stale_fingerprint_and_competing_source_target():
    db, engine = _session()
    try:
        actor, org, owner, run, row = _seed(db, "yardi-owner-collision")
        match_yardi_staged_owner(
            run.id, row.id, YardiOwnerMatchIn(target_owner_user_id=owner.id),
            db, actor,
        )
        dry_run = dry_run_yardi_review(run.id, db, actor)
        with pytest.raises(HTTPException) as stale:
            bind_yardi_reviewed_owner_matches(
                run.id, YardiReviewedPropertyBindingIn(review_fingerprint="0" * 64),
                db, actor,
            )
        assert stale.value.status_code == 409
        other = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="other-owner-export", status="DRAFT",
        )
        db.add(other)
        db.flush()
        db.add(PlatformMigrationItem(
            run_id=other.id, organization_id=org.id, provider="YARDI",
            resource="OWNERS", source_id="O-other",
            target_entity="OWNER_USER", target_id=owner.id,
            source_fingerprint="different-row",
        ))
        db.commit()
        with pytest.raises(HTTPException) as collision:
            bind_yardi_reviewed_owner_matches(
                run.id, YardiReviewedPropertyBindingIn(
                    review_fingerprint=dry_run["review_fingerprint"],
                ), db, actor,
            )
        assert collision.value.status_code == 409
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "OWNERS",
        ).count() == 0
        db.refresh(owner)
        assert owner.hashed_password == "preserved-hash"
    finally:
        db.close()
        engine.dispose()


def test_owner_review_rejects_wrong_role_org_and_inactive_replay():
    db, engine = _session()
    try:
        actor, org, owner, run, row = _seed(db, "yardi-owner-role")
        tenant = User(
            organization_id=org.id, role=UserRole.TENANT,
            email="other-tenant-for-owner@example.test", hashed_password="tenant-hash",
            first_name="Other", last_name="Tenant", is_active=True,
        )
        outside_org = _org(db, "yardi-owner-outside")
        outsider = User(
            organization_id=outside_org.id, role=UserRole.OWNER,
            email="outsider-owner@example.test", hashed_password="outside-hash",
            first_name="Other", last_name="Owner", is_active=True,
        )
        db.add_all([tenant, outsider])
        db.commit()
        for wrong_id in (tenant.id, outsider.id):
            with pytest.raises(HTTPException) as wrong:
                match_yardi_staged_owner(
                    run.id, row.id, YardiOwnerMatchIn(target_owner_user_id=wrong_id),
                    db, actor,
                )
            assert wrong.value.status_code == 404
        match_yardi_staged_owner(
            run.id, row.id, YardiOwnerMatchIn(target_owner_user_id=owner.id),
            db, actor,
        )
        owner.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as inactive:
            match_yardi_staged_owner(
                run.id, row.id, YardiOwnerMatchIn(target_owner_user_id=owner.id),
                db, actor,
            )
        assert inactive.value.status_code == 404
    finally:
        db.close()
        engine.dispose()
