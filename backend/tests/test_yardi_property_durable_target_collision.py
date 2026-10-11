"""Yardi property match rejects a target claimed by another durable source mapping."""
import pytest
from fastapi import HTTPException
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.property import Property
from app.routers.yardi_migrations import match_yardi_staged_property, YardiPropertyMatchIn
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _org, _platform_user, _session


def test_property_match_cannot_claim_durably_mapped_target_of_other_source():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-existing-mapped-target")
        target = Property(organization_id=org.id, name="Existing Property",
            address_line1="1 Main", city="Cleveland", state="OH", zip_code="44113")
        run = PlatformMigrationRun(organization_id=org.id, provider="YARDI",
            source_account_ref="yardi-existing-source", status="DRAFT")
        db.add_all([target, run])
        db.flush()
        db.add(PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="YARDI",
            resource="PROPERTIES", source_id="P-old", target_entity="PROPERTY",
            target_id=target.id, source_fingerprint="a" * 64,
            created_by_platform_user_id=actor.id,
        ))
        db.commit()
        upload = stage_yardi_file(db, run=run, filename="properties.csv",
            content=b"ID,Name,Street,City,State,Zip\nP-new,Another,2 Main,Cleveland,OH,44113\n",
            resource_override="PROPERTIES", sheet_name=None,
            explicit_mapping={"source_id":"ID", "name":"Name", "address_line1":"Street",
                "city":"City", "state":"State", "zip_code":"Zip"},
            platform_user_id=actor.id)
        db.commit()
        row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id).one()
        with pytest.raises(HTTPException) as error:
            match_yardi_staged_property(run.id, row.id,
                YardiPropertyMatchIn(target_property_id=target.id), db, actor)
        assert error.value.status_code == 409
        db.refresh(row)
        assert row.resolution_action is None
        db.refresh(target)
        assert target.name == "Existing Property"
    finally:
        db.close()
        engine.dispose()
