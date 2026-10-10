"""Yardi lease occupancy staging must not create business records."""
from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.lease import Lease
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _session, _org, _platform_user


def test_lease_source_relationships_remain_review_only():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-lease-stage")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="yardi-lease-source", status="DRAFT",
        )
        db.add(run)
        db.commit()
        before = db.query(Lease).count()
        content = b"Lease Ref,Resident Ref,Property Ref,Unit Ref\nL-1,T-1,P-1,U-1\n"
        mapping = {
            "source_id": "Lease Ref",
            "source_tenant_id": "Resident Ref",
            "source_property_id": "Property Ref",
            "source_unit_id": "Unit Ref",
        }
        staged = stage_yardi_file(
            db, run=run, filename="leases.csv",
            content=content, resource_override="LEASE_OCCUPANCY",
            sheet_name=None, explicit_mapping=mapping,
            platform_user_id=actor.id,
        )
        row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == staged.upload.id
        ).one()
        assert row.provider == "YARDI"
        assert row.disposition == "REVIEW"
        assert sum("commit blocked" in warning for warning in row.warnings) == 3
        assert db.query(Lease).count() == before
        replay = stage_yardi_file(
            db, run=run, filename="leases.csv", content=content,
            resource_override="LEASE_OCCUPANCY", sheet_name=None,
            explicit_mapping=mapping, platform_user_id=actor.id,
        )
        assert replay.replayed and replay.upload.id == staged.upload.id
        assert db.query(Lease).count() == before
    finally:
        db.close()
        engine.dispose()
