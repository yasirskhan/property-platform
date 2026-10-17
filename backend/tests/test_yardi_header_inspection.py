"""Yardi staff source-header inspection must not store raw exports or mutate records."""
import asyncio
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile

from app.models.platform_migration import (
    PlatformMigrationRun, PlatformMigrationStagedRow, PlatformMigrationUpload,
)
from app.models.platform_user import PlatformUserRole
from app.models.property import Property
from app.routers.yardi_migrations import inspect_yardi_source_headers
from test_yardi_migrations import _org, _platform_user, _session


def _call(run_id, filename, data, session, actor, sheet=None):
    return asyncio.run(inspect_yardi_source_headers(
        run_id=run_id,
        file=UploadFile(filename=filename, file=BytesIO(data)),
        sheet_name=sheet, db=session, current_user=actor,
    ))


def test_header_inspection_is_bounded_nonmutating_and_exposes_no_source_rows():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-source-inspection")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="export-inspect", status="DRAFT",
        )
        db.add(run)
        db.commit()
        before = (
            db.query(Property).count(),
            db.query(PlatformMigrationUpload).count(),
            db.query(PlatformMigrationStagedRow).count(),
        )
        result = _call(run.id, "residents.csv",
                       b"Resident ID,Resident Name\nT-01,Alice\n", db, actor)
        assert result["provider"] == "YARDI"
        assert result["headers"] == ["Resident ID", "Resident Name"]
        assert result["row_count"] == 1
        assert result["file_format"] == "CSV"
        assert result["sheet_name"] == "CSV"
        for key in ("source_rows_returned", "raw_source_stored",
                    "staging_mutation", "customer_business_mutation"):
            assert result[key] is False
        assert "Alice" not in str(result)
        assert before == (
            db.query(Property).count(),
            db.query(PlatformMigrationUpload).count(),
            db.query(PlatformMigrationStagedRow).count(),
        )
        assert run.last_dry_run_fingerprint is None
    finally:
        db.close()
        engine.dispose()


def test_header_inspection_rejects_secret_columns_and_wrong_staff_role():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        org = _org(db, "yardi-inspect-guard")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="inspect-guard", status="DRAFT",
        )
        db.add(run)
        db.commit()
        with pytest.raises(HTTPException) as bad_header:
            _call(run.id, "secret.csv", b"ID,password\n1,test\n", db, admin)
        assert bad_header.value.status_code == 422
        with pytest.raises(HTTPException) as forbidden:
            _call(run.id, "residents.csv", b"ID,Name\n1,Alice\n", db, support)
        assert forbidden.value.status_code == 403
        assert db.query(PlatformMigrationUpload).count() == 0
        assert db.query(PlatformMigrationStagedRow).count() == 0
    finally:
        db.close()
        engine.dispose()
