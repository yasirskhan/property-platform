"""Yardi staged upload review access contract."""
import pytest
from fastapi import HTTPException, Response
from app.models.platform_migration import PlatformMigrationUpload, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.routers import yardi_migrations as api
from test_yardi_migrations import _session, _org, _platform_user


def test_yardi_rows_are_scoped_to_matching_upload_and_run():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        org = _org(db, "yardi-row-review")
        run = api.create_yardi_run(
            api.YardiMigrationRunCreateIn(
                organization_id=org.id, source_account_ref="source-1",
            ), db=db, current_user=admin,
        )
        upload = PlatformMigrationUpload(
            run_id=run.id, organization_id=org.id, provider="YARDI",
            filename="file.csv", file_format="CSV",
            file_sha256="a" * 64, normalized_fingerprint="b" * 64,
            detected_resource="PROPERTIES", sheet_name="CSV",
            headers=["Property ID"], column_mapping={"source_id": "Property ID"},
            validation_summary={}, status="REVIEW_REQUIRED", row_count=1,
        )
        db.add(upload)
        db.flush()
        db.add(PlatformMigrationStagedRow(
            upload_id=upload.id, run_id=run.id, organization_id=org.id,
            provider="YARDI", resource="PROPERTIES", row_number=2,
            source_id="p-1", disposition="REVIEW",
            row_fingerprint="c" * 64,
            normalized_data={"source_id": "p-1"}, warnings=[], errors=[],
        ))
        db.commit()
        response = Response()
        rows = api.list_yardi_staged_rows(
            run.id, upload.id, response, offset=0, limit=200,
            db=db, current_user=support,
        )
        assert [r.source_id for r in rows] == ["p-1"]
        assert response.headers["Cache-Control"] == "no-store"
        with pytest.raises(HTTPException) as exc:
            api.list_yardi_staged_rows(
                run.id, upload.id + 1000, Response(), offset=0, limit=200,
                db=db, current_user=support,
            )
        assert exc.value.status_code == 404
        upload.provider = "APPFOLIO"
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.list_yardi_staged_rows(
                run.id, upload.id, Response(), offset=0, limit=200,
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 404
    finally:
        db.close()
        engine.dispose()
