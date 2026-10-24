"""Yardi reviewed properties may not claim the same target twice in one run."""
import pytest
from fastapi import HTTPException
from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.property import Property
from app.routers.yardi_migrations import YardiPropertyMatchIn, match_yardi_staged_property
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _org, _platform_user, _session


def test_two_sources_cannot_claim_same_property_target():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-collision-target")
        target = Property(
            organization_id=org.id, name="Target House",
            address_line1="1 Main St", city="Cleveland", state="OH",
            zip_code="44113",
        )
        db.add(target)
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="review-collision", status="DRAFT",
        )
        db.add(run)
        db.commit()
        result = stage_yardi_file(
            db, run=run, filename="properties.csv",
            content=b"ID,Name,Street,City,State,Zip\nP-1,Target House,1 Main St,Cleveland,OH,44113\nP-2,Other House,2 Main St,Cleveland,OH,44113\n",
            resource_override="PROPERTIES", sheet_name=None,
            explicit_mapping={
                "source_id": "ID", "name": "Name", "address_line1": "Street",
                "city": "City", "state": "State", "zip_code": "Zip",
            }, platform_user_id=actor.id,
        )
        db.commit()
        rows = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == result.upload.id,
        ).order_by(PlatformMigrationStagedRow.row_number).all()
        assert len(rows) == 2
        match_yardi_staged_property(
            run.id, rows[0].id, YardiPropertyMatchIn(target_property_id=target.id),
            db, actor,
        )
        with pytest.raises(HTTPException) as error:
            match_yardi_staged_property(
                run.id, rows[1].id, YardiPropertyMatchIn(target_property_id=target.id),
                db, actor,
            )
        assert error.value.status_code == 409
        db.refresh(rows[1])
        assert rows[1].resolution_action is None
        db.refresh(target)
        assert target.name == "Target House"
    finally:
        db.close()
        engine.dispose()
