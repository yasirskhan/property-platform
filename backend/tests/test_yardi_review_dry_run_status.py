"""Yardi dry-run status always compares against live review evidence."""
from fastapi import Response
from app.models.platform_migration import PlatformMigrationRun
from app.models.platform_user import PlatformUserRole
from app.routers.yardi_migrations import (
    get_yardi_reconciliation, get_yardi_review_dry_run_status,
)
from test_yardi_migrations import _session, _org, _platform_user


def test_yardi_dry_run_status_rejects_stale_and_missing_snapshots():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-snapshot-status")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="snapshot-status", status="DRAFT",
        )
        db.add(run)
        db.commit()
        response = Response()
        missing = get_yardi_review_dry_run_status(run.id, response, db, actor)
        assert missing["has_saved_dry_run"] is False
        assert missing["is_current"] is False
        missing_review = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert missing_review["saved_review_fingerprint"] is None
        assert missing_review["saved_review_current"] is False
        assert missing_review["review_fingerprint"] == missing["current_review_fingerprint"]
        assert response.headers["cache-control"] == "no-store"
        run.last_dry_run_fingerprint = missing["current_review_fingerprint"]
        db.commit()
        current = get_yardi_review_dry_run_status(run.id, Response(), db, actor)
        assert current["is_current"] is True
        current_review = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert current_review["saved_review_current"] is True
        assert current_review["saved_review_fingerprint"] == current_review["review_fingerprint"]
        run.last_dry_run_fingerprint = "0" * 64
        db.commit()
        stale = get_yardi_review_dry_run_status(run.id, Response(), db, actor)
        assert stale["has_saved_dry_run"] is True
        assert stale["is_current"] is False
        stale_review = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert stale_review["saved_review_fingerprint"] == "0" * 64
        assert stale_review["saved_review_current"] is False
        assert stale_review["review_fingerprint"] != stale_review["saved_review_fingerprint"]
        assert stale["controlled_commit_enabled"] is False
        assert stale["customer_business_mutation"] is False
    finally:
        db.close()
        engine.dispose()
