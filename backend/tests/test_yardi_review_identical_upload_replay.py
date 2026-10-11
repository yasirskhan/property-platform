"""An identical Yardi source replay leaves verified dry-run evidence intact."""
from fastapi import Response
from app.models.platform_migration import PlatformMigrationRun
from app.models.platform_user import PlatformUserRole
from app.routers.yardi_migrations import dry_run_yardi_review, get_yardi_review_dry_run_status
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _session, _org, _platform_user


def test_reupload_identical_yardi_source_preserves_review_snapshot():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-snapshot-replay")
        run = PlatformMigrationRun(organization_id=org.id, provider="YARDI",
                                   source_account_ref="stable-replay", status="DRAFT")
        db.add(run)
        db.commit()
        args = dict(db=db, run=run, filename="owners.csv",
                    content=b"ID,Name\nO-1,Example\n",
                    resource_override="OWNERS", sheet_name=None,
                    explicit_mapping={"source_id": "ID", "name": "Name"},
                    platform_user_id=actor.id)
        original = stage_yardi_file(**args)
        db.commit()
        snapshot = dry_run_yardi_review(run.id, db, actor)
        replay = stage_yardi_file(**args)
        assert replay.replayed and replay.upload.id == original.upload.id
        db.commit()
        current = get_yardi_review_dry_run_status(run.id, Response(), db, actor)
        assert current["is_current"] is True
        assert current["current_review_fingerprint"] == snapshot["review_fingerprint"]
        assert current["controlled_commit_enabled"] is False
    finally:
        db.close()
        engine.dispose()
