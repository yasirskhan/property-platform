"""Lease acceptance checks only its three actual Yardi source identities."""
import pytest
from fastapi import HTTPException, Response

from app.models.lease import Lease
from app.models.platform_migration import PlatformMigrationStagedRow
from app.routers import yardi_migrations as yardi
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_lease_identity_acceptance import _seed
from test_yardi_migrations import _session


def test_lease_acceptance_bounds_collision_scan_without_missing_other_upload_duplicates(monkeypatch):
    db, engine = _session()
    try:
        actor, org, run, prop, alternate, unit, tenant, lease_row = _seed(
            db, slug="yardi-lease-accept-collision-targeted"
        )
        before_leases = db.query(Lease).count()
        first = yardi.accept_yardi_staged_lease_relationship(
            run.id, lease_row.id, db, actor
        )
        assert first["replayed"] is False

        # Two unrelated Yardi Vendor uploads contain a genuine duplicate ID,
        # but the Lease source relationship does not depend on this Vendor.
        for name in ("First Vendor", "Different Vendor Version"):
            stage_yardi_file(
                db, run=run, filename=name.replace(" ", "_") + ".csv",
                content=("ID,Name\nV-UNRELATED," + name + "\n").encode(),
                resource_override="VENDORS", sheet_name=None,
                explicit_mapping={"source_id": "ID", "name": "Name"},
                platform_user_id=actor.id,
            )
            db.commit()

        original = yardi._yardi_unresolved_identity_sources
        requested = []

        def scoped(db_, run_, identities=None):
            requested.append(None if identities is None else set(identities))
            return original(db_, run_, identities=identities)

        monkeypatch.setattr(yardi, "_yardi_unresolved_identity_sources", scoped)
        repeated = yardi.accept_yardi_staged_lease_relationship(
            run.id, lease_row.id, db, actor
        )
        assert repeated["replayed"] is True
        expected = {
            ("PROPERTIES", "P1"), ("UNITS", "U1"), ("TENANTS", "T1"),
        }
        assert requested[-1] == expected

        # A second Unit export can contradict the original accepted Lease
        # from a different upload, even if it is outside the lease file.
        uploaded = stage_yardi_file(
            db, run=run, filename="changed-unit.csv",
            content=b"Unit,Parent,Label\nU1,P1,Changed Label\n",
            resource_override="UNITS", sheet_name=None,
            explicit_mapping={
                "source_id": "Unit", "source_property_id": "Parent",
                "unit_name": "Label",
            }, platform_user_id=actor.id,
        )
        db.commit()
        duplicate = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == uploaded.upload.id,
        ).one()
        result = yardi.get_yardi_reconciliation(run.id, Response(), db, actor)
        assert result["lease_relationship_readiness"]["identity_source_id_collisions"] == 1

        with pytest.raises(HTTPException) as conflict:
            yardi.accept_yardi_staged_lease_relationship(
                run.id, lease_row.id, db, actor
            )
        assert conflict.value.status_code == 409
        assert requested[-1] == expected

        excluded = yardi.skip_yardi_staged_row(
            run.id, duplicate.id,
            yardi.YardiRowSkipIn(reason_code="DUPLICATE_SOURCE"),
            db, actor,
        )
        assert excluded["action"] == "SKIP" and excluded["replayed"] is False
        restored = yardi.accept_yardi_staged_lease_relationship(
            run.id, lease_row.id, db, actor
        )
        assert restored["replayed"] is True
        assert requested[-1] == expected
        final = yardi.get_yardi_reconciliation(run.id, Response(), db, actor)
        assert final["lease_relationship_readiness"]["identity_source_id_collisions"] == 0
        assert final["lease_relationship_readiness"]["source_review_ready"] == 1
        assert final["customer_business_mutation"] is False

        db.refresh(prop)
        db.refresh(unit)
        db.refresh(tenant)
        db.refresh(lease_row)
        assert prop.name == "Original"
        assert unit.property_id == prop.id
        assert tenant.hashed_password == "unchanged-password-hash"
        assert lease_row.resolution_action == "ACCEPT_RELATIONSHIP"
        assert db.query(Lease).count() == before_leases
    finally:
        db.close()
        engine.dispose()
