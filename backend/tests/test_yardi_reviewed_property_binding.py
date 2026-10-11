"""Yardi reviewed Property bindings create durable source maps, never Properties."""
import pytest
from fastapi import HTTPException
from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationItem, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.property import Property
from app.routers.yardi_migrations import (
    bind_yardi_reviewed_property_matches, dry_run_yardi_review,
    match_yardi_staged_property, YardiPropertyMatchIn,
    YardiReviewedPropertyBindingIn,
)
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _session, _org, _platform_user


def test_reviewed_property_match_binding_is_exact_and_replay_safe():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-property-binding")
        target = Property(
            organization_id=org.id, name="Original Property",
            address_line1="1 Main", city="Cleveland", state="OH",
            zip_code="44113",
        )
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="source-1", status="DRAFT",
        )
        db.add_all([target, run])
        db.commit()
        upload = stage_yardi_file(
            db, run=run, filename="properties.csv",
            content=b"ID,Name,Street,City,State,Zip\nY-01,Other Name,2 Main,Cleveland,OH,44113\n",
            resource_override="PROPERTIES", sheet_name=None,
            explicit_mapping={
                "source_id": "ID", "name": "Name",
                "address_line1": "Street", "city": "City",
                "state": "State", "zip_code": "Zip",
            }, platform_user_id=actor.id,
        )
        db.commit()
        row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id
        ).one()
        match_yardi_staged_property(
            run.id, row.id, YardiPropertyMatchIn(target_property_id=target.id),
            db, actor,
        )
        summary = dry_run_yardi_review(run.id, db, actor)
        request = YardiReviewedPropertyBindingIn(
            review_fingerprint=summary["review_fingerprint"],
        )
        with pytest.raises(HTTPException) as stale:
            bind_yardi_reviewed_property_matches(
                run.id,
                YardiReviewedPropertyBindingIn(review_fingerprint="0" * 64),
                db, actor,
            )
        assert stale.value.status_code == 409
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.provider == "YARDI",
        ).count() == 0
        db.refresh(target)
        assert target.name == "Original Property"
        first = bind_yardi_reviewed_property_matches(run.id, request, db, actor)
        assert first["bound"] == 1 and first["replayed"] is False
        mapped = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.provider == "YARDI",
            PlatformMigrationItem.resource == "PROPERTIES",
        ).one()
        assert mapped.source_id == "Y-01"
        assert mapped.target_id == target.id
        assert mapped.source_fingerprint == row.row_fingerprint
        again = bind_yardi_reviewed_property_matches(run.id, request, db, actor)
        assert again["replayed"] is True and again["bound"] == 0
        db.refresh(target)
        assert target.name == "Original Property"
        assert target.address_line1 == "1 Main"
    finally:
        db.close()
        engine.dispose()
