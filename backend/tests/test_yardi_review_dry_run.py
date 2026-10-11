"""A Yardi dry run records review metadata only, never customer data."""
from fastapi import HTTPException
import pytest
from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.user import User
from app.routers.yardi_migrations import (
    dry_run_yardi_review, skip_yardi_staged_row, YardiRowSkipIn,
)
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _session, _org, _platform_user


def test_yardi_review_dry_run_replays_and_invalidates_on_skip():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-dry-run")
        run = PlatformMigrationRun(organization_id=org.id, provider="YARDI",
            source_account_ref="dry-run", status="DRAFT")
        db.add(run)
        db.commit()
        with pytest.raises(HTTPException) as empty:
            dry_run_yardi_review(run.id, db, actor)
        assert empty.value.status_code == 422
        before = db.query(User).count()
        upload = stage_yardi_file(db, run=run, filename="owners.csv",
            content=b"ID,Name\nO-1,Example Owner\n", resource_override="OWNERS",
            sheet_name=None, explicit_mapping={"source_id": "ID", "name": "Name"},
            platform_user_id=actor.id)
        db.commit()
        row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id).one()
        first = dry_run_yardi_review(run.id, db, actor)
        again = dry_run_yardi_review(run.id, db, actor)
        assert first["replayed"] is False and again["replayed"] is True
        assert first["unresolved_rows"] == 1
        assert first["customer_business_mutation"] is False
        assert first["controlled_commit_enabled"] is False
        skip_yardi_staged_row(run.id, row.id,
            YardiRowSkipIn(reason_code="NOT_IN_SCOPE"), db, actor)
        assert run.last_dry_run_fingerprint is None
        after = dry_run_yardi_review(run.id, db, actor)
        assert after["review_fingerprint"] != first["review_fingerprint"]
        assert after["unresolved_rows"] == 0 and after["skipped_rows"] == 1
        assert db.query(User).count() == before
    finally:
        db.close()
        engine.dispose()
