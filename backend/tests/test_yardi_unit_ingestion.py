"""Yardi Units source-id and dependency staging regressions."""
from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.property import Unit
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _org, _platform_user, _session


def test_yardi_units_missing_verified_parent_remains_review_only():
    db, engine = _session()
    try:
        user = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-unit-stage")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="yardi-unit-source", status="DRAFT",
            created_by_platform_user_id=user.id,
        )
        db.add(run)
        db.commit()
        prior_units = db.query(Unit).count()
        result = stage_yardi_file(
            db, run=run, filename="units.csv",
            content=b"Unit Ref,Property Ref,Unit Label\nU-1,P-1,Unit 1\nU-1,P-1,Unit 2\n",
            resource_override="UNITS", sheet_name=None,
            explicit_mapping={
                "source_id": "Unit Ref",
                "source_property_id": "Property Ref",
                "unit_name": "Unit Label",
            }, platform_user_id=user.id,
        )
        rows = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == result.upload.id
        ).order_by(PlatformMigrationStagedRow.row_number).all()
        assert result.upload.detected_resource == "UNITS"
        assert result.upload.provider == "YARDI"
        assert result.upload.validation_summary["duplicates"] == 1
        assert rows[0].disposition == "REVIEW"
        assert "relationship blocked" in rows[0].warnings[0]
        assert rows[1].disposition == "INVALID"
        assert db.query(Unit).count() == prior_units
        replay = stage_yardi_file(
            db, run=run, filename="units.csv",
            content=b"Unit Ref,Property Ref,Unit Label\nU-1,P-1,Unit 1\nU-1,P-1,Unit 2\n",
            resource_override="UNITS", sheet_name=None,
            explicit_mapping={
                "source_id": "Unit Ref",
                "source_property_id": "Property Ref",
                "unit_name": "Unit Label",
            }, platform_user_id=user.id,
        )
        assert replay.replayed and replay.upload.id == result.upload.id
    finally:
        db.close()
        engine.dispose()


def test_yardi_unit_match_requires_mapped_parent_and_preserves_customer_unit():
    import pytest
    from fastapi import HTTPException
    from app.models.property import Property
    from app.models.platform_migration import PlatformMigrationItem
    from app.routers.yardi_migrations import match_yardi_staged_unit, YardiUnitMatchIn

    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-unit-reviewed")
        property_row = Property(
            organization_id=org.id, name="Existing", address_line1="1 Main",
            city="Cleveland", state="OH", zip_code="44113",
        )
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="yardi-unit-review", status="DRAFT",
        )
        db.add_all([property_row, run])
        db.flush()
        target = Unit(property_id=property_row.id, unit_number="101")
        db.add(target)
        db.commit()
        upload = stage_yardi_file(
            db, run=run, filename="units.csv",
            content=b"ID,Parent,Label\\nU-1,P-1,101\\n",
            resource_override="UNITS", sheet_name=None,
            explicit_mapping={
                "source_id": "ID", "source_property_id": "Parent",
                "unit_name": "Label",
            }, platform_user_id=actor.id,
        )
        db.commit()
        row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id,
        ).one()
        with pytest.raises(HTTPException) as missing:
            match_yardi_staged_unit(
                run.id, row.id, YardiUnitMatchIn(target_unit_id=target.id), db, actor,
            )
        assert missing.value.status_code == 409
        db.add(PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="YARDI",
            resource="PROPERTIES", source_id="P-1",
            target_entity="PROPERTY", target_id=property_row.id,
            source_fingerprint="verified-property-fingerprint",
        ))
        db.commit()
        reviewed = match_yardi_staged_unit(
            run.id, row.id, YardiUnitMatchIn(target_unit_id=target.id), db, actor,
        )
        assert reviewed["action"] == "MATCH_EXISTING"
        assert reviewed["replayed"] is False
        assert match_yardi_staged_unit(
            run.id, row.id, YardiUnitMatchIn(target_unit_id=target.id), db, actor,
        )["replayed"] is True
        db.refresh(target)
        assert target.unit_number == "101"
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "UNITS",
        ).count() == 0
    finally:
        db.close()
        engine.dispose()
