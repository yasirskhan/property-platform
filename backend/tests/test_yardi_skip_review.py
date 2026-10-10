"""Yardi skip decisions are provider-scoped, idempotent and nonmutating."""
from fastapi import HTTPException, Response
import pytest

from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.user import User
from app.routers.yardi_migrations import (
    YardiRowSkipIn, get_yardi_reconciliation, skip_yardi_staged_row,
)
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _session, _org, _platform_user


def test_yardi_skip_updates_review_evidence_and_fingerprint_without_customer_mutation():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-review-skip")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="review-skip", status="DRAFT",
        )
        db.add(run)
        db.commit()
        staged = stage_yardi_file(
            db, run=run, filename="owners.csv",
            content=b"Owner ID,Owner Name\nO-1,One Owner\n",
            resource_override="OWNERS", sheet_name=None,
            explicit_mapping={"source_id": "Owner ID", "name": "Owner Name"},
            platform_user_id=actor.id,
        )
        db.commit()
        row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == staged.upload.id,
        ).one()
        before_users = db.query(User).count()
        old = get_yardi_reconciliation(run.id, Response(), db, actor)
        payload = YardiRowSkipIn(reason_code="NOT_IN_SCOPE")
        first = skip_yardi_staged_row(run.id, row.id, payload, db, actor)
        assert first["action"] == "SKIP" and first["replayed"] is False
        next_review = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert old["review_fingerprint"] != next_review["review_fingerprint"]
        assert db.query(User).count() == before_users
        again = skip_yardi_staged_row(run.id, row.id, payload, db, actor)
        assert again["replayed"] is True
        with pytest.raises(HTTPException) as err:
            skip_yardi_staged_row(run.id + 10000, row.id, payload, db, actor)
        assert err.value.status_code == 404
    finally:
        db.close()
        engine.dispose()
