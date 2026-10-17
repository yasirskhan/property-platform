"""Yardi read-only Lease coverage shares the validated live target snapshot.

No customer Lease, occupancy, payment or financial records are created.
"""
from fastapi import Response
from sqlalchemy import event

from app.models.lease import Lease
from app.models.platform_migration import PlatformMigrationItem
from app.routers.yardi_migrations import get_yardi_reconciliation
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_lease_identity_acceptance import _seed
from test_yardi_migrations import _session


def test_lease_aggregate_reuses_exact_scoped_live_identity_snapshot():
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, lease = _seed(
            db, slug="yardi-lease-shared-target-snapshot"
        )
        before_leases = db.query(Lease).count()
        before_mappings = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
        ).count()

        def inspect():
            selects = {"properties": 0, "units": 0, "tenants": 0}

            def observe(connection, cursor, statement, parameters, context, executemany):
                sql = " ".join(statement.lower().split())
                if not sql.startswith("select"):
                    return
                if " from properties " in sql and "properties.is_active" in sql:
                    selects["properties"] += 1
                if " from units join properties " in sql and "units.is_active" in sql:
                    selects["units"] += 1
                if " from users " in sql and "users.role" in sql:
                    selects["tenants"] += 1

            event.listen(engine, "before_cursor_execute", observe)
            try:
                snapshot = get_yardi_reconciliation(run.id, Response(), db, actor)
            finally:
                event.remove(engine, "before_cursor_execute", observe)
            return snapshot, selects

        ready, counts = inspect()
        assert counts == {"properties": 1, "units": 1, "tenants": 1}
        assert ready["lease_relationship_readiness"]["complete_identity_links"] == 1
        assert ready["lease_relationship_readiness"]["source_review_ready"] == 1

        # Current customer activity must invalidate both identity and Lease
        # readiness without changing an accepted/staged source review.
        original.is_active = False
        db.commit()
        archived, archived_counts = inspect()
        assert archived_counts == counts
        assert archived["lease_relationship_readiness"]["missing_property"] == 1
        assert archived["lease_relationship_readiness"]["missing_unit"] == 1
        assert archived["lease_relationship_readiness"]["complete_identity_links"] == 0
        assert archived["review_fingerprint"] != ready["review_fingerprint"]

        original.is_active = True
        db.commit()
        recovered, recovered_counts = inspect()
        assert recovered_counts == counts
        assert recovered["review_fingerprint"] == ready["review_fingerprint"]

        # Additional source Leases cannot cause another live customer SELECT
        # pass, even where this second Lease references a different Property.
        stage_yardi_file(
            db, run=run, filename="second-lease.csv",
            content=b"Lease,Tenant,Property,Unit\nL2,T1,P2,U1\n",
            resource_override="LEASE_OCCUPANCY", sheet_name=None,
            explicit_mapping={
                "source_id": "Lease", "source_tenant_id": "Tenant",
                "source_property_id": "Property", "source_unit_id": "Unit",
            }, platform_user_id=actor.id,
        )
        db.commit()
        two, more_counts = inspect()
        assert more_counts == counts
        assert two["lease_relationship_readiness"]["staged"] == 2
        assert two["lease_relationship_readiness"]["complete_identity_links"] == 1
        assert two["lease_relationship_readiness"]["unit_property_mismatch"] == 1
        assert two["review_fingerprint"] != recovered["review_fingerprint"]

        db.refresh(original)
        db.refresh(alternate)
        db.refresh(unit)
        db.refresh(tenant)
        db.refresh(lease)
        assert original.name == "Original" and original.is_active is True
        assert alternate.name == "Alternate"
        assert unit.property_id == original.id
        assert tenant.hashed_password == "unchanged-password-hash"
        assert lease.resolution_action is None
        assert db.query(Lease).count() == before_leases
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
        ).count() == before_mappings
        assert two["customer_business_mutation"] is False
        assert two["controlled_commit_enabled"] is False
    finally:
        db.close()
        engine.dispose()
