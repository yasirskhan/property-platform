"""Original mapped Property source drift blocks Yardi source-review acceptance."""
import pytest
from fastapi import HTTPException, Response

from app.models.lease import Lease
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationStagedRow
from app.routers.yardi_migrations import (
    YardiRowSkipIn, accept_yardi_staged_lease_relationship,
    get_yardi_reconciliation, list_yardi_lease_relationships,
    skip_yardi_staged_row,
)
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_lease_identity_acceptance import _seed
from test_yardi_migrations import _session


def test_single_changed_original_property_source_invalidates_replay_and_unit_readiness():
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, lease_row = _seed(
            db, slug="yardi-original-property-fingerprint-drift"
        )
        lease_count = db.query(Lease).count()
        binding_count = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id
        ).count()
        property_binding = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "PROPERTIES",
            PlatformMigrationItem.source_id == "P1",
        ).one()
        initial = accept_yardi_staged_lease_relationship(
            run.id, lease_row.id, db, actor
        )
        assert initial["replayed"] is False
        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["lease_relationship_readiness"]["source_review_ready"] == 1
        assert baseline["lease_relationship_readiness"]["parent_property_source_drift"] == 0

        uploaded = stage_yardi_file(
            db, run=run, filename="changed-property-source.csv",
            content=b"ID,Name,Street,City,State,Zip\nP1,Changed Source Name,1 Main,Cleveland,OH,44113\n",
            resource_override="PROPERTIES", sheet_name=None,
            explicit_mapping={
                "source_id": "ID", "name": "Name", "address_line1": "Street",
                "city": "City", "state": "State", "zip_code": "Zip",
            }, platform_user_id=actor.id,
        )
        db.commit()
        staged = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == uploaded.upload.id
        ).one()
        assert staged.row_fingerprint != property_binding.source_fingerprint

        stale = get_yardi_reconciliation(run.id, Response(), db, actor)
        summary = stale["lease_relationship_readiness"]
        assert summary["identity_source_id_collisions"] == 0
        assert summary["parent_property_source_drift"] == 1
        assert summary["accepted_relationship_stale"] == 1
        assert summary["source_review_ready"] == 0
        assert summary["complete_identity_links"] == 0
        assert stale["resource_coverage"]["UNITS"]["matched_existing"] == 0
        assert stale["resource_coverage"]["UNITS"]["needs_review"] == 1
        assert stale["review_fingerprint"] != baseline["review_fingerprint"]

        preview = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10,
            db=db, current_user=actor,
        )["items"][0]
        assert "PROPERTY_SOURCE_VERSION_DRIFT" in preview["blockers"]
        assert preview["relationship_review_current"] is False
        with pytest.raises(HTTPException) as blocked:
            accept_yardi_staged_lease_relationship(run.id, lease_row.id, db, actor)
        assert blocked.value.status_code == 409

        # An unanchored, durably mapped source cannot simply be discarded
        # through SKIP; staff must genuinely reconcile its source fingerprint.
        with pytest.raises(HTTPException) as forbidden_skip:
            skip_yardi_staged_row(
                run.id, staged.id,
                YardiRowSkipIn(reason_code="UNSUPPORTED_SOURCE"),
                db, actor,
            )
        assert forbidden_skip.value.status_code == 409

        # Simulate an independently reviewed exact source-mapping repair in
        # fixture metadata, never through an automatic customer record merge.
        property_binding.source_fingerprint = staged.row_fingerprint
        db.commit()
        restored = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert restored["lease_relationship_readiness"]["parent_property_source_drift"] == 0
        assert restored["lease_relationship_readiness"]["source_review_ready"] == 1
        assert restored["lease_relationship_readiness"]["accepted_relationship_stale"] == 0
        assert restored["resource_coverage"]["UNITS"]["matched_existing"] == 1
        assert restored["review_fingerprint"] != stale["review_fingerprint"]
        again = accept_yardi_staged_lease_relationship(run.id, lease_row.id, db, actor)
        assert again["replayed"] is True
        after = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10,
            db=db, current_user=actor,
        )["items"][0]
        assert "PROPERTY_SOURCE_VERSION_DRIFT" not in after["blockers"]
        assert after["relationship_review_current"] is True

        db.refresh(original)
        db.refresh(alternate)
        db.refresh(unit)
        db.refresh(tenant)
        db.refresh(lease_row)
        assert original.name == "Original" and alternate.name == "Alternate"
        assert unit.property_id == original.id
        assert tenant.hashed_password == "unchanged-password-hash"
        assert lease_row.resolution_action == "ACCEPT_RELATIONSHIP"
        assert db.query(Lease).count() == lease_count
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id
        ).count() == binding_count
        assert restored["customer_business_mutation"] is False
        assert restored["controlled_commit_enabled"] is False
    finally:
        db.close()
        engine.dispose()
