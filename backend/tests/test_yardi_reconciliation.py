"""Yardi reconciliation is strictly read-only and scoped to the Yardi run."""
from fastapi import Response
from app.models.platform_migration import PlatformMigrationRun
from app.models.platform_user import PlatformUserRole
from app.routers.yardi_migrations import get_yardi_reconciliation
from test_yardi_migrations import _session, _org, _platform_user


def test_yardi_empty_reconciliation_is_stable_and_not_committable():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-reconciliation")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="reconcile", status="DRAFT",
        )
        db.add(run)
        db.commit()
        response = Response()
        result = get_yardi_reconciliation(run.id, response, db, actor)
        repeat = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert result["provider"] == "YARDI"
        assert result["staged_rows"] == 0
        assert result["durable_mapping_count"] == 0
        assert result["unresolved_rows"] == 0
        assert result["review_fingerprint"] == repeat["review_fingerprint"]
        assert result["controlled_commit_enabled"] is False
        assert result["customer_business_mutation"] is False
        assert response.headers["cache-control"] == "no-store"
    finally:
        db.close()
        engine.dispose()
