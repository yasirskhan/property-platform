"""A reviewed Yardi source must not bind to a target already claimed by another run."""
import pytest
from fastapi import HTTPException

from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.property import Property
from app.routers.yardi_migrations import (
    YardiReviewedPropertyBindingIn, bind_yardi_reviewed_property_matches,
    dry_run_yardi_review,
)
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _org, _platform_user, _session


def test_binding_blocks_same_source_id_claimed_by_another_run():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-cross-run-bind")
        property_row = Property(
            organization_id=org.id, name="Property Original",
            address_line1="1 Main", city="Cleveland", state="OH", zip_code="44113",
        )
        runs = [PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref=f"source-{i}", status="DRAFT",
        ) for i in (1, 2)]
        db.add_all([property_row, *runs])
        db.commit()
        requests = []
        for run in runs:
            upload = stage_yardi_file(
                db, run=run, filename="properties.csv",
                content=b"ID,Name,Street,City,State,Zip\nY-01,Imported,2 Main,Cleveland,OH,44113\n",
                resource_override="PROPERTIES", sheet_name=None,
                explicit_mapping={
                    "source_id": "ID", "name": "Name", "address_line1": "Street",
                    "city": "City", "state": "State", "zip_code": "Zip",
                }, platform_user_id=actor.id,
            )
            db.commit()
            row = db.query(PlatformMigrationStagedRow).filter(
                PlatformMigrationStagedRow.upload_id == upload.upload.id,
            ).one()
            # Model the preexisting reviewed decision while both runs were staged.
            row.resolution_action = "MATCH_EXISTING"
            row.resolution_target_id = property_row.id
            db.commit()
            preview = dry_run_yardi_review(run.id, db, actor)
            requests.append(YardiReviewedPropertyBindingIn(
                review_fingerprint=preview["review_fingerprint"],
            ))
        first = bind_yardi_reviewed_property_matches(runs[0].id, requests[0], db, actor)
        assert first["bound"] == 1
        with pytest.raises(HTTPException) as conflict:
            bind_yardi_reviewed_property_matches(runs[1].id, requests[1], db, actor)
        assert conflict.value.status_code == 409
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == runs[1].id,
            PlatformMigrationItem.provider == "YARDI",
        ).count() == 0
        db.refresh(property_row)
        assert property_row.name == "Property Original"
    finally:
        db.close()
        engine.dispose()
