"""Yardi owner identity staging remains review-only."""
from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.user import User
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _session, _org, _platform_user


def test_owner_identity_staged_without_creating_users_or_ownership():
    db, engine = _session()
    try:
        user = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-owner-stage")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="yardi-owner-contract", status="DRAFT",
        )
        db.add(run)
        db.commit()
        before_users = db.query(User).count()
        content = b"Owner Ref,Owner Label\nOWN-1,First Owner\nOWN-1,Duplicate Owner\n"
        mapping = {"source_id": "Owner Ref", "name": "Owner Label"}
        result = stage_yardi_file(
            db, run=run, filename="owners.csv", content=content,
            resource_override="OWNERS", sheet_name=None,
            explicit_mapping=mapping, platform_user_id=user.id,
        )
        assert result.upload.provider == "YARDI"
        assert result.upload.detected_resource == "OWNERS"
        assert result.upload.validation_summary["duplicates"] == 1
        rows = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == result.upload.id,
        ).order_by(PlatformMigrationStagedRow.row_number).all()
        assert rows[0].disposition == "REVIEW"
        assert "no ownership" in rows[0].warnings[0]
        assert rows[1].disposition == "INVALID"
        assert db.query(User).count() == before_users
        again = stage_yardi_file(
            db, run=run, filename="owners.csv", content=content,
            resource_override="OWNERS", sheet_name=None,
            explicit_mapping=mapping, platform_user_id=user.id,
        )
        assert again.replayed and again.upload.id == result.upload.id
        assert db.query(User).count() == before_users
    finally:
        db.close()
        engine.dispose()
