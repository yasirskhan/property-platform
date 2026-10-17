"""Audited SKIP of invalid Yardi source rows must unblock safe reviewed binding."""
import pytest
from fastapi import HTTPException

from app.models.platform_migration import (
    PlatformMigrationItem, PlatformMigrationRun, PlatformMigrationStagedRow,
)
from app.models.platform_user import PlatformUserRole
from app.models.property import Property
from app.routers.yardi_migrations import (
    YardiPropertyMatchIn, YardiReviewedPropertyBindingIn, YardiRowSkipIn,
    YardiVendorMatchIn, bind_yardi_reviewed_property_matches,
    bind_yardi_reviewed_vendor_matches, dry_run_yardi_review,
    match_yardi_staged_property, match_yardi_staged_vendor,
    skip_yardi_staged_row,
)
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _org, _platform_user, _session
from test_yardi_vendor_review_binding import _seed as _vendor_seed


def test_invalid_skipped_property_does_not_block_reviewed_binding():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-invalid-skipped-property-binding")
        target = Property(
            organization_id=org.id, name="Untouched Property",
            address_line1="1 Main", city="Cleveland", state="OH", zip_code="44113",
        )
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="invalid-skipped-property", status="DRAFT",
        )
        db.add_all([target, run])
        db.commit()
        upload = stage_yardi_file(
            db, run=run, filename="properties.csv",
            content=(b"ID,Name,Street,City,State,Zip\n"
                     b"P1,Reviewed,2 Main,Cleveland,OH,44113\n"
                     b"P2,Invalid,3 Main,Cleveland,OH,44113\n"),
            resource_override="PROPERTIES", sheet_name=None,
            explicit_mapping={
                "source_id": "ID", "name": "Name", "address_line1": "Street",
                "city": "City", "state": "State", "zip_code": "Zip",
            }, platform_user_id=actor.id,
        )
        db.commit()
        rows = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id,
        ).order_by(PlatformMigrationStagedRow.id).all()
        assert len(rows) == 2
        reviewed, rejected = rows
        match_yardi_staged_property(
            run.id, reviewed.id, YardiPropertyMatchIn(target_property_id=target.id),
            db, actor,
        )
        rejected.errors = ["Source row rejected during validation"]
        rejected.disposition = "INVALID"
        db.commit()
        with pytest.raises(HTTPException) as blocked:
            bind_yardi_reviewed_property_matches(
                run.id, YardiReviewedPropertyBindingIn(review_fingerprint="0" * 64),
                db, actor,
            )
        assert blocked.value.status_code == 409
        assert "Invalid Property" in blocked.value.detail

        skip = skip_yardi_staged_row(
            run.id, rejected.id, YardiRowSkipIn(reason_code="UNSUPPORTED_SOURCE"),
            db, actor,
        )
        assert skip["action"] == "SKIP" and not skip["replayed"]
        summary = dry_run_yardi_review(run.id, db, actor)
        assert summary["invalid_rows"] == 0
        assert summary["skipped_rows"] == 1
        assert summary["unresolved_rows"] == 0
        request = YardiReviewedPropertyBindingIn(
            review_fingerprint=summary["review_fingerprint"],
        )
        assert bind_yardi_reviewed_property_matches(run.id, request, db, actor)["bound"] == 1
        assert bind_yardi_reviewed_property_matches(run.id, request, db, actor)["replayed"]
        bindings = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "PROPERTIES",
        ).all()
        assert len(bindings) == 1
        assert bindings[0].source_id == "P1"
        db.refresh(target)
        db.refresh(rejected)
        assert target.name == "Untouched Property"
        assert rejected.resolution_action == "SKIP"
        assert rejected.disposition == "INVALID"
    finally:
        db.close()
        engine.dispose()


def test_invalid_skipped_vendor_does_not_block_reviewed_binding():
    db, engine = _session()
    try:
        actor, org, vendor, run, reviewed = _vendor_seed(
            db, slug="yardi-invalid-skipped-vendor-binding",
            source="invalid-skipped-vendor",
        )
        match_yardi_staged_vendor(
            run.id, reviewed.id, YardiVendorMatchIn(target_vendor_id=vendor.id),
            db, actor,
        )
        upload = stage_yardi_file(
            db, run=run, filename="invalid-vendor.csv",
            content=b"Vendor Ref,Company Name\nV-2,Rejected Vendor\n",
            resource_override="VENDORS", sheet_name=None,
            explicit_mapping={"source_id": "Vendor Ref", "name": "Company Name"},
            platform_user_id=actor.id,
        )
        db.commit()
        rejected = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id,
        ).one()
        rejected.errors = ["Source row rejected during validation"]
        rejected.disposition = "INVALID"
        db.commit()
        with pytest.raises(HTTPException) as blocked:
            bind_yardi_reviewed_vendor_matches(
                run.id, YardiReviewedPropertyBindingIn(review_fingerprint="0" * 64),
                db, actor,
            )
        assert blocked.value.status_code == 409
        assert "Invalid Vendor" in blocked.value.detail
        skip_yardi_staged_row(
            run.id, rejected.id, YardiRowSkipIn(reason_code="UNSUPPORTED_SOURCE"),
            db, actor,
        )
        summary = dry_run_yardi_review(run.id, db, actor)
        assert summary["invalid_rows"] == 0
        assert summary["skipped_rows"] == 1
        assert summary["unresolved_rows"] == 0
        result = bind_yardi_reviewed_vendor_matches(
            run.id, YardiReviewedPropertyBindingIn(
                review_fingerprint=summary["review_fingerprint"],
            ), db, actor,
        )
        assert result["bound"] == 1
        bindings = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "VENDORS",
        ).all()
        assert len(bindings) == 1 and bindings[0].source_id == reviewed.source_id
        db.refresh(vendor)
        db.refresh(rejected)
        assert vendor.company_name == "Untouched Vendor"
        assert rejected.resolution_action == "SKIP"
    finally:
        db.close()
        engine.dispose()
