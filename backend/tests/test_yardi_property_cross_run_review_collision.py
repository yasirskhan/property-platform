"""A target reviewed in one Yardi run cannot be claimed in another run."""
import pytest
from fastapi import HTTPException
from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.property import Property
from app.routers.yardi_migrations import match_yardi_staged_property, YardiPropertyMatchIn
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _org, _platform_user, _session


def test_cross_run_review_claim_rejected_without_target_mutation():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-review-other-run")
        target = Property(organization_id=org.id, name="Target",
            address_line1="1 Main", city="Cleveland", state="OH", zip_code="44113")
        first = PlatformMigrationRun(organization_id=org.id, provider="YARDI",
            source_account_ref="first", status="DRAFT")
        second = PlatformMigrationRun(organization_id=org.id, provider="YARDI",
            source_account_ref="second", status="DRAFT")
        db.add_all([target, first, second])
        db.commit()
        mapping = {"source_id": "ID", "name": "Name", "address_line1": "Street",
            "city": "City", "state": "State", "zip_code": "Zip"}
        rows = []
        for run, source_id in [(first, "OLD"), (second, "NEW")]:
            uploaded = stage_yardi_file(db, run=run, filename="properties.csv",
                content=("ID,Name,Street,City,State,Zip\n" +
                    source_id + ",Different,2 Main,Cleveland,OH,44113\n").encode(),
                resource_override="PROPERTIES", sheet_name=None,
                explicit_mapping=mapping, platform_user_id=actor.id)
            db.commit()
            rows.append(db.query(PlatformMigrationStagedRow).filter(
                PlatformMigrationStagedRow.upload_id == uploaded.upload.id).one())
        first_result = match_yardi_staged_property(first.id, rows[0].id,
            YardiPropertyMatchIn(target_property_id=target.id), db, actor)
        assert first_result["replayed"] is False
        with pytest.raises(HTTPException) as exc:
            match_yardi_staged_property(second.id, rows[1].id,
                YardiPropertyMatchIn(target_property_id=target.id), db, actor)
        assert exc.value.status_code == 409
        db.refresh(rows[1])
        assert rows[1].resolution_action is None
        db.refresh(target)
        assert target.name == "Target"
    finally:
        db.close()
        engine.dispose()
