"""One historical Yardi durable-claim snapshot serves identity and Lease coverage."""
from fastapi import Response

from app.models.lease import Lease
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.routers import yardi_migrations as yardi
from test_yardi_lease_identity_acceptance import _seed
from test_yardi_migrations import _session


def test_identity_and_lease_reconciliation_share_historical_durable_claims(monkeypatch):
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, lease_row = _seed(
            db, slug="yardi-one-historical-durable-claim-snapshot"
        )
        lease_count = db.query(Lease).count()
        mapping_count = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
        ).count()
        original_helper = yardi._yardi_lease_durable_identity_claims
        calls = []

        def observed(*args, **kwargs):
            calls.append((kwargs["organization_id"], len(kwargs["mappings"])))
            return original_helper(*args, **kwargs)

        monkeypatch.setattr(yardi, "_yardi_lease_durable_identity_claims", observed)

        def current():
            calls.clear()
            result = yardi.get_yardi_reconciliation(run.id, Response(), db, actor)
            assert calls == [(org.id, mapping_count)]
            return result

        baseline = current()
        base_lease = baseline["lease_relationship_readiness"]
        assert base_lease["complete_identity_links"] == 1
        assert base_lease["identity_target_binding_collisions"] == 0
        assert base_lease["identity_source_binding_collisions"] == 0
        assert baseline["customer_business_mutation"] is False

        competing_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="other-original-property-claim", status="DRAFT",
        )
        db.add(competing_run)
        db.flush()
        competing = PlatformMigrationItem(
            run_id=competing_run.id, organization_id=org.id, provider="YARDI",
            resource="PROPERTIES", source_id="OTHER-P", target_entity="PROPERTY",
            target_id=original.id, source_fingerprint="other-original-source",
        )
        db.add(competing)
        db.commit()
        contested = current()
        assert contested["lease_relationship_readiness"]["identity_target_binding_collisions"] == 1
        assert contested["lease_relationship_readiness"]["complete_identity_links"] == 0
        assert contested["review_fingerprint"] != baseline["review_fingerprint"]

        # Two Yardi runs reporting exactly the SAME stable source and customer
        # target do not represent independent competing identity claims.
        competing.source_id = "P1"
        db.commit()
        recovered = current()
        assert recovered["review_fingerprint"] == baseline["review_fingerprint"]
        assert recovered["lease_relationship_readiness"]["complete_identity_links"] == 1

        # The same source ID mapped to a DIFFERENT customer target must
        # independently invalidate Lease readiness even without staff review.
        competing.target_id = alternate.id
        db.commit()
        diverged = current()
        assert diverged["lease_relationship_readiness"]["identity_source_binding_collisions"] == 1
        assert diverged["lease_relationship_readiness"]["complete_identity_links"] == 0
        assert diverged["review_fingerprint"] != baseline["review_fingerprint"]

        competing.target_id = original.id
        db.commit()
        final = current()
        assert final["review_fingerprint"] == baseline["review_fingerprint"]
        db.refresh(original)
        db.refresh(alternate)
        db.refresh(unit)
        db.refresh(tenant)
        db.refresh(lease_row)
        assert original.name == "Original" and alternate.name == "Alternate"
        assert unit.property_id == original.id
        assert tenant.hashed_password == "unchanged-password-hash"
        assert lease_row.resolution_action is None
        assert db.query(Lease).count() == lease_count
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
        ).count() == mapping_count
        assert final["controlled_commit_enabled"] is False
    finally:
        db.close()
        engine.dispose()
