"""New Yardi staging source invalidates previously recorded dry-run evidence."""
from fastapi import Response
from app.models.platform_migration import PlatformMigrationRun
from app.models.platform_user import PlatformUserRole
from app.routers.yardi_migrations import (
    dry_run_yardi_review, get_yardi_review_dry_run_status,
)
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _session, _org, _platform_user


def test_new_upload_revokes_prior_yardi_dry_run():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-stage-invalidation")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="invalidation", status="DRAFT",
        )
        db.add(run)
        db.commit()
        args = dict(
            db=db, run=run, filename="owners.csv",
            resource_override="OWNERS", sheet_name=None,
            explicit_mapping={"source_id": "ID", "name": "Name"},
            platform_user_id=actor.id,
        )
        stage_yardi_file(**args, content=b"ID,Name\nO-1,Original\n")
        db.commit()
        first = dry_run_yardi_review(run.id, db, actor)
        assert first["controlled_commit_enabled"] is False
        before = get_yardi_review_dry_run_status(run.id, Response(), db, actor)
        assert before["is_current"] is True
        stage_yardi_file(**args, content=b"ID,Name\nO-2,Second\n")
        db.commit()
        after = get_yardi_review_dry_run_status(run.id, Response(), db, actor)
        assert after["has_saved_dry_run"] is False
        assert after["is_current"] is False
        assert after["current_review_fingerprint"] != first["review_fingerprint"]
        assert after["controlled_commit_enabled"] is False
    finally:
        db.close()
        engine.dispose()
