"""Current target checks for unreviewed Yardi durable identity reconciliation."""
from datetime import datetime

from fastapi import Response

from app.models.platform_migration import (
    PlatformMigrationItem, PlatformMigrationRun, PlatformMigrationStagedRow,
)
from app.models.platform_user import PlatformUserRole
from app.models.property import Property, Unit
from app.routers.yardi_migrations import get_yardi_reconciliation
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _org, _platform_user, _session


def test_unreviewed_exact_bindings_recheck_property_and_unit_target_and_parent():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-unreviewed-live-target")
        original = Property(
            organization_id=org.id, name="Original", address_line1="1 Main",
            city="Cleveland", state="OH", zip_code="44113",
        )
        alternate = Property(
            organization_id=org.id, name="Alternate", address_line1="2 Main",
            city="Cleveland", state="OH", zip_code="44113",
        )
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="unreviewed-live-target", status="DRAFT",
        )
        db.add_all([original, alternate, run])
        db.flush()
        unit = Unit(property_id=original.id, unit_number="101")
        db.add(unit)
        db.commit()

        property_upload = stage_yardi_file(
            db, run=run, filename="properties.csv",
            content=b"ID,Name,Street,City,State,Zip\nP1,Source,1 Main,Cleveland,OH,44113\n",
            resource_override="PROPERTIES", sheet_name=None,
            explicit_mapping={
                "source_id": "ID", "name": "Name", "address_line1": "Street",
                "city": "City", "state": "State", "zip_code": "Zip",
            }, platform_user_id=actor.id,
        )
        db.commit()
        property_row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == property_upload.upload.id,
        ).one()
        db.add(PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="YARDI",
            resource="PROPERTIES", source_id="P1", target_entity="PROPERTY",
            target_id=original.id, source_fingerprint=property_row.row_fingerprint,
        ))
        db.commit()
        unit_upload = stage_yardi_file(
            db, run=run, filename="units.csv",
            content=b"Unit,Parent,Label\nU1,P1,101\n",
            resource_override="UNITS", sheet_name=None,
            explicit_mapping={
                "source_id": "Unit", "source_property_id": "Parent",
                "unit_name": "Label",
            }, platform_user_id=actor.id,
        )
        db.commit()
        unit_row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == unit_upload.upload.id,
        ).one()
        db.add(PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="YARDI",
            resource="UNITS", source_id="U1", target_entity="UNIT",
            target_id=unit.id, source_fingerprint=unit_row.row_fingerprint,
        ))
        db.commit()
        ready = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert ready["resource_coverage"]["PROPERTIES"]["mapped"] == 1
        assert ready["resource_coverage"]["UNITS"]["mapped"] == 1
        assert property_row.resolution_action is None
        assert unit_row.resolution_action is None

        original.is_active = False
        db.commit()
        inactive_parent = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert inactive_parent["resource_coverage"]["PROPERTIES"]["mapped"] == 0
        assert inactive_parent["resource_coverage"]["UNITS"]["mapped"] == 0
        assert inactive_parent["review_fingerprint"] != ready["review_fingerprint"]
        original.is_active = True
        original.deleted_at = datetime.utcnow()
        db.commit()
        archived_parent = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert archived_parent["resource_coverage"]["PROPERTIES"]["mapped"] == 0
        assert archived_parent["resource_coverage"]["UNITS"]["mapped"] == 0
        original.deleted_at = None
        unit.is_active = False
        db.commit()
        inactive_unit = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert inactive_unit["resource_coverage"]["PROPERTIES"]["mapped"] == 1
        assert inactive_unit["resource_coverage"]["UNITS"]["mapped"] == 0
        unit.is_active = True
        unit.property_id = alternate.id
        db.commit()
        moved = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert moved["resource_coverage"]["UNITS"]["mapped"] == 0
        unit.property_id = original.id
        db.commit()
        restored = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert restored["resource_coverage"]["PROPERTIES"]["mapped"] == 1
        assert restored["resource_coverage"]["UNITS"]["mapped"] == 1
        assert restored["review_fingerprint"] == ready["review_fingerprint"]
        db.refresh(original)
        db.refresh(unit)
        assert original.name == "Original"
        assert unit.unit_number == "101"
        assert property_row.resolution_action is None
        assert unit_row.resolution_action is None
    finally:
        db.close()
        engine.dispose()
