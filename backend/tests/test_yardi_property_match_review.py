"""Explicit Yardi property matching is scoped and does not overwrite targets."""
import pytest
from fastapi import HTTPException

from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.property import Property
from app.routers.yardi_migrations import YardiPropertyMatchIn, match_yardi_staged_property
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _org, _platform_user, _session


def test_yardi_property_match_requires_same_org_and_is_idempotent():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-match-target")
        another_org = _org(db, "yardi-match-other")
        property_values = dict(
            name="Target House", address_line1="1 Main St",
            city="Cleveland", state="OH", zip_code="44113",
        )
        target = Property(organization_id=org.id, **property_values)
        foreign = Property(organization_id=another_org.id, **property_values)
        db.add_all([target, foreign])
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="review-match", status="DRAFT",
        )
        db.add(run)
        db.commit()
        result = stage_yardi_file(
            db, run=run, filename="properties.csv",
            content=b"ID,Name,Street,City,State,Zip\nP-1,Target House,1 Main St,Cleveland,OH,44113\n",
            resource_override="PROPERTIES", sheet_name=None,
            explicit_mapping={
                "source_id": "ID", "name": "Name", "address_line1": "Street",
                "city": "City", "state": "State", "zip_code": "Zip",
            }, platform_user_id=actor.id,
        )
        db.commit()
        row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == result.upload.id,
        ).one()
        with pytest.raises(HTTPException) as error:
            match_yardi_staged_property(
                run.id, row.id, YardiPropertyMatchIn(target_property_id=foreign.id),
                db, actor,
            )
        assert error.value.status_code == 404
        first = match_yardi_staged_property(
            run.id, row.id, YardiPropertyMatchIn(target_property_id=target.id),
            db, actor,
        )
        assert first["replayed"] is False
        replay = match_yardi_staged_property(
            run.id, row.id, YardiPropertyMatchIn(target_property_id=target.id),
            db, actor,
        )
        assert replay["replayed"] is True
        db.refresh(target)
        assert target.name == "Target House"
        assert row.resolution_action == "MATCH_EXISTING"
        assert run.last_dry_run_fingerprint is None
    finally:
        db.close()
        engine.dispose()
