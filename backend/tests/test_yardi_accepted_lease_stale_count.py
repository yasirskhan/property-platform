"""Accepted Yardi Lease source reviews become stale on changed linked evidence."""
from fastapi import Response

from app.models.lease import Lease
from app.models.platform_migration import PlatformMigrationStagedRow
from app.routers.yardi_migrations import (
    YardiRowSkipIn, accept_yardi_staged_lease_relationship,
    get_yardi_reconciliation, list_yardi_lease_relationships,
    skip_yardi_staged_row,
)
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_lease_identity_acceptance import _seed
from test_yardi_migrations import _session


def test_accepted_lease_stale_count_includes_duplicate_lease_and_moved_unit():
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, lease = _seed(
            db, slug="yardi-accepted-stale-count-evidence"
        )
        before_leases = db.query(Lease).count()
        accepted = accept_yardi_staged_lease_relationship(
            run.id, lease.id, db, actor
        )
        assert accepted["replayed"] is False

        def aggregate():
            return get_yardi_reconciliation(
                run.id, Response(), db, actor
            )

        def original_preview():
            return list_yardi_lease_relationships(
                run.id, Response(), offset=0, limit=10,
                db=db, current_user=actor,
            )["items"][0]

        initial = aggregate()
        assert initial["lease_relationship_readiness"]["accepted_relationship_stale"] == 0
        assert original_preview()["relationship_review_current"] is True

        uploaded = stage_yardi_file(
            db, run=run, filename="conflicting-lease.csv",
            content=b"Lease,Tenant,Property,Unit\nL1,T1,P2,U1\n",
            resource_override="LEASE_OCCUPANCY", sheet_name=None,
            explicit_mapping={
                "source_id": "Lease", "source_tenant_id": "Tenant",
                "source_property_id": "Property", "source_unit_id": "Unit",
            }, platform_user_id=actor.id,
        )
        db.commit()
        duplicate = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == uploaded.upload.id,
        ).one()
        contested = aggregate()
        assert contested["lease_relationship_readiness"]["lease_source_id_collisions"] >= 1
        assert contested["lease_relationship_readiness"]["accepted_relationship_stale"] == 1
        assert contested["review_fingerprint"] != initial["review_fingerprint"]
        assert "LEASE_SOURCE_ID_COLLISION" in original_preview()["blockers"]
        assert original_preview()["relationship_review_current"] is False

        excluded = skip_yardi_staged_row(
            run.id, duplicate.id,
            YardiRowSkipIn(reason_code="DUPLICATE_SOURCE"),
            db, actor,
        )
        assert excluded["action"] == "SKIP"
        after_skip = aggregate()
        assert after_skip["lease_relationship_readiness"]["accepted_relationship_stale"] == 0
        assert original_preview()["relationship_review_current"] is True

        # Both customer Properties are still active; changing only the Unit
        # parent must make the retained accepted Lease source review stale.
        unit.property_id = alternate.id
        db.commit()
        moved = aggregate()
        assert moved["lease_relationship_readiness"]["unit_property_mismatch"] == 1
        assert moved["lease_relationship_readiness"]["accepted_relationship_stale"] == 1
        assert moved["review_fingerprint"] != after_skip["review_fingerprint"]
        assert "UNIT_PROPERTY_MISMATCH" in original_preview()["blockers"]
        assert original_preview()["relationship_review_current"] is False

        unit.property_id = original.id
        db.commit()
        recovered = aggregate()
        assert recovered["lease_relationship_readiness"]["accepted_relationship_stale"] == 0
        assert recovered["review_fingerprint"] == after_skip["review_fingerprint"]
        assert original_preview()["relationship_review_current"] is True
        db.refresh(lease)
        db.refresh(original)
        db.refresh(alternate)
        db.refresh(unit)
        db.refresh(tenant)
        assert lease.resolution_action == "ACCEPT_RELATIONSHIP"
        assert original.name == "Original" and alternate.name == "Alternate"
        assert unit.property_id == original.id
        assert tenant.hashed_password == "unchanged-password-hash"
        assert db.query(Lease).count() == before_leases
        assert recovered["customer_business_mutation"] is False
        assert recovered["controlled_commit_enabled"] is False
    finally:
        db.close()
        engine.dispose()
