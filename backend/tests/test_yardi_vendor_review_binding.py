"""Reviewed Yardi vendor identity never creates or overwrites a customer Vendor."""
import pytest
from fastapi import HTTPException
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.vendor import Vendor
from app.routers.yardi_migrations import (
    YardiVendorMatchIn, YardiReviewedPropertyBindingIn,
    bind_yardi_reviewed_vendor_matches, dry_run_yardi_review,
    match_yardi_staged_vendor, get_yardi_reconciliation,
)
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _org, _platform_user, _session


def _seed(db, *, slug="yardi-vendor-reviewed", source="vendor-review"):
    actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
    org = _org(db, slug)
    vendor = Vendor(organization_id=org.id, company_name="Untouched Vendor")
    run = PlatformMigrationRun(
        organization_id=org.id, provider="YARDI",
        source_account_ref=source, status="DRAFT",
    )
    db.add_all([vendor, run])
    db.commit()
    upload = stage_yardi_file(
        db, run=run, filename="vendors.csv",
        content=b"Vendor Ref,Company Name\nV-1,Source Vendor\n",
        resource_override="VENDORS", sheet_name=None,
        explicit_mapping={"source_id": "Vendor Ref", "name": "Company Name"},
        platform_user_id=actor.id,
    )
    db.commit()
    row = db.query(PlatformMigrationStagedRow).filter(
        PlatformMigrationStagedRow.upload_id == upload.upload.id
    ).one()
    return actor, org, vendor, run, row


def test_review_vendor_exact_binding_replay_and_no_customer_mutation():
    db, engine = _session()
    try:
        actor, org, vendor, run, row = _seed(db)
        from app.main import app
        endpoints = {route.path: route.endpoint for route in app.routes if hasattr(route, "endpoint")}
        base = "/api/platform/migrations/yardi/runs/{run_id}"
        assert endpoints[base + "/staged-rows/{row_id}/match-vendor"] is match_yardi_staged_vendor
        assert endpoints[base + "/bind-reviewed-vendors"] is bind_yardi_reviewed_vendor_matches
        assert match_yardi_staged_vendor(
            run.id, row.id, YardiVendorMatchIn(target_vendor_id=vendor.id), db, actor
        )["replayed"] is False
        reviewed = get_yardi_reconciliation(run.id, __import__("fastapi").Response(), db, actor)
        assert reviewed["resource_coverage"]["VENDORS"]["matched_existing"] == 1
        assert match_yardi_staged_vendor(
            run.id, row.id, YardiVendorMatchIn(target_vendor_id=vendor.id), db, actor
        )["replayed"] is True
        snapshot = dry_run_yardi_review(run.id, db, actor)
        binding = YardiReviewedPropertyBindingIn(review_fingerprint=snapshot["review_fingerprint"])
        assert bind_yardi_reviewed_vendor_matches(run.id, binding, db, actor)["bound"] == 1
        assert bind_yardi_reviewed_vendor_matches(run.id, binding, db, actor)["replayed"] is True
        mapped = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "VENDORS",
        ).one()
        assert mapped.source_id == "V-1"
        assert mapped.target_entity == "VENDOR" and mapped.target_id == vendor.id
        assert mapped.source_fingerprint == row.row_fingerprint
        db.refresh(vendor)
        assert vendor.company_name == "Untouched Vendor"
        assert db.query(Vendor).filter(Vendor.organization_id == org.id).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_vendor_binding_rejects_stale_review_and_cross_run_collision():
    db, engine = _session()
    try:
        actor, org, vendor, run, row = _seed(db, slug="yardi-vendor-collision")
        match_yardi_staged_vendor(
            run.id, row.id, YardiVendorMatchIn(target_vendor_id=vendor.id), db, actor,
        )
        snapshot = dry_run_yardi_review(run.id, db, actor)
        with pytest.raises(HTTPException) as stale:
            bind_yardi_reviewed_vendor_matches(
                run.id, YardiReviewedPropertyBindingIn(review_fingerprint="0" * 64),
                db, actor,
            )
        assert stale.value.status_code == 409
        other = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="other-vendors", status="DRAFT",
        )
        db.add(other)
        db.flush()
        db.add(PlatformMigrationItem(
            run_id=other.id, organization_id=org.id, provider="YARDI",
            resource="VENDORS", source_id="V-other",
            target_entity="VENDOR", target_id=vendor.id,
            source_fingerprint="different",
        ))
        db.commit()
        with pytest.raises(HTTPException) as collision:
            bind_yardi_reviewed_vendor_matches(
                run.id, YardiReviewedPropertyBindingIn(
                    review_fingerprint=snapshot["review_fingerprint"],
                ), db, actor,
            )
        assert collision.value.status_code == 409
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "VENDORS",
        ).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_vendor_review_rejects_cross_org_and_deleted_targets():
    db, engine = _session()
    try:
        actor, org, vendor, run, row = _seed(db, slug="yardi-vendor-org")
        other_org = _org(db, "yardi-other-vendor-org")
        other_vendor = Vendor(organization_id=other_org.id, company_name="Different Org")
        db.add(other_vendor)
        db.commit()
        with pytest.raises(HTTPException) as cross_org:
            match_yardi_staged_vendor(
                run.id, row.id, YardiVendorMatchIn(target_vendor_id=other_vendor.id),
                db, actor,
            )
        assert cross_org.value.status_code == 404
        match_yardi_staged_vendor(
            run.id, row.id, YardiVendorMatchIn(target_vendor_id=vendor.id),
            db, actor,
        )
        vendor.deleted_at = __import__("datetime").datetime.utcnow()
        db.commit()
        with pytest.raises(HTTPException) as deleted_replay:
            match_yardi_staged_vendor(
                run.id, row.id, YardiVendorMatchIn(target_vendor_id=vendor.id),
                db, actor,
            )
        assert deleted_replay.value.status_code == 404
    finally:
        db.close()
        engine.dispose()
