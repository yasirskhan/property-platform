"""Historical source parent claims affect both reviewed and unreviewed Unit readiness."""
import pytest
from fastapi import Response

from app.models.platform_migration import (
    PlatformMigrationItem, PlatformMigrationRun, PlatformMigrationStagedRow,
)
from app.routers.yardi_migrations import get_yardi_reconciliation
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_lease_identity_acceptance import _seed
from test_yardi_migrations import _session


@pytest.mark.parametrize("reviewed", [True, False])
def test_original_unit_parent_claims_are_revalidated_without_customer_mutation(reviewed):
    db, engine = _session()
    try:
        actor, org, run, prop, alternative, unit, tenant, lease = _seed(
            db, slug="yardi-reconcile-parent-" + ("reviewed" if reviewed else "unreviewed")
        )
        staged_unit = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.resource == "UNITS",
        ).one()
        if not reviewed:
            staged_unit.resolution_action = None
            staged_unit.resolution_target_unit_id = None
            db.commit()

        stat = "matched_existing" if reviewed else "mapped"
        def current():
            return get_yardi_reconciliation(run.id, Response(), db, actor)
        baseline = current()
        assert baseline["resource_coverage"]["UNITS"][stat] == 1

        other_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="other-parent-evidence", status="DRAFT",
        )
        db.add(other_run)
        db.flush()
        other_binding = PlatformMigrationItem(
            run_id=other_run.id, organization_id=org.id, provider="YARDI",
            resource="PROPERTIES", source_id="ANOTHER-PROPERTY",
            target_entity="PROPERTY", target_id=prop.id,
            source_fingerprint="another-provider-source",
        )
        db.add(other_binding)
        db.commit()

        contested_target = current()
        assert contested_target["resource_coverage"]["UNITS"][stat] == 0
        assert contested_target["resource_coverage"]["UNITS"]["needs_review"] >= 1
        assert contested_target["review_fingerprint"] != baseline["review_fingerprint"]

        # Another foreign durable Property source ID still claims the same
        # target; unchanged stale counters must not reuse old review evidence.
        other_binding.source_id = "YET-ANOTHER-PROPERTY"
        db.commit()
        changed_competitor = current()
        assert changed_competitor["resource_coverage"] == contested_target["resource_coverage"]
        assert changed_competitor["review_fingerprint"] != contested_target["review_fingerprint"]
        other_binding.source_id = "ANOTHER-PROPERTY"
        db.commit()
        restored_competitor = current()
        assert restored_competitor["review_fingerprint"] == contested_target["review_fingerprint"]

        other_binding.source_id = "P1"
        db.commit()
        same_source = current()
        assert same_source["resource_coverage"]["UNITS"][stat] == 1
        assert same_source["review_fingerprint"] == baseline["review_fingerprint"]

        other_binding.target_id = alternative.id
        db.commit()
        divergent_source = current()
        assert divergent_source["resource_coverage"]["UNITS"][stat] == 0
        assert divergent_source["review_fingerprint"] != baseline["review_fingerprint"]

        other_binding.target_id = prop.id
        db.commit()
        assert current()["resource_coverage"]["UNITS"][stat] == 1

        # An independent retained staff review claims the original Property.
        staged = stage_yardi_file(
            db, run=other_run, filename="competing-parent-review.csv",
            content=b"ID,Name,Street,City,State,Zip\nPX,Other Source,1 Main,Cleveland,OH,44113\n",
            resource_override="PROPERTIES", sheet_name=None,
            explicit_mapping={
                "source_id": "ID", "name": "Name", "address_line1": "Street",
                "city": "City", "state": "State", "zip_code": "Zip",
            }, platform_user_id=actor.id,
        )
        db.commit()
        reviewed_parent = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == staged.upload.id,
        ).one()
        reviewed_parent.resolution_action = "MATCH_EXISTING"
        reviewed_parent.resolution_target_id = prop.id
        db.commit()
        contested_review = current()
        assert contested_review["resource_coverage"]["UNITS"][stat] == 0
        reviewed_parent.source_id = "P1"
        db.commit()
        restored = current()
        assert restored["resource_coverage"]["UNITS"][stat] == 1
        assert restored["review_fingerprint"] == baseline["review_fingerprint"]

        db.refresh(prop)
        db.refresh(unit)
        db.refresh(tenant)
        db.refresh(staged_unit)
        assert prop.name == "Original"
        assert unit.property_id == prop.id
        assert unit.unit_number == "101"
        assert tenant.hashed_password == "unchanged-password-hash"
        assert staged_unit.resolution_action == ("MATCH_EXISTING" if reviewed else None)
        assert restored["customer_business_mutation"] is False
    finally:
        db.close()
        engine.dispose()
