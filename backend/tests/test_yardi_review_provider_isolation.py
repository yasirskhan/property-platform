"""Yardi review dry-run rejects foreign provider runs without mutation."""
import pytest
from fastapi import HTTPException, Response

from app.models.platform_migration import PlatformMigrationRun
from app.models.platform_user import PlatformUserRole
from app.routers.yardi_migrations import (
    dry_run_yardi_review, get_yardi_review_dry_run_status,
)
from test_yardi_migrations import _org, _platform_user, _session


def test_foreign_provider_cannot_read_or_record_yardi_review_snapshot():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-review-provider-isolation")
        foreign = PlatformMigrationRun(
            organization_id=org.id, provider="APPFOLIO",
            source_account_ref="not-yardi", status="DRAFT",
        )
        db.add(foreign)
        db.commit()
        for operation in (
            lambda: dry_run_yardi_review(foreign.id, db, actor),
            lambda: get_yardi_review_dry_run_status(
                foreign.id, Response(), db, actor,
            ),
        ):
            with pytest.raises(HTTPException) as error:
                operation()
            assert error.value.status_code == 404
        db.refresh(foreign)
        assert foreign.last_dry_run_fingerprint is None
        assert foreign.last_dry_run_summary is None
    finally:
        db.close()
        engine.dispose()
