"""Explicit Yardi property matching is scoped and does not overwrite targets."""
import pytest
from fastapi import HTTPException, Response

from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.property import Property
from app.routers.yardi_migrations import YardiPropertyMatchIn, match_yardi_staged_property, get_yardi_reconciliation
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
        before_review = get_yardi_reconciliation(run.id, Response(), db, actor)
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
        after_review = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert before_review["review_fingerprint"] != after_review["review_fingerprint"]
        assert after_review["resource_coverage"]["PROPERTIES"]["matched_existing"] == 1
        assert after_review["unresolved_rows"] == 0
        db.refresh(target)
        assert target.name == "Target House"
        assert row.resolution_action == "MATCH_EXISTING"
        assert run.last_dry_run_fingerprint is None

        target.is_active = False
        db.commit()
        inactive = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert inactive["resource_coverage"]["PROPERTIES"]["matched_existing"] == 0
        assert inactive["resource_coverage"]["PROPERTIES"]["needs_review"] == 1
        target.is_active = True
        target.deleted_at = __import__("datetime").datetime.utcnow()
        db.commit()
        archived = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert archived["resource_coverage"]["PROPERTIES"]["matched_existing"] == 0
        assert archived["resource_coverage"]["PROPERTIES"]["needs_review"] == 1
        assert archived["review_fingerprint"] != after_review["review_fingerprint"]
        db.refresh(row)
        db.refresh(target)
        assert row.resolution_action == "MATCH_EXISTING"
        assert target.name == "Target House"
    finally:
        db.close()
        engine.dispose()


def test_yardi_invalid_reviewed_property_is_not_counted_as_valid_matched_source():
    """Invalid source evidence outranks a historical MATCH_EXISTING decision."""
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-invalid-reviewed-property-coverage")
        prop = Property(
            organization_id=org.id, name="Original Property",
            address_line1="1 Main", city="Cleveland", state="OH", zip_code="44113",
        )
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="invalid-review-coverage", status="DRAFT",
        )
        db.add_all([prop, run])
        db.commit()
        upload = stage_yardi_file(
            db, run=run, filename="properties.csv",
            content=b"ID,Name,Street,City,State,Zip\nP-1,Original Property,1 Main,Cleveland,OH,44113\n",
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
        match_yardi_staged_property(
            run.id, row.id, YardiPropertyMatchIn(target_property_id=prop.id),
            db, actor,
        )
        good = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert good["resource_coverage"]["PROPERTIES"]["matched_existing"] == 1
        row.disposition = "INVALID"
        db.commit()
        invalid = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert invalid["resource_coverage"]["PROPERTIES"]["matched_existing"] == 0
        assert invalid["resource_coverage"]["PROPERTIES"]["invalid"] == 1
        assert invalid["invalid_rows"] == 1
        assert invalid["review_fingerprint"] != good["review_fingerprint"]
        db.refresh(row)
        db.refresh(prop)
        assert row.resolution_action == "MATCH_EXISTING"
        assert prop.name == "Original Property"
    finally:
        db.close()
        engine.dispose()
