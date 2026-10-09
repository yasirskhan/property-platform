"""Focused Phase 4.15 Yardi staging safety regressions."""
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest

from app.services.appfolio_file_ingestion import AppFolioFileIngestionError
from app.services.yardi_file_ingestion import stage_yardi_file


def _call(**overrides):
    args = dict(
        db=MagicMock(), run=SimpleNamespace(provider="YARDI", id=1, organization_id=1, source_account_ref="yardi-a"),
        filename="properties.csv", content=b"Property ID,Name\nP1,A\n",
        resource_override="PROPERTIES", sheet_name=None,
        explicit_mapping={"source_id": "Property ID", "name": "Name"},
        platform_user_id=1,
    )
    args.update(overrides)
    return stage_yardi_file(**args)


def test_reject_wrong_provider():
    with pytest.raises(AppFolioFileIngestionError, match="not a Yardi"):
        _call(run=SimpleNamespace(provider="APPFOLIO"))


def test_reject_unverified_resource():
    with pytest.raises(AppFolioFileIngestionError, match="PROPERTIES"):
        _call(resource_override="GENERAL_LEDGER")


def test_reject_unknown_source_header():
    with pytest.raises(AppFolioFileIngestionError, match="unknown source header"):
        _call(explicit_mapping={"source_id": "Imaginary"})


def test_reject_secret_column():
    with pytest.raises(AppFolioFileIngestionError):
        _call(content=b"Property ID,password\nP1,secret\n")


def test_duplicate_yardi_source_ids_stay_invalid_without_target_mutation():
    from test_yardi_migrations import _session, _org, _platform_user
    from app.models.platform_user import PlatformUserRole
    from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationStagedRow
    from app.models.property import Property
    db, engine = _session()
    try:
        user = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-duplicate-stage")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="yardi-test", status="DRAFT",
            created_by_platform_user_id=user.id,
        )
        db.add(run)
        db.commit()
        before = db.query(Property).count()
        content = ("Property ID,Name,Street,City,State,Zip\\n"
            "P-01,First,1 Main,Cleveland,OH,44113\\n"
            "P-01,Second,2 Main,Cleveland,OH,44113\\n"
        ).encode("utf-8")
        mapping = {
            "source_id": "Property ID", "name": "Name",
            "address_line1": "Street", "city": "City",
            "state": "State", "zip_code": "Zip",
        }
        result = stage_yardi_file(
            db, run=run, filename="properties.csv", content=content,
            resource_override="PROPERTIES", sheet_name=None,
            explicit_mapping=mapping, platform_user_id=user.id,
        )
        assert result.upload.provider == "YARDI"
        assert result.upload.status == "STAGED_WITH_ERRORS"
        assert result.upload.validation_summary["duplicates"] == 1
        rows = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == result.upload.id
        ).order_by(PlatformMigrationStagedRow.row_number).all()
        assert [r.source_id for r in rows] == ["P-01", "P-01"]
        assert rows[1].disposition == "INVALID"
        assert db.query(Property).count() == before
        replay = stage_yardi_file(
            db, run=run, filename="properties.csv", content=content,
            resource_override="PROPERTIES", sheet_name=None,
            explicit_mapping=mapping, platform_user_id=user.id,
        )
        assert replay.replayed is True
        assert replay.upload.id == result.upload.id
        assert db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == result.upload.id
        ).count() == 2
        assert db.query(Property).count() == before
    finally:
        db.close()
        engine.dispose()
