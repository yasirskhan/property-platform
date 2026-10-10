"""Yardi resident identity staging is review-only and replay-safe."""
from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.user import User
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _session, _org, _platform_user


def test_residents_staged_without_login_or_lease_creation():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-resident-stage")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="yardi-resident-source", status="DRAFT",
        )
        db.add(run)
        db.commit()
        original_users = db.query(User).count()
        file_content = b"Resident Ref,Resident Name\nR-1,First Resident\nR-1,Duplicate Resident\n"
        mapping = {"source_id": "Resident Ref", "name": "Resident Name"}
        result = stage_yardi_file(
            db, run=run, filename="residents.csv",
            content=file_content, resource_override="TENANTS",
            sheet_name=None, explicit_mapping=mapping,
            platform_user_id=actor.id,
        )
        assert result.upload.provider == "YARDI"
        assert result.upload.detected_resource == "TENANTS"
        assert result.upload.validation_summary["duplicates"] == 1
        rows = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == result.upload.id
        ).order_by(PlatformMigrationStagedRow.row_number).all()
        assert rows[0].disposition == "REVIEW"
        assert "no user login" in rows[0].warnings[0]
        assert rows[1].disposition == "INVALID"
        assert db.query(User).count() == original_users
        again = stage_yardi_file(
            db, run=run, filename="residents.csv",
            content=file_content, resource_override="TENANTS",
            sheet_name=None, explicit_mapping=mapping,
            platform_user_id=actor.id,
        )
        assert again.replayed and again.upload.id == result.upload.id
        assert db.query(User).count() == original_users
    finally:
        db.close()
        engine.dispose()
