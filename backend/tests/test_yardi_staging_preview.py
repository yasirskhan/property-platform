"""Yardi staging preview is read-only and requires a provider-scoped run."""
from fastapi import Response
from app.models.platform_migration import PlatformMigrationRun
from app.models.platform_user import PlatformUserRole
from app.routers.yardi_migrations import preview_yardi_staging
from test_yardi_migrations import _session, _org, _platform_user


def test_empty_yardi_preview_has_stable_fingerprint_and_no_commit():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-preview")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="preview", status="DRAFT",
        )
        db.add(run)
        db.commit()
        response = Response()
        one = preview_yardi_staging(run.id, response, db, actor)
        two = preview_yardi_staging(run.id, Response(), db, actor)
        assert one["provider"] == "YARDI"
        assert one["upload_count"] == 0
        assert one["staged_row_count"] == 0
        assert one["preview_fingerprint"] == two["preview_fingerprint"]
        assert one["controlled_commit_enabled"] is False
        assert one["customer_business_mutation"] is False
        assert response.headers["cache-control"] == "no-store"
    finally:
        db.close()
        engine.dispose()
