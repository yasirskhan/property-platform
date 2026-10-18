"""Read-only, fingerprint-bound DoorLoop quality preview regressions."""
import asyncio
import hashlib
import json
from io import BytesIO

import pytest
from fastapi import HTTPException, Response, UploadFile

from app.models.platform_migration import (
    PlatformMigrationRun, PlatformMigrationUpload, PlatformMigrationStagedRow,
)
from app.models.platform_user import PlatformUserRole
from app.models.property import Property
from app.routers.doorloop_migrations import create_doorloop_run, preview_doorloop_source_quality
from app.schemas.doorloop_migration import DoorLoopRunCreateIn
from test_yardi_migrations import _session, _org, _platform_user


def _quality(run_id, db, actor, raw, mapping, digest=None, identity="external_id"):
    response = Response()
    value = asyncio.run(preview_doorloop_source_quality(
        run_id, response,
        UploadFile(filename="test.csv", file=BytesIO(raw)),
        None, json.dumps(mapping),
        digest if digest is not None else hashlib.sha256(raw).hexdigest(),
        identity, db, actor,
    ))
    return value, response


def test_doorloop_quality_preview_reports_aggregates_but_never_mutates():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "doorloop-quality")
        run = create_doorloop_run(DoorLoopRunCreateIn(
            organization_id=org.id, source_account_ref="export",
        ), db, admin)
        raw = b"External ID,Label\nID-1,Alpha\nID-1,\nID-2,Beta\n"
        result, response = _quality(
            run.id, db, admin, raw, {"external_id": "External ID", "label": "Label"},
        )
        assert result["provider"] == "DOORLOOP"
        assert result["source_file_sha256"] == hashlib.sha256(raw).hexdigest()
        assert result["total_rows"] == 3
        assert result["missing_values_by_proposed_field"] == {
            "external_id": 0, "label": 1,
        }
        assert result["duplicate_nonempty_identity_rows"] == 1
        assert result["identity_field_evaluated"] == "external_id"
        assert result["rows_returned"] is False
        assert result["source_contract_verified"] is False
        assert result["mapping_authorized"] is False
        assert result["mapping_stored"] is False
        assert result["can_stage_import"] is False
        assert result["can_commit_import"] is False
        assert result["customer_business_mutation"] is False
        assert response.headers["cache-control"] == "no-store"
        assert db.query(PlatformMigrationUpload).count() == 0
        assert db.query(PlatformMigrationStagedRow).count() == 0
        assert db.query(Property).count() == 0
        db.refresh(run)
        assert run.status == "DRAFT"
    finally:
        db.close()
        engine.dispose()


def test_doorloop_quality_requires_exact_file_and_authorized_provider():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        org = _org(db, "doorloop-quality-security")
        run = create_doorloop_run(DoorLoopRunCreateIn(
            organization_id=org.id, source_account_ref="export",
        ), db, admin)
        other = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="foreign", status="DRAFT",
        )
        db.add(other)
        db.commit()
        raw = b"External ID,Label\nA,One\n"
        mapping = {"external_id": "External ID"}
        with pytest.raises(HTTPException) as changed:
            _quality(run.id, db, admin, raw, mapping, digest="0" * 64)
        assert changed.value.status_code == 409
        with pytest.raises(HTTPException) as no_access:
            _quality(run.id, db, support, raw, mapping)
        assert no_access.value.status_code == 403
        with pytest.raises(HTTPException) as foreign:
            _quality(other.id, db, admin, raw, mapping)
        assert foreign.value.status_code == 404
        assert db.query(PlatformMigrationUpload).count() == 0
        assert db.query(PlatformMigrationStagedRow).count() == 0
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize("mapping,identity", [
    ({"external_id": "Not in export"}, "external_id"),
    ({"token": "External ID"}, "token"),
    ({"a": "External ID", "b": "External ID"}, "a"),
    ({}, "external_id"),
    ({"external_id": "External ID"}, "missing_field"),
])
def test_doorloop_quality_rejects_unsafe_or_ambiguous_mappings(mapping, identity):
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "doorloop-quality-rejected")
        run = create_doorloop_run(DoorLoopRunCreateIn(
            organization_id=org.id, source_account_ref="export",
        ), db, admin)
        with pytest.raises(HTTPException) as rejected:
            _quality(run.id, db, admin, b"External ID,Label\nA,One\n", mapping, identity=identity)
        assert rejected.value.status_code == 422
        assert db.query(PlatformMigrationUpload).count() == 0
    finally:
        db.close()
        engine.dispose()
