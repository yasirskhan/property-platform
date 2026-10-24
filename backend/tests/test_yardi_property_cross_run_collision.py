"""Reject matching a Property durably mapped in another Yardi run."""
import pytest
from fastapi import HTTPException
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.property import Property
from app.routers.yardi_migrations import match_yardi_staged_property, YardiPropertyMatchIn
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _org, _platform_user, _session


def test_yardi_property_target_cannot_be_claimed_across_runs():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-other-run-collision")
        target = Property(organization_id=org.id, name="Customer Property",
            address_line1="1 Main", city="Cleveland", state="OH", zip_code="44113")
        old_run = PlatformMigrationRun(organization_id=org.id, provider="YARDI",
            source_account_ref="yardi-prior", status="DRAFT")
        new_run = PlatformMigrationRun(organization_id=org.id, provider="YARDI",
            source_account_ref="yardi-later", status="DRAFT")
        db.add_all([target, old_run, new_run])
        db.flush()
        db.add(PlatformMigrationItem(
            run_id=old_run.id, organization_id=org.id, provider="YARDI",
            resource="PROPERTIES", source_id="OLD-1", target_entity="PROPERTY",
            target_id=target.id, source_fingerprint="a" * 64,
            created_by_platform_user_id=actor.id,
        ))
        db.commit()
        staged = stage_yardi_file(db, run=new_run, filename="properties.csv",
            content=b"ID,Name,Street,City,State,Zip\nNEW-1,New,2 Main,Cleveland,OH,44113\n",
            resource_override="PROPERTIES", sheet_name=None,
            explicit_mapping={"source_id":"ID","name":"Name","address_line1":"Street",
                "city":"City","state":"State","zip_code":"Zip"},
            platform_user_id=actor.id)
        db.commit()
        row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == staged.upload.id).one()
        with pytest.raises(HTTPException) as error:
            match_yardi_staged_property(new_run.id, row.id,
                YardiPropertyMatchIn(target_property_id=target.id), db, actor)
        assert error.value.status_code == 409
        db.refresh(row)
        assert row.resolution_action is None
        db.refresh(target)
        assert target.name == "Customer Property"
    finally:
        db.close()
        engine.dispose()
