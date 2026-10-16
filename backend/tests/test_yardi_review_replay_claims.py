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

        # A different competing provider ID against the same retained
        # customer target stays stale, but must invalidate the exact
        # reviewed-source fingerprint for Owners, Tenants and Vendors.
        original_competing_source = competing.source_id
        competing.source_id = "SECOND-" + resource
        db.commit()
        changed_source = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert changed_source["resource_coverage"] == conflicted_coverage["resource_coverage"]
        assert changed_source["review_fingerprint"] != conflicted_coverage["review_fingerprint"]
        competing.source_id = original_competing_source
        db.commit()
        exact_recovery = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert exact_recovery["review_fingerprint"] == conflicted_coverage["review_fingerprint"]

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


def test_unbound_reviewed_vendor_fingerprint_tracks_competing_durable_source():
    """A staff-reviewed row without a current mapping also has exact claim evidence."""
    from app.models.platform_migration import PlatformMigrationItem

    db, engine = _session()
    try:
        actor, org, vendor, run, row = seed_vendor(
            db, slug="yardi-unbound-reviewed-vendor-source-provenance",
        )
        payload = YardiVendorMatchIn(target_vendor_id=vendor.id)
        assert match_yardi_staged_vendor(run.id, row.id, payload, db, actor)["replayed"] is False
        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["resource_coverage"]["VENDORS"]["matched_existing"] == 1
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
        ).count() == 0

        historical_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="old-vendor-durable-review", status="DRAFT",
        )
        db.add(historical_run)
        db.flush()
        historical = PlatformMigrationItem(
            run_id=historical_run.id, organization_id=org.id, provider="YARDI",
            resource="VENDORS", source_id="OLD-V-1",
            target_entity="VENDOR", target_id=vendor.id,
            source_fingerprint="historical-durable-vendor-source",
        )
        db.add(historical)
        db.commit()
        first = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert first["resource_coverage"]["VENDORS"]["matched_existing"] == 0
        assert first["resource_coverage"]["VENDORS"]["needs_review"] == 1
        assert first["review_fingerprint"] != baseline["review_fingerprint"]

        # A reviewed but not yet bound source must also invalidate an exact
        # staff dry-run snapshot when the competing historical source changes.
        retained_snapshot = dry_run_yardi_review(run.id, db, actor)
        assert retained_snapshot["review_fingerprint"] == first["review_fingerprint"]

        historical.source_id = "OLD-V-2"
        db.commit()
        second = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert second["resource_coverage"] == first["resource_coverage"]
        assert second["review_fingerprint"] != first["review_fingerprint"]
        # An unchanged aggregate count must not permit replay of a stored
        # dry-run made under a different durable source-claim identity.
        from app.routers.yardi_migrations import get_yardi_review_dry_run_status
        expired = get_yardi_review_dry_run_status(run.id, Response(), db, actor)
        assert expired["saved_review_fingerprint"] == retained_snapshot["review_fingerprint"]
        assert expired["current_review_fingerprint"] == second["review_fingerprint"]
        assert expired["is_current"] is False

        historical.source_id = "OLD-V-1"
        db.commit()
        assert get_yardi_reconciliation(
            run.id, Response(), db, actor,
        )["review_fingerprint"] == first["review_fingerprint"]
        recovered_status = get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )
        assert recovered_status["is_current"] is True
        historical.source_id = row.source_id
        db.commit()
        restored = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert restored["resource_coverage"]["VENDORS"]["matched_existing"] == 1
        assert restored["review_fingerprint"] == baseline["review_fingerprint"]
        db.refresh(vendor)
        assert vendor.company_name == "Untouched Vendor"
        assert restored["customer_business_mutation"] is False
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize("resource,seed,match,request_cls,target_field,entity", [
    ("OWNERS", seed_owner, match_yardi_staged_owner, YardiOwnerMatchIn,
     "target_owner_user_id", "OWNER_USER"),
    ("TENANTS", seed_tenant, match_yardi_staged_tenant, YardiTenantMatchIn,
     "target_tenant_user_id", "TENANT_USER"),
])
def test_unbound_reviewed_user_durable_source_swap_invalidates_dry_run(
    resource, seed, match, request_cls, target_field, entity,
):
    """Exact historical claim provenance must protect an unbound reviewed user."""
    from app.models.platform_migration import PlatformMigrationItem
    from app.routers.yardi_migrations import get_yardi_review_dry_run_status

    db, engine = _session()
    try:
        actor, org, user, run, row = seed(
            db, slug=f"yardi-unbound-user-durable-source-{resource.lower()}"
        )
        payload = request_cls(**{target_field: user.id})
        assert match(run.id, row.id, payload, db, actor)["replayed"] is False
        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["resource_coverage"][resource]["matched_existing"] == 1
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id
        ).count() == 0

        old = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref=f"historic-unbound-{resource.lower()}",
            status="DRAFT",
        )
        db.add(old)
        db.flush()
        historical = PlatformMigrationItem(
            run_id=old.id, organization_id=org.id, provider="YARDI",
            resource=resource, source_id="OLD-IDENTITY-1",
            target_entity=entity, target_id=user.id,
            source_fingerprint="historic-identity-evidence",
        )
        db.add(historical)
        db.commit()
        first = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert first["resource_coverage"][resource]["needs_review"] == 1
        assert first["resource_coverage"][resource]["matched_existing"] == 0
        assert first["review_fingerprint"] != baseline["review_fingerprint"]

        retained = dry_run_yardi_review(run.id, db, actor)
        assert retained["review_fingerprint"] == first["review_fingerprint"]
        assert get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )["is_current"] is True

        historical.source_id = "OLD-IDENTITY-2"
        db.commit()
        changed = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert changed["resource_coverage"] == first["resource_coverage"]
        assert changed["review_fingerprint"] != first["review_fingerprint"]
        status = get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )
        assert status["saved_review_fingerprint"] == retained["review_fingerprint"]
        assert status["current_review_fingerprint"] == changed["review_fingerprint"]
        assert status["is_current"] is False

        historical.source_id = "OLD-IDENTITY-1"
        db.commit()
        assert get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )["is_current"] is True
        historical.source_id = row.source_id
        db.commit()
        recovered = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert recovered["resource_coverage"][resource]["matched_existing"] == 1
        assert recovered["review_fingerprint"] == baseline["review_fingerprint"]
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id
        ).count() == 0
        db.refresh(user)
        assert user.hashed_password == "preserved-hash"
        assert user.first_name == "Existing"
        assert row.resolution_action == "MATCH_EXISTING"
        assert recovered["customer_business_mutation"] is False
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize("resource,seed,match,request_cls,target_field,entity", [
    ("OWNERS", seed_owner, match_yardi_staged_owner, YardiOwnerMatchIn,
     "target_owner_user_id", "OWNER_USER"),
    ("TENANTS", seed_tenant, match_yardi_staged_tenant, YardiTenantMatchIn,
     "target_tenant_user_id", "TENANT_USER"),
])
def test_unbound_reviewed_user_durable_claim_scoping_and_same_source_recovery(
    resource, seed, match, request_cls, target_field, entity,
):
    """No cross-provider/org drift; same stable source is a valid replay."""
    from app.models.platform_migration import PlatformMigrationItem
    from app.routers.yardi_migrations import get_yardi_review_dry_run_status
    from test_yardi_migrations import _org

    db, engine = _session()
    try:
        actor, org, user, run, row = seed(
            db, slug=f"yardi-unbound-user-claim-scope-{resource.lower()}"
        )
        payload = request_cls(**{target_field: user.id})
        assert match(run.id, row.id, payload, db, actor)["replayed"] is False
        initial = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert initial["resource_coverage"][resource]["matched_existing"] == 1
        snapshot = dry_run_yardi_review(run.id, db, actor)

        foreign_org = _org(db, f"yardi-unbound-foreign-{resource.lower()}")
        appfolio_run = PlatformMigrationRun(
            organization_id=org.id, provider="APPFOLIO",
            source_account_ref=f"foreign-provider-{resource.lower()}", status="DRAFT",
        )
        outside_run = PlatformMigrationRun(
            organization_id=foreign_org.id, provider="YARDI",
            source_account_ref=f"foreign-org-{resource.lower()}", status="DRAFT",
        )
        same_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref=f"same-source-{resource.lower()}", status="DRAFT",
        )
        db.add_all([appfolio_run, outside_run, same_run])
        db.flush()
        for prior_run, prior_provider, prior_org, source_id in (
            (appfolio_run, "APPFOLIO", org.id, "OTHER-PROVIDER"),
            (outside_run, "YARDI", foreign_org.id, "OTHER-ORGANIZATION"),
            (same_run, "YARDI", org.id, row.source_id),
        ):
            db.add(PlatformMigrationItem(
                run_id=prior_run.id, organization_id=prior_org,
                provider=prior_provider, resource=resource, source_id=source_id,
                target_entity=entity, target_id=user.id,
                source_fingerprint=f"historical-{prior_run.id}",
            ))
        db.commit()
        unaffected = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert unaffected["resource_coverage"] == initial["resource_coverage"]
        assert unaffected["review_fingerprint"] == initial["review_fingerprint"]
        assert get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )["is_current"] is True

        history = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == same_run.id,
        ).one()
        history.source_id = "DIFFERENT-SAME-ORGANIZATION"
        db.commit()
        contested = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert contested["resource_coverage"][resource]["needs_review"] == 1
        assert contested["review_fingerprint"] != initial["review_fingerprint"]
        assert get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )["is_current"] is False
        history.source_id = row.source_id
        db.commit()
        assert get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )["is_current"] is True
        db.refresh(user)
        assert user.hashed_password == "preserved-hash"
        assert user.first_name == "Existing"
        assert row.resolution_action == "MATCH_EXISTING"
        assert snapshot["review_fingerprint"] == initial["review_fingerprint"]
    finally:
        db.close()
        engine.dispose()


def test_unbound_reviewed_property_durable_source_swap_expires_staff_dry_run():
    """Property review without current mapping must fingerprint exact old claims."""
    from app.models.platform_migration import PlatformMigrationItem
    from app.models.platform_user import PlatformUserRole
    from app.models.property import Property
    from app.routers.yardi_migrations import (
        YardiPropertyMatchIn, get_yardi_review_dry_run_status,
        match_yardi_staged_property,
    )
    from test_yardi_migrations import _org, _platform_user

    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-unbound-reviewed-property-source-swap")
        target = Property(
            organization_id=org.id, name="Preserved Property",
            address_line1="1 Main", city="Cleveland", state="OH", zip_code="44113",
        )
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="current-reviewed-property", status="DRAFT",
        )
        old_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="historical-property-identity", status="DRAFT",
        )
        db.add_all([target, run, old_run])
        db.commit()
        upload = stage_yardi_file(
            db, run=run, filename="reviewed-property.csv",
            content=b"ID,Name,Street,City,State,Zip\nP-1,Source Property,2 Main,Cleveland,OH,44113\n",
            resource_override="PROPERTIES", sheet_name=None,
            explicit_mapping={
                "source_id": "ID", "name": "Name",
                "address_line1": "Street", "city": "City",
                "state": "State", "zip_code": "Zip",
            }, platform_user_id=actor.id,
        )
        db.commit()
        row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id,
        ).one()
        assert match_yardi_staged_property(
            run.id, row.id, YardiPropertyMatchIn(target_property_id=target.id),
            db, actor,
        )["replayed"] is False
        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["resource_coverage"]["PROPERTIES"]["matched_existing"] == 1
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
        ).count() == 0

        historical = PlatformMigrationItem(
            run_id=old_run.id, organization_id=org.id, provider="YARDI",
            resource="PROPERTIES", source_id="OLDER-PROPERTY-1",
            target_entity="PROPERTY", target_id=target.id,
            source_fingerprint="old-reviewed-property-source",
        )
        db.add(historical)
        db.commit()
        first = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert first["resource_coverage"]["PROPERTIES"]["needs_review"] == 1
        snapshot = dry_run_yardi_review(run.id, db, actor)
        assert snapshot["review_fingerprint"] == first["review_fingerprint"]

        historical.source_id = "OLDER-PROPERTY-2"
        db.commit()
        changed = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert changed["resource_coverage"] == first["resource_coverage"]
        assert changed["review_fingerprint"] != first["review_fingerprint"]
        stale = get_yardi_review_dry_run_status(run.id, Response(), db, actor)
        assert stale["is_current"] is False
        assert stale["saved_review_fingerprint"] == snapshot["review_fingerprint"]

        historical.source_id = "OLDER-PROPERTY-1"
        db.commit()
        assert get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )["is_current"] is True
        historical.source_id = row.source_id
        db.commit()
        ready = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert ready["resource_coverage"]["PROPERTIES"]["matched_existing"] == 1
        assert ready["review_fingerprint"] == baseline["review_fingerprint"]
        db.refresh(target)
        assert target.name == "Preserved Property"
        assert target.address_line1 == "1 Main"
        assert row.resolution_action == "MATCH_EXISTING"
        assert ready["customer_business_mutation"] is False
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize("resource,seed,match,request_cls,target_field", [
    ("OWNERS", seed_owner, match_yardi_staged_owner, YardiOwnerMatchIn,
     "target_owner_user_id"),
    ("TENANTS", seed_tenant, match_yardi_staged_tenant, YardiTenantMatchIn,
     "target_tenant_user_id"),
])
def test_unbound_reviewed_user_role_and_activity_revocation_expires_dry_run(
    resource, seed, match, request_cls, target_field,
):
    """An unchanged source review does not make a deactivated user current."""
    from datetime import datetime
    from app.models.platform_migration import PlatformMigrationItem
    from app.models.user import UserRole
    from app.routers.yardi_migrations import get_yardi_review_dry_run_status

    db, engine = _session()
    try:
        actor, org, user, run, row = seed(
            db, slug=f"yardi-unbound-reviewed-user-revocation-{resource.lower()}"
        )
        assert match(
            run.id, row.id, request_cls(**{target_field: user.id}), db, actor,
        )["replayed"] is False
        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["resource_coverage"][resource]["matched_existing"] == 1
        initial = dry_run_yardi_review(run.id, db, actor)
        assert initial["review_fingerprint"] == baseline["review_fingerprint"]

        old_role = user.role
        wrong_role = UserRole.TENANT if resource == "OWNERS" else UserRole.OWNER
        changes = (
            ("inactive", "is_active", False),
            ("wrong_role", "role", wrong_role),
            ("soft_deleted", "deleted_at", datetime.utcnow()),
        )
        for label, attribute, value in changes:
            setattr(user, attribute, value)
            db.commit()
            stale = get_yardi_reconciliation(run.id, Response(), db, actor)
            assert stale["resource_coverage"][resource]["matched_existing"] == 0, label
            assert stale["resource_coverage"][resource]["needs_review"] == 1, label
            assert stale["review_fingerprint"] != baseline["review_fingerprint"], label
            saved = get_yardi_review_dry_run_status(
                run.id, Response(), db, actor,
            )
            assert saved["is_current"] is False, label
            assert saved["saved_review_fingerprint"] == initial["review_fingerprint"]

            setattr(
                user, attribute,
                {"is_active": True, "role": old_role, "deleted_at": None}[attribute],
            )
            db.commit()
            recovered = get_yardi_reconciliation(run.id, Response(), db, actor)
            assert recovered["review_fingerprint"] == baseline["review_fingerprint"]
            assert recovered["resource_coverage"][resource]["matched_existing"] == 1
            assert get_yardi_review_dry_run_status(
                run.id, Response(), db, actor,
            )["is_current"] is True

        db.refresh(user)
        assert user.hashed_password == "preserved-hash"
        assert user.role == old_role and user.is_active is True
        assert user.deleted_at is None
        assert row.resolution_action == "MATCH_EXISTING"
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
        ).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_unbound_reviewed_vendor_soft_delete_expires_and_restores_dry_run():
    """Vendor archival cannot reuse a current source review or dry-run snapshot."""
    from datetime import datetime
    from app.models.platform_migration import PlatformMigrationItem
    from app.routers.yardi_migrations import get_yardi_review_dry_run_status

    db, engine = _session()
    try:
        actor, org, vendor, run, row = seed_vendor(
            db, slug="yardi-unbound-reviewed-vendor-soft-delete",
        )
        assert match_yardi_staged_vendor(
            run.id, row.id, YardiVendorMatchIn(target_vendor_id=vendor.id),
            db, actor,
        )["replayed"] is False
        original = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert original["resource_coverage"]["VENDORS"]["matched_existing"] == 1
        saved = dry_run_yardi_review(run.id, db, actor)

        vendor.deleted_at = datetime.utcnow()
        db.commit()
        stale = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert stale["resource_coverage"]["VENDORS"]["matched_existing"] == 0
        assert stale["resource_coverage"]["VENDORS"]["needs_review"] == 1
        assert stale["review_fingerprint"] != saved["review_fingerprint"]
        expired = get_yardi_review_dry_run_status(run.id, Response(), db, actor)
        assert expired["is_current"] is False
        assert expired["saved_review_fingerprint"] == saved["review_fingerprint"]

        vendor.deleted_at = None
        db.commit()
        recovered = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert recovered["review_fingerprint"] == original["review_fingerprint"]
        assert recovered["resource_coverage"]["VENDORS"]["matched_existing"] == 1
        assert get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )["is_current"] is True
        db.refresh(vendor)
        assert vendor.company_name == "Untouched Vendor"
        assert vendor.deleted_at is None
        assert row.resolution_action == "MATCH_EXISTING"
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
        ).count() == 0
        assert recovered["customer_business_mutation"] is False
    finally:
        db.close()
        engine.dispose()


def test_unbound_vendor_review_dry_run_tracks_which_target_was_archived():
    """Equal resource totals do not make a different stale Vendor interchangeable."""
    from datetime import datetime
    from app.models.platform_migration import PlatformMigrationItem
    from app.models.vendor import Vendor
    from app.routers.yardi_migrations import get_yardi_review_dry_run_status

    db, engine = _session()
    try:
        actor, org, first_vendor, run, first_row = seed_vendor(
            db, slug="yardi-reviewed-vendor-archival-swap",
        )
        second_vendor = Vendor(
            organization_id=org.id, company_name="Untouched Second Vendor",
        )
        db.add(second_vendor)
        db.commit()
        upload = stage_yardi_file(
            db, run=run, filename="second-reviewed-vendor.csv",
            content=b"Vendor Ref,Company Name\nV-2,Second Source Vendor\n",
            resource_override="VENDORS", sheet_name=None,
            explicit_mapping={"source_id": "Vendor Ref", "name": "Company Name"},
            platform_user_id=actor.id,
        )
        db.commit()
        second_row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id,
        ).one()
        for row, vendor in ((first_row, first_vendor), (second_row, second_vendor)):
            assert match_yardi_staged_vendor(
                run.id, row.id, YardiVendorMatchIn(target_vendor_id=vendor.id),
                db, actor,
            )["replayed"] is False
        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["resource_coverage"]["VENDORS"]["matched_existing"] == 2

        first_vendor.deleted_at = datetime.utcnow()
        db.commit()
        first_stale = get_yardi_reconciliation(run.id, Response(), db, actor)
        counts = first_stale["resource_coverage"]["VENDORS"]
        assert counts["matched_existing"] == 1
        assert counts["needs_review"] == 1
        saved = dry_run_yardi_review(run.id, db, actor)
        assert saved["review_fingerprint"] == first_stale["review_fingerprint"]

        # Exchange only the fixture's unavailable customer target. Aggregate
        # counters stay the same but a DIFFERENT source row is now stale.
        first_vendor.deleted_at = None
        second_vendor.deleted_at = datetime.utcnow()
        db.commit()
        second_stale = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert second_stale["resource_coverage"] == first_stale["resource_coverage"]
        assert second_stale["review_fingerprint"] != first_stale["review_fingerprint"]
        stale_status = get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )
        assert stale_status["is_current"] is False
        assert stale_status["saved_review_fingerprint"] == saved["review_fingerprint"]

        first_vendor.deleted_at = datetime.utcnow()
        second_vendor.deleted_at = None
        db.commit()
        restored_first = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert restored_first["review_fingerprint"] == first_stale["review_fingerprint"]
        assert get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )["is_current"] is True

        first_vendor.deleted_at = None
        db.commit()
        recovered = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert recovered["review_fingerprint"] == baseline["review_fingerprint"]
        assert recovered["resource_coverage"]["VENDORS"]["matched_existing"] == 2
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
        ).count() == 0
        db.refresh(first_vendor)
        db.refresh(second_vendor)
        assert first_vendor.company_name == "Untouched Vendor"
        assert second_vendor.company_name == "Untouched Second Vendor"
        assert first_row.resolution_action == "MATCH_EXISTING"
        assert second_row.resolution_action == "MATCH_EXISTING"
        assert recovered["customer_business_mutation"] is False
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize("resource,seed,match,request_cls,target_field,header,source_id", [
    ("OWNERS", seed_owner, match_yardi_staged_owner, YardiOwnerMatchIn,
     "target_owner_user_id", "Owner Ref", "O-2"),
    ("TENANTS", seed_tenant, match_yardi_staged_tenant, YardiTenantMatchIn,
     "target_tenant_user_id", "Resident Ref", "R-2"),
])
@pytest.mark.parametrize("invalid_field", ["is_active", "role", "deleted_at"])
def test_unbound_reviewed_user_eligibility_swap_expires_equal_count_dry_run(
    resource, seed, match, request_cls, target_field, header, source_id,
    invalid_field,
):
    """Two distinct stale customer targets must not share one review snapshot."""
    from datetime import datetime
    from app.models.platform_migration import PlatformMigrationItem
    from app.models.user import User, UserRole
    from app.routers.yardi_migrations import get_yardi_review_dry_run_status

    db, engine = _session()
    try:
        slug = f"yardi-user-eligibility-swap-{resource.lower()}-{invalid_field}"
        actor, org, first_user, run, first_row = seed(db, slug=slug)
        second_user = User(
            organization_id=org.id, role=first_user.role,
            email=f"{slug}-second@example.test", hashed_password="second-preserved-hash",
            first_name="Second", last_name="Preserved", is_active=True,
        )
        db.add(second_user)
        db.commit()
        upload = stage_yardi_file(
            db, run=run, filename="second-reviewed-user.csv",
            content=f"{header},Full Name\n{source_id},Second Reviewed User\n".encode(),
            resource_override=resource, sheet_name=None,
            explicit_mapping={"source_id": header, "name": "Full Name"},
            platform_user_id=actor.id,
        )
        db.commit()
        second_row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id,
        ).one()
        for row, target in ((first_row, first_user), (second_row, second_user)):
            assert match(
                run.id, row.id, request_cls(**{target_field: target.id}), db, actor,
            )["replayed"] is False
        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["resource_coverage"][resource]["matched_existing"] == 2
        assert baseline["resource_coverage"][resource]["needs_review"] == 0

        original = getattr(first_user, invalid_field)
        invalid = (
            False if invalid_field == "is_active"
            else (UserRole.TENANT if resource == "OWNERS" else UserRole.OWNER)
            if invalid_field == "role" else datetime.utcnow()
        )
        setattr(first_user, invalid_field, invalid)
        db.commit()
        first_stale = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert first_stale["resource_coverage"][resource]["matched_existing"] == 1
        assert first_stale["resource_coverage"][resource]["needs_review"] == 1
        saved = dry_run_yardi_review(run.id, db, actor)
        assert saved["review_fingerprint"] == first_stale["review_fingerprint"]

        # Eligibility swaps between targets, not total resource coverage.
        setattr(first_user, invalid_field, original)
        setattr(second_user, invalid_field, invalid)
        db.commit()
        second_stale = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert second_stale["resource_coverage"] == first_stale["resource_coverage"]
        assert second_stale["review_fingerprint"] != first_stale["review_fingerprint"]
        expired = get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )
        assert expired["is_current"] is False
        assert expired["saved_review_fingerprint"] == saved["review_fingerprint"]

        setattr(first_user, invalid_field, invalid)
        setattr(second_user, invalid_field, original)
        db.commit()
        restored = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert restored["review_fingerprint"] == first_stale["review_fingerprint"]
        assert get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )["is_current"] is True

        setattr(first_user, invalid_field, original)
        db.commit()
        recovered = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert recovered["review_fingerprint"] == baseline["review_fingerprint"]
        assert recovered["resource_coverage"][resource]["matched_existing"] == 2
        assert recovered["resource_coverage"][resource]["needs_review"] == 0
        assert recovered["customer_business_mutation"] is False
        assert first_row.resolution_action == "MATCH_EXISTING"
        assert second_row.resolution_action == "MATCH_EXISTING"
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
        ).count() == 0
        db.refresh(first_user)
        db.refresh(second_user)
        assert first_user.hashed_password == "preserved-hash"
        assert second_user.hashed_password == "second-preserved-hash"
        assert first_user.first_name == "Existing"
        assert second_user.first_name == "Second"
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize("resource", ["PROPERTIES", "UNITS"])
@pytest.mark.parametrize("invalid_field", ["is_active", "deleted_at"])
def test_unbound_reviewed_inventory_eligibility_swap_expires_equal_count_dry_run(
    resource, invalid_field,
):
    """Property/Unit reviewed target swaps need exact stale-row evidence."""
    from datetime import datetime
    from app.models.platform_migration import PlatformMigrationItem
    from app.models.platform_user import PlatformUserRole
    from app.models.property import Property, Unit
    from app.routers.yardi_migrations import (
        YardiPropertyMatchIn, YardiUnitMatchIn, get_yardi_review_dry_run_status,
        match_yardi_staged_property, match_yardi_staged_unit,
    )
    from test_yardi_migrations import _org, _platform_user

    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(
            db, f"yardi-inventory-target-swap-{resource.lower()}-{invalid_field}",
        )
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="reviewed-inventory-status-swap", status="DRAFT",
        )
        parent = Property(
            organization_id=org.id, name="Unchanged Unit Parent",
            address_line1="1 Parent", city="Cleveland", state="OH", zip_code="44113",
        )
        db.add_all([run, parent])
        db.flush()

        if resource == "PROPERTIES":
            first = Property(
                organization_id=org.id, name="Unchanged First Property",
                address_line1="2 First", city="Cleveland", state="OH", zip_code="44113",
            )
            second = Property(
                organization_id=org.id, name="Unchanged Second Property",
                address_line1="3 Second", city="Cleveland", state="OH", zip_code="44113",
            )
            db.add_all([first, second])
            db.commit()
            upload = stage_yardi_file(
                db, run=run, filename="reviewed-property-target-swap.csv",
                content=(
                    b"ID,Name,Street,City,State,Zip\n"
                    b"P-1,First Source,2 First,Cleveland,OH,44113\n"
                    b"P-2,Second Source,3 Second,Cleveland,OH,44113\n"
                ),
                resource_override="PROPERTIES", sheet_name=None,
                explicit_mapping={
                    "source_id": "ID", "name": "Name", "address_line1": "Street",
                    "city": "City", "state": "State", "zip_code": "Zip",
                },
                platform_user_id=actor.id,
            )
            match = match_yardi_staged_property
            payload_type = YardiPropertyMatchIn
            target_field = "target_property_id"
        else:
            first = Unit(property_id=parent.id, unit_number="101", is_active=True)
            second = Unit(property_id=parent.id, unit_number="102", is_active=True)
            db.add_all([first, second])
            db.add(PlatformMigrationItem(
                run_id=run.id, organization_id=org.id, provider="YARDI",
                resource="PROPERTIES", source_id="P-PARENT",
                target_entity="PROPERTY", target_id=parent.id,
                source_fingerprint="original-parent-evidence",
            ))
            db.commit()
            upload = stage_yardi_file(
                db, run=run, filename="reviewed-unit-target-swap.csv",
                content=b"ID,Parent,Label\nU-1,P-PARENT,101\nU-2,P-PARENT,102\n",
                resource_override="UNITS", sheet_name=None,
                explicit_mapping={
                    "source_id": "ID", "source_property_id": "Parent",
                    "unit_name": "Label",
                },
                platform_user_id=actor.id,
            )
            match = match_yardi_staged_unit
            payload_type = YardiUnitMatchIn
            target_field = "target_unit_id"
        db.commit()
        staged = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id,
        ).order_by(PlatformMigrationStagedRow.id.asc()).all()
        assert len(staged) == 2
        for row, target in zip(staged, (first, second)):
            assert match(
                run.id, row.id, payload_type(**{target_field: target.id}), db, actor,
            )["replayed"] is False

        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["resource_coverage"][resource]["matched_existing"] == 2
        assert baseline["resource_coverage"][resource]["needs_review"] == 0

        original = getattr(first, invalid_field)
        invalid = False if invalid_field == "is_active" else datetime.utcnow()
        setattr(first, invalid_field, invalid)
        db.commit()
        first_stale = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert first_stale["resource_coverage"][resource]["matched_existing"] == 1
        assert first_stale["resource_coverage"][resource]["needs_review"] == 1
        saved = dry_run_yardi_review(run.id, db, actor)
        assert saved["review_fingerprint"] == first_stale["review_fingerprint"]

        setattr(first, invalid_field, original)
        setattr(second, invalid_field, invalid)
        db.commit()
        second_stale = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert second_stale["resource_coverage"] == first_stale["resource_coverage"]
        assert second_stale["review_fingerprint"] != first_stale["review_fingerprint"]
        status = get_yardi_review_dry_run_status(run.id, Response(), db, actor)
        assert status["is_current"] is False
        assert status["saved_review_fingerprint"] == saved["review_fingerprint"]

        setattr(first, invalid_field, invalid)
        setattr(second, invalid_field, original)
        db.commit()
        restored = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert restored["review_fingerprint"] == first_stale["review_fingerprint"]
        assert get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )["is_current"] is True

        setattr(first, invalid_field, original)
        db.commit()
        recovered = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert recovered["review_fingerprint"] == baseline["review_fingerprint"]
        assert recovered["resource_coverage"][resource]["matched_existing"] == 2
        assert recovered["resource_coverage"][resource]["needs_review"] == 0
        assert recovered["customer_business_mutation"] is False
        assert all(row.resolution_action == "MATCH_EXISTING" for row in staged)
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == resource,
        ).count() == 0
        db.refresh(first)
        db.refresh(second)
        if resource == "PROPERTIES":
            assert first.name == "Unchanged First Property"
            assert second.name == "Unchanged Second Property"
        else:
            assert first.unit_number == "101" and first.property_id == parent.id
            assert second.unit_number == "102" and second.property_id == parent.id
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize("resource,seed,entity,header,second_id,second_label,invalid_field", [
    ("OWNERS", seed_owner, "OWNER_USER", "Owner Ref", "O-2",
     "Full Name", "is_active"),
    ("OWNERS", seed_owner, "OWNER_USER", "Owner Ref", "O-2",
     "Full Name", "role"),
    ("TENANTS", seed_tenant, "TENANT_USER", "Resident Ref", "R-2",
     "Full Name", "is_active"),
    ("TENANTS", seed_tenant, "TENANT_USER", "Resident Ref", "R-2",
     "Full Name", "role"),
    ("VENDORS", seed_vendor, "VENDOR", "Vendor Ref", "V-2",
     "Company Name", "deleted_at"),
])
def test_unreviewed_durable_identity_eligibility_swap_expires_equal_count_dry_run(
    resource, seed, entity, header, second_id, second_label, invalid_field,
):
    """Unreviewed durable mapped identities also need exact target staleness."""
    from datetime import datetime
    from app.models.platform_migration import PlatformMigrationItem
    from app.models.user import User, UserRole
    from app.models.vendor import Vendor
    from app.routers.yardi_migrations import get_yardi_review_dry_run_status

    db, engine = _session()
    try:
        slug = f"yardi-durable-eligibility-swap-{resource.lower()}-{invalid_field}"
        actor, org, first, run, first_row = seed(db, slug=slug)
        if resource == "VENDORS":
            second = Vendor(
                organization_id=org.id, company_name="Untouched Durable Second Vendor",
            )
        else:
            second = User(
                organization_id=org.id, role=first.role,
                email=f"{slug}-second@example.test",
                hashed_password="untouched-second-password",
                first_name="Second", last_name="Untouched",
                is_active=True,
            )
        db.add(second)
        db.commit()
        upload = stage_yardi_file(
            db, run=run, filename="second-durable-identity.csv",
            content=f"{header},{second_label}\n{second_id},Second Durable Source\n".encode(),
            resource_override=resource, sheet_name=None,
            explicit_mapping={"source_id": header, "name": second_label},
            platform_user_id=actor.id,
        )
        db.commit()
        second_row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id,
        ).one()
        db.add_all([
            PlatformMigrationItem(
                run_id=run.id, organization_id=org.id, provider="YARDI",
                resource=resource, source_id=row.source_id, target_entity=entity,
                target_id=target.id, source_fingerprint=row.row_fingerprint,
            )
            for row, target in ((first_row, first), (second_row, second))
        ])
        db.commit()
        assert first_row.resolution_action is None
        assert second_row.resolution_action is None
        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["resource_coverage"][resource]["mapped"] == 2
        assert baseline["resource_coverage"][resource]["needs_review"] == 0

        original = getattr(first, invalid_field)
        invalid = (
            False if invalid_field == "is_active"
            else (UserRole.TENANT if resource == "OWNERS" else UserRole.OWNER)
            if invalid_field == "role" else datetime.utcnow()
        )
        setattr(first, invalid_field, invalid)
        db.commit()
        first_stale = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert first_stale["resource_coverage"][resource]["mapped"] == 1
        assert first_stale["resource_coverage"][resource]["needs_review"] == 1
        saved = dry_run_yardi_review(run.id, db, actor)
        assert saved["review_fingerprint"] == first_stale["review_fingerprint"]

        setattr(first, invalid_field, original)
        setattr(second, invalid_field, invalid)
        db.commit()
        second_stale = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert second_stale["resource_coverage"] == first_stale["resource_coverage"]
        assert second_stale["review_fingerprint"] != first_stale["review_fingerprint"]
        expired = get_yardi_review_dry_run_status(run.id, Response(), db, actor)
        assert expired["is_current"] is False
        assert expired["saved_review_fingerprint"] == saved["review_fingerprint"]

        setattr(first, invalid_field, invalid)
        setattr(second, invalid_field, original)
        db.commit()
        restored = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert restored["review_fingerprint"] == first_stale["review_fingerprint"]
        assert get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )["is_current"] is True

        setattr(first, invalid_field, original)
        db.commit()
        recovered = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert recovered["review_fingerprint"] == baseline["review_fingerprint"]
        assert recovered["resource_coverage"][resource]["mapped"] == 2
        assert recovered["resource_coverage"][resource]["needs_review"] == 0
        assert recovered["customer_business_mutation"] is False
        assert first_row.resolution_action is None
        assert second_row.resolution_action is None
        mapped = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == resource,
        ).all()
        assert len(mapped) == 2
        assert {m.target_id for m in mapped} == {first.id, second.id}
        db.refresh(first)
        db.refresh(second)
        if resource == "VENDORS":
            assert first.company_name == "Untouched Vendor"
            assert second.company_name == "Untouched Durable Second Vendor"
        else:
            assert first.hashed_password == "preserved-hash"
            assert second.hashed_password == "untouched-second-password"
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize("resource", ["PROPERTIES", "UNITS"])
@pytest.mark.parametrize("invalid_field", ["is_active", "deleted_at"])
def test_unreviewed_durable_inventory_eligibility_swap_expires_equal_count_dry_run(
    resource, invalid_field,
):
    """A durable target eligibility swap invalidates an equal-count dry run."""
    from datetime import datetime
    from app.models.platform_migration import PlatformMigrationItem
    from app.models.platform_user import PlatformUserRole
    from app.models.property import Property, Unit
    from app.routers.yardi_migrations import get_yardi_review_dry_run_status
    from test_yardi_migrations import _org, _platform_user

    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(
            db, f"yardi-durable-inventory-swap-{resource.lower()}-{invalid_field}",
        )
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="durable-inventory-status-swap", status="DRAFT",
        )
        parent = Property(
            organization_id=org.id, name="Original Durable Parent",
            address_line1="1 Parent", city="Cleveland", state="OH", zip_code="44113",
        )
        db.add_all([run, parent])
        db.flush()
        if resource == "PROPERTIES":
            first = Property(
                organization_id=org.id, name="Untouched Durable First",
                address_line1="2 First", city="Cleveland", state="OH", zip_code="44113",
            )
            second = Property(
                organization_id=org.id, name="Untouched Durable Second",
                address_line1="3 Second", city="Cleveland", state="OH", zip_code="44113",
            )
            db.add_all([first, second])
            db.commit()
            upload = stage_yardi_file(
                db, run=run, filename="durable-property-target-swap.csv",
                content=(
                    b"ID,Name,Street,City,State,Zip\n"
                    b"P-1,First Source,2 First,Cleveland,OH,44113\n"
                    b"P-2,Second Source,3 Second,Cleveland,OH,44113\n"
                ),
                resource_override="PROPERTIES", sheet_name=None,
                explicit_mapping={
                    "source_id": "ID", "name": "Name", "address_line1": "Street",
                    "city": "City", "state": "State", "zip_code": "Zip",
                }, platform_user_id=actor.id,
            )
            entity = "PROPERTY"
        else:
            first = Unit(property_id=parent.id, unit_number="101", is_active=True)
            second = Unit(property_id=parent.id, unit_number="102", is_active=True)
            db.add_all([first, second])
            db.add(PlatformMigrationItem(
                run_id=run.id, organization_id=org.id, provider="YARDI",
                resource="PROPERTIES", source_id="P-PARENT",
                target_entity="PROPERTY", target_id=parent.id,
                source_fingerprint="original-durable-property-parent",
            ))
            db.commit()
            upload = stage_yardi_file(
                db, run=run, filename="durable-unit-target-swap.csv",
                content=b"ID,Parent,Label\nU-1,P-PARENT,101\nU-2,P-PARENT,102\n",
                resource_override="UNITS", sheet_name=None,
                explicit_mapping={
                    "source_id": "ID", "source_property_id": "Parent",
                    "unit_name": "Label",
                }, platform_user_id=actor.id,
            )
            entity = "UNIT"
        db.commit()
        staged = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id,
        ).order_by(PlatformMigrationStagedRow.id.asc()).all()
        assert len(staged) == 2
        assert all(row.resolution_action is None for row in staged)
        db.add_all([
            PlatformMigrationItem(
                run_id=run.id, organization_id=org.id, provider="YARDI",
                resource=resource, source_id=row.source_id, target_entity=entity,
                target_id=target.id, source_fingerprint=row.row_fingerprint,
            )
            for row, target in zip(staged, (first, second))
        ])
        db.commit()
        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["resource_coverage"][resource]["mapped"] == 2
        assert baseline["resource_coverage"][resource]["needs_review"] == 0

        original = getattr(first, invalid_field)
        invalid = False if invalid_field == "is_active" else datetime.utcnow()
        setattr(first, invalid_field, invalid)
        db.commit()
        first_stale = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert first_stale["resource_coverage"][resource]["mapped"] == 1
        assert first_stale["resource_coverage"][resource]["needs_review"] == 1
        saved = dry_run_yardi_review(run.id, db, actor)
        assert saved["review_fingerprint"] == first_stale["review_fingerprint"]

        setattr(first, invalid_field, original)
        setattr(second, invalid_field, invalid)
        db.commit()
        second_stale = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert second_stale["resource_coverage"] == first_stale["resource_coverage"]
        assert second_stale["review_fingerprint"] != first_stale["review_fingerprint"]
        status = get_yardi_review_dry_run_status(run.id, Response(), db, actor)
        assert status["is_current"] is False
        assert status["saved_review_fingerprint"] == saved["review_fingerprint"]

        setattr(first, invalid_field, invalid)
        setattr(second, invalid_field, original)
        db.commit()
        restored = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert restored["review_fingerprint"] == first_stale["review_fingerprint"]
        assert get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )["is_current"] is True

        setattr(first, invalid_field, original)
        db.commit()
        recovered = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert recovered["review_fingerprint"] == baseline["review_fingerprint"]
        assert recovered["resource_coverage"][resource]["mapped"] == 2
        assert recovered["resource_coverage"][resource]["needs_review"] == 0
        assert recovered["customer_business_mutation"] is False
        assert all(row.resolution_action is None for row in staged)
        mapped = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == resource,
        ).all()
        assert len(mapped) == 2
        assert {m.target_id for m in mapped} == {first.id, second.id}
        db.refresh(first)
        db.refresh(second)
        if resource == "PROPERTIES":
            assert first.name == "Untouched Durable First"
            assert second.name == "Untouched Durable Second"
        else:
            assert first.unit_number == "101" and first.property_id == parent.id
            assert second.unit_number == "102" and second.property_id == parent.id
    finally:
        db.close()
        engine.dispose()
