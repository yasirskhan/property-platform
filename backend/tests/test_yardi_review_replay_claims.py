"""A replayed Yardi identity review cannot ignore a later staff target claim.

The conflicting row is seeded as retained historical review evidence. A new
review would be rejected, but historical/conflicting reviews must remain
detectable without editing existing customer identities.
"""
import pytest
from fastapi import HTTPException, Response

from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationStagedRow
from app.routers.yardi_migrations import (
    YardiOwnerMatchIn, YardiTenantMatchIn, YardiVendorMatchIn,
    YardiReviewedPropertyBindingIn, bind_yardi_reviewed_owner_matches,
    bind_yardi_reviewed_tenant_matches, bind_yardi_reviewed_vendor_matches,
    dry_run_yardi_review, get_yardi_reconciliation,
    match_yardi_staged_owner, match_yardi_staged_tenant, match_yardi_staged_vendor,
)
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _session
from test_yardi_owner_review_binding import _seed as seed_owner
from test_yardi_tenant_review_binding import _seed as seed_tenant
from test_yardi_vendor_review_binding import _seed as seed_vendor


@pytest.mark.parametrize("resource,seed,match,payload_type,field,content,mapping", [
    (
        "OWNERS", seed_owner, match_yardi_staged_owner, YardiOwnerMatchIn,
        "resolution_target_owner_user_id",
        b"Owner Ref,Full Name\nO-OTHER,Other Owner\n",
        {"source_id": "Owner Ref", "name": "Full Name"},
    ),
    (
        "TENANTS", seed_tenant, match_yardi_staged_tenant, YardiTenantMatchIn,
        "resolution_target_tenant_user_id",
        b"Resident Ref,Full Name\nR-OTHER,Other Resident\n",
        {"source_id": "Resident Ref", "name": "Full Name"},
    ),
    (
        "VENDORS", seed_vendor, match_yardi_staged_vendor, YardiVendorMatchIn,
        "resolution_target_vendor_id",
        b"Vendor Ref,Company Name\nV-OTHER,Other Vendor\n",
        {"source_id": "Vendor Ref", "name": "Company Name"},
    ),
])
def test_review_replay_revalidates_other_staff_claims(
    resource, seed, match, payload_type, field, content, mapping,
):
    db, engine = _session()
    try:
        actor, org, target, run, row = seed(
            db, slug=f"yardi-stale-replay-{resource.lower()}"
        )
        request = payload_type(**{field.removeprefix("resolution_"): target.id})
        assert match(run.id, row.id, request, db, actor)["replayed"] is False
        assert match(run.id, row.id, request, db, actor)["replayed"] is True
        initial_coverage = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert initial_coverage["resource_coverage"][resource]["matched_existing"] == 1

        other_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref=f"other-{resource.lower()}", status="DRAFT",
        )
        db.add(other_run)
        db.commit()
        upload = stage_yardi_file(
            db, run=other_run, filename=f"{resource.lower()}.csv",
            content=content, resource_override=resource,
            sheet_name=None, explicit_mapping=mapping, platform_user_id=actor.id,
        )
        db.commit()
        competing = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id
        ).one()
        competing.resolution_action = "MATCH_EXISTING"
        setattr(competing, field, target.id)
        db.commit()

        with pytest.raises(HTTPException) as conflict:
            match(run.id, row.id, request, db, actor)
        assert conflict.value.status_code == 409
        conflicted_coverage = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert conflicted_coverage["resource_coverage"][resource]["matched_existing"] == 0
        assert conflicted_coverage["resource_coverage"][resource]["needs_review"] == 1
        assert conflicted_coverage["review_fingerprint"] != initial_coverage["review_fingerprint"]
        db.refresh(row)
        db.refresh(target)
        assert row.resolution_action == "MATCH_EXISTING"
        if resource == "VENDORS":
            assert target.company_name == "Untouched Vendor"
        else:
            assert target.hashed_password == "preserved-hash"

        competing.resolution_action = None
        setattr(competing, field, None)
        db.commit()
        assert match(run.id, row.id, request, db, actor)["replayed"] is True
        restored_coverage = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert restored_coverage["resource_coverage"][resource]["matched_existing"] == 1

        # A review in another run of the same stable source ID is not a
        # different source target claim.
        competing.source_id = row.source_id
        competing.resolution_action = "MATCH_EXISTING"
        setattr(competing, field, target.id)
        db.commit()
        same_source = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert same_source["resource_coverage"][resource]["matched_existing"] == 1
        assert same_source["review_fingerprint"] == restored_coverage["review_fingerprint"]
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize("resource,seed,match,payload_type,field,entity", [
    ("OWNERS", seed_owner, match_yardi_staged_owner, YardiOwnerMatchIn,
     "resolution_target_owner_user_id", "OWNER_USER"),
    ("TENANTS", seed_tenant, match_yardi_staged_tenant, YardiTenantMatchIn,
     "resolution_target_tenant_user_id", "TENANT_USER"),
    ("VENDORS", seed_vendor, match_yardi_staged_vendor, YardiVendorMatchIn,
     "resolution_target_vendor_id", "VENDOR"),
])
def test_review_replay_rejects_changed_durable_source_fingerprint(
    resource, seed, match, payload_type, field, entity,
):
    from app.models.platform_migration import PlatformMigrationItem

    db, engine = _session()
    try:
        actor, org, target, run, row = seed(
            db, slug=f"yardi-replay-fingerprint-{resource.lower()}"
        )
        request = payload_type(**{field.removeprefix("resolution_"): target.id})
        assert match(run.id, row.id, request, db, actor)["replayed"] is False
        assert match(run.id, row.id, request, db, actor)["replayed"] is True

        # This mapping represents stale retained data created after the review.
        mapping = PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="YARDI",
            resource=resource, source_id=row.source_id, target_entity=entity,
            target_id=target.id, source_fingerprint="stale-row-evidence",
        )
        db.add(mapping)
        db.commit()
        with pytest.raises(HTTPException) as stale:
            match(run.id, row.id, request, db, actor)
        assert stale.value.status_code == 409
        db.refresh(row)
        db.refresh(target)
        assert row.resolution_action == "MATCH_EXISTING"
        if resource == "VENDORS":
            assert target.company_name == "Untouched Vendor"
        else:
            assert target.hashed_password == "preserved-hash"

        mapping.source_fingerprint = row.row_fingerprint
        db.commit()
        assert match(run.id, row.id, request, db, actor)["replayed"] is True
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize("resource,seed,match,binder,payload_type,field,content,mapping", [
    (
        "OWNERS", seed_owner, match_yardi_staged_owner,
        bind_yardi_reviewed_owner_matches, YardiOwnerMatchIn,
        "resolution_target_owner_user_id",
        b"Owner Ref,Full Name\nO-OTHER,Other Owner\n",
        {"source_id": "Owner Ref", "name": "Full Name"},
    ),
    (
        "TENANTS", seed_tenant, match_yardi_staged_tenant,
        bind_yardi_reviewed_tenant_matches, YardiTenantMatchIn,
        "resolution_target_tenant_user_id",
        b"Resident Ref,Full Name\nR-OTHER,Other Resident\n",
        {"source_id": "Resident Ref", "name": "Full Name"},
    ),
    (
        "VENDORS", seed_vendor, match_yardi_staged_vendor,
        bind_yardi_reviewed_vendor_matches, YardiVendorMatchIn,
        "resolution_target_vendor_id",
        b"Vendor Ref,Company Name\nV-OTHER,Other Vendor\n",
        {"source_id": "Vendor Ref", "name": "Company Name"},
    ),
])
def test_reviewed_binding_rejects_later_staff_target_claim_on_first_bind_and_replay(
    resource, seed, match, binder, payload_type, field, content, mapping,
):
    db, engine = _session()
    try:
        actor, org, target, run, row = seed(
            db, slug=f"yardi-binding-staff-claim-{resource.lower()}"
        )
        request = payload_type(**{field.removeprefix("resolution_"): target.id})
        assert match(run.id, row.id, request, db, actor)["replayed"] is False
        snapshot = dry_run_yardi_review(run.id, db, actor)
        binding = YardiReviewedPropertyBindingIn(
            review_fingerprint=snapshot["review_fingerprint"]
        )

        other_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref=f"other-binding-{resource.lower()}", status="DRAFT",
        )
        db.add(other_run)
        db.commit()
        upload = stage_yardi_file(
            db, run=other_run, filename=f"{resource.lower()}-other.csv",
            content=content, resource_override=resource, sheet_name=None,
            explicit_mapping=mapping, platform_user_id=actor.id,
        )
        db.commit()
        competing = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id
        ).one()
        competing.resolution_action = "MATCH_EXISTING"
        setattr(competing, field, target.id)
        db.commit()

        with pytest.raises(HTTPException) as first:
            binder(run.id, binding, db, actor)
        assert first.value.status_code == 409
        competing.resolution_action = None
        setattr(competing, field, None)
        db.commit()
        assert binder(run.id, binding, db, actor)["bound"] == 1

        competing.resolution_action = "MATCH_EXISTING"
        setattr(competing, field, target.id)
        db.commit()
        with pytest.raises(HTTPException) as replay:
            binder(run.id, binding, db, actor)
        assert replay.value.status_code == 409
        competing.resolution_action = None
        setattr(competing, field, None)
        db.commit()
        assert binder(run.id, binding, db, actor)["replayed"] is True

        # Historical reviewed claims with a missing provider identity cannot
        # silently bypass the current target guard via SQL NULL inequality.
        competing.source_id = None
        competing.resolution_action = "MATCH_EXISTING"
        setattr(competing, field, target.id)
        db.commit()
        with pytest.raises(HTTPException) as unknown:
            binder(run.id, binding, db, actor)
        assert unknown.value.status_code == 409
        competing.resolution_action = None
        setattr(competing, field, None)
        db.commit()
        assert binder(run.id, binding, db, actor)["replayed"] is True
        db.refresh(target)
        if resource == "VENDORS":
            assert target.company_name == "Untouched Vendor"
        else:
            assert target.hashed_password == "preserved-hash"
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize("resource,seed,target_field,entity,content,mapping", [
    (
        "OWNERS", seed_owner, "resolution_target_owner_user_id", "OWNER_USER",
        b"Owner Ref,Full Name\nO-OTHER,Other Owner\n",
        {"source_id": "Owner Ref", "name": "Full Name"},
    ),
    (
        "TENANTS", seed_tenant, "resolution_target_tenant_user_id", "TENANT_USER",
        b"Resident Ref,Full Name\nR-OTHER,Other Resident\n",
        {"source_id": "Resident Ref", "name": "Full Name"},
    ),
    (
        "VENDORS", seed_vendor, "resolution_target_vendor_id", "VENDOR",
        b"Vendor Ref,Company Name\nV-OTHER,Other Vendor\n",
        {"source_id": "Vendor Ref", "name": "Company Name"},
    ),
])
def test_unreviewed_durable_identity_coverage_rejects_competing_staff_target_claim(
    resource, seed, target_field, entity, content, mapping,
):
    from app.models.platform_migration import PlatformMigrationItem

    db, engine = _session()
    try:
        actor, org, target, run, row = seed(
            db, slug=f"yardi-mapped-target-claim-{resource.lower()}"
        )
        db.add(PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="YARDI",
            resource=resource, source_id=row.source_id,
            target_entity=entity, target_id=target.id,
            source_fingerprint=row.row_fingerprint,
        ))
        db.commit()
        before = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert before["resource_coverage"][resource]["mapped"] == 1

        other_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref=f"other-mapped-{resource.lower()}", status="DRAFT",
        )
        db.add(other_run)
        db.commit()
        upload = stage_yardi_file(
            db, run=other_run, filename=f"{resource.lower()}-other.csv",
            content=content, resource_override=resource, sheet_name=None,
            explicit_mapping=mapping, platform_user_id=actor.id,
        )
        db.commit()
        competing = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id
        ).one()
        competing.resolution_action = "MATCH_EXISTING"
        setattr(competing, target_field, target.id)
        db.commit()
        after = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert after["resource_coverage"][resource]["mapped"] == 0
        assert after["resource_coverage"][resource]["needs_review"] == 1
        assert after["review_fingerprint"] != before["review_fingerprint"]

        competing.resolution_action = None
        setattr(competing, target_field, None)
        db.commit()
        recovered = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert recovered["resource_coverage"][resource]["mapped"] == 1

        competing.source_id = row.source_id
        competing.resolution_action = "MATCH_EXISTING"
        setattr(competing, target_field, target.id)
        db.commit()
        same_source = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert same_source["resource_coverage"][resource]["mapped"] == 1
        assert same_source["review_fingerprint"] == recovered["review_fingerprint"]

        # Historical/corrupted staff evidence with a missing source identity
        # still contests this customer target. SQL NULL != source_id would
        # otherwise silently hide it from readiness.
        competing.source_id = None
        db.commit()
        unknown_source = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert unknown_source["resource_coverage"][resource]["mapped"] == 0
        assert unknown_source["resource_coverage"][resource]["needs_review"] == 1
        assert unknown_source["review_fingerprint"] != recovered["review_fingerprint"]
        db.refresh(target)
        assert (target.company_name == "Untouched Vendor" if resource == "VENDORS"
                else target.hashed_password == "preserved-hash")
    finally:
        db.close()
        engine.dispose()


def test_reconciliation_fingerprint_changes_when_competing_target_swaps_but_totals_do_not():
    """A conflict moving between two mapped rows cannot reuse dry-run evidence."""
    from app.models.platform_migration import PlatformMigrationItem
    from app.models.vendor import Vendor

    db, engine = _session()
    try:
        actor, org, first_vendor, run, first_row = seed_vendor(
            db, slug="yardi-swapped-target-fingerprint"
        )
        second_vendor = Vendor(
            organization_id=org.id, company_name="Second Preserved Vendor",
        )
        db.add(second_vendor)
        db.commit()
        second_upload = stage_yardi_file(
            db, run=run, filename="second-vendor.csv",
            content=b"Vendor Ref,Company Name\nV-SECOND,Second Vendor\n",
            resource_override="VENDORS", sheet_name=None,
            explicit_mapping={"source_id": "Vendor Ref", "name": "Company Name"},
            platform_user_id=actor.id,
        )
        db.commit()
        second_row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == second_upload.upload.id
        ).one()
        for row, vendor in ((first_row, first_vendor), (second_row, second_vendor)):
            db.add(PlatformMigrationItem(
                run_id=run.id, organization_id=org.id, provider="YARDI",
                resource="VENDORS", source_id=row.source_id, target_entity="VENDOR",
                target_id=vendor.id, source_fingerprint=row.row_fingerprint,
            ))
        db.commit()
        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["resource_coverage"]["VENDORS"]["mapped"] == 2

        other_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="competing-vendor-switch", status="DRAFT",
        )
        db.add(other_run)
        db.commit()
        competing_upload = stage_yardi_file(
            db, run=other_run, filename="competitor.csv",
            content=b"Vendor Ref,Company Name\nV-THIRD,Third Vendor\n",
            resource_override="VENDORS", sheet_name=None,
            explicit_mapping={"source_id": "Vendor Ref", "name": "Company Name"},
            platform_user_id=actor.id,
        )
        db.commit()
        competing = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == competing_upload.upload.id
        ).one()
        competing.resolution_action = "MATCH_EXISTING"
        competing.resolution_target_vendor_id = first_vendor.id
        db.commit()
        first_collision = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert first_collision["resource_coverage"]["VENDORS"]["mapped"] == 1
        assert first_collision["resource_coverage"]["VENDORS"]["needs_review"] == 1

        # The same Vendor target stays contested after historical source ID
        # changes. Identical counters may not reuse the same fingerprint.
        competing.source_id = "V-FOURTH"
        db.commit()
        changed_source = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert changed_source["resource_coverage"] == first_collision["resource_coverage"]
        assert changed_source["review_fingerprint"] != first_collision["review_fingerprint"]
        competing.source_id = "V-THIRD"
        db.commit()
        original_source = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert original_source["review_fingerprint"] == first_collision["review_fingerprint"]

        # Same reviewed staff action and aggregate totals, different contested
        # customer target and different source row no longer considered ready.
        competing.resolution_target_vendor_id = second_vendor.id
        db.commit()
        swapped = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert swapped["resource_coverage"] == first_collision["resource_coverage"]
        assert swapped["review_fingerprint"] != first_collision["review_fingerprint"]
        db.refresh(first_vendor)
        db.refresh(second_vendor)
        assert first_vendor.company_name == "Untouched Vendor"
        assert second_vendor.company_name == "Second Preserved Vendor"
    finally:
        db.close()
        engine.dispose()
