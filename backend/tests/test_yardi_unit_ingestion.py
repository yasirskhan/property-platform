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
