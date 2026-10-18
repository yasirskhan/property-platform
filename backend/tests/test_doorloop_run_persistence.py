"""DoorLoop durable run isolation and nonpersistent export inventory regressions.

These tests exercise actual SQLAlchemy persistence. The hosted workflow also
runs PostgreSQL migration validation; no customer data importer is authorized.
"""
import asyncio
import hashlib
import json
from io import BytesIO

import pytest
from fastapi import HTTPException, Response, UploadFile
from pydantic import ValidationError

from app.models.audit_log import AuditLog
from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationUpload, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.property import Property
from app.routers.doorloop_migrations import (
    create_doorloop_run, doorloop_run_source_readiness, get_doorloop_run,
    inspect_doorloop_source_headers, list_doorloop_runs,
)
from app.schemas.doorloop_migration import DoorLoopRunCreateIn
from test_yardi_migrations import _org, _platform_user, _session


def test_doorloop_run_persists_with_audit_and_exact_provider_isolation():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        org = _org(db, "doorloop-audit")
        other_org = _org(db, "doorloop-other")
        before_properties = db.query(Property).count()
        run = create_doorloop_run(
            DoorLoopRunCreateIn(organization_id=org.id, source_account_ref=" export-A "),
            db=db, user=admin,
        )
        assert run.provider == "DOORLOOP"
        assert run.status == "DRAFT"
        assert run.source_account_ref == "export-A"
        assert run.created_by_platform_user_id == admin.id
        db.expire_all()
        persisted = db.query(PlatformMigrationRun).filter_by(id=run.id).one()
        assert persisted.provider == "DOORLOOP"
        assert persisted.organization_id == org.id
        event = db.query(AuditLog).filter_by(
            action="doorloop_migration_run_created", entity_id=run.id,
        ).one()
        assert event.platform_user_id == admin.id
        assert event.organization_id == org.id
        audit = json.loads(event.new_value)
        assert audit["credentials_stored"] is False
        assert audit["customer_business_mutation"] is False
        assert "export-A" not in event.new_value
        assert db.query(Property).count() == before_properties

        db.add(PlatformMigrationRun(
            organization_id=other_org.id, provider="DOORLOOP",
            source_account_ref="other-org-run", status="DRAFT",
        ))
        for provider in ("YARDI", "APPFOLIO", "BUILDIUM", "RENTMANAGER"):
            db.add(PlatformMigrationRun(
                organization_id=org.id, provider=provider,
                source_account_ref="other-provider", status="DRAFT",
            ))
        db.commit()
        view = Response()
        result = list_doorloop_runs(view, org.id, 100, db, support)
        assert [item.id for item in result] == [run.id]
        assert view.headers["cache-control"] == "no-store"
        assert len(list_doorloop_runs(Response(), None, 100, db, support)) == 2
        assert len(list_doorloop_runs(Response(), None, 1, db, support)) == 1
        view = Response()
        assert get_doorloop_run(run.id, view, db, support).id == run.id
        assert view.headers["cache-control"] == "no-store"
        for foreign in db.query(PlatformMigrationRun).filter(
            PlatformMigrationRun.provider != "DOORLOOP",
        ).all():
            with pytest.raises(HTTPException) as wrong_provider:
                get_doorloop_run(foreign.id, Response(), db, admin)
            assert wrong_provider.value.status_code == 404
    finally:
        db.close()
        engine.dispose()


def test_doorloop_roles_inactive_org_and_secret_references_fail_closed():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        tech = _platform_user(db, PlatformUserRole.PLATFORM_TECH)
        dev = _platform_user(db, PlatformUserRole.PLATFORM_DEV)
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        sales = _platform_user(db, PlatformUserRole.PLATFORM_SALES)
        org = _org(db, "doorloop-inactive")
        run = create_doorloop_run(DoorLoopRunCreateIn(
            organization_id=org.id, source_account_ref="label",
        ), db, admin)
        for actor in (support, sales):
            with pytest.raises(HTTPException) as forbidden:
                create_doorloop_run(DoorLoopRunCreateIn(
                    organization_id=org.id, source_account_ref="safe",
                ), db, actor)
            assert forbidden.value.status_code == 403
        for actor in (tech, dev):
            assert get_doorloop_run(run.id, Response(), db, actor).id == run.id
        for secret in ("Bearer abc", '{"token":"opaque"}', "api_key=secret"):
            with pytest.raises(ValidationError):
                DoorLoopRunCreateIn(organization_id=org.id, source_account_ref=secret)
        with pytest.raises(ValidationError):
            DoorLoopRunCreateIn(organization_id=org.id, source_account_ref="ok", password="no")
        org.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as inactive_write:
            create_doorloop_run(DoorLoopRunCreateIn(
                organization_id=org.id, source_account_ref="new",
            ), db, admin)
        assert inactive_write.value.status_code == 404
        with pytest.raises(HTTPException) as inactive_read:
            get_doorloop_run(run.id, Response(), db, support)
        assert inactive_read.value.status_code == 404
        assert list_doorloop_runs(Response(), None, 100, db, support) == []
        with pytest.raises(HTTPException) as inactive_filter:
            list_doorloop_runs(Response(), org.id, 100, db, admin)
        assert inactive_filter.value.status_code == 404
        assert db.query(PlatformMigrationRun).filter_by(provider="DOORLOOP").count() == 1
        assert db.query(AuditLog).filter_by(action="doorloop_migration_run_created").count() == 1
    finally:
        db.close()
        engine.dispose()


def test_doorloop_source_readiness_and_export_inspection_do_not_stage_data():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        org = _org(db, "doorloop-source")
        valid = create_doorloop_run(DoorLoopRunCreateIn(
            organization_id=org.id, source_account_ref="customer-export",
        ), db, admin)
        yardi = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="other", status="DRAFT",
        )
        db.add(yardi)
        db.commit()
        response = Response()
        ready = doorloop_run_source_readiness(valid.id, response, db, support)
        assert ready["provider"] == "DOORLOOP"
        assert ready["source_inspection_enabled"] is True
        assert ready["file_staging_enabled"] is False
        assert ready["controlled_commit_enabled"] is False
        assert ready["customer_business_mutation"] is False
        assert response.headers["cache-control"] == "no-store"
        with pytest.raises(HTTPException) as other_provider:
            doorloop_run_source_readiness(yardi.id, Response(), db, admin)
        assert other_provider.value.status_code == 404

        content = b"External ID,Property Label\n123,Example Property\n"
        response = Response()
        found = asyncio.run(inspect_doorloop_source_headers(
            valid.id, response, UploadFile(filename="export.csv", file=BytesIO(content)),
            None, db, admin,
        ))
        assert response.headers["cache-control"] == "no-store"
        assert found["headers"] == ["External ID", "Property Label"]
        assert found["row_count"] == 1
        assert found["source_file_bytes"] == len(content)
        assert found["source_file_sha256"] == hashlib.sha256(content).hexdigest()
        assert found["column_inventory"] == [
            {"index": 0, "source_header": "External ID", "mapping_status": "UNMAPPED"},
            {"index": 1, "source_header": "Property Label", "mapping_status": "UNMAPPED"},
        ]
        assert found["suggested_target_fields"] == []
        assert found["source_contract_verified"] is False
        assert found["can_stage_import"] is False
        assert found["can_commit_import"] is False
        assert found["source_rows_returned"] is False
        assert found["raw_source_stored"] is False
        assert db.query(PlatformMigrationUpload).count() == 0
        assert db.query(PlatformMigrationStagedRow).count() == 0
        assert db.query(Property).count() == 0
        with pytest.raises(HTTPException) as support_denied:
            asyncio.run(inspect_doorloop_source_headers(
                valid.id, Response(),
                UploadFile(filename="export.csv", file=BytesIO(content)),
                None, db, support,
            ))
        assert support_denied.value.status_code == 403
        with pytest.raises(HTTPException) as wrong_provider:
            asyncio.run(inspect_doorloop_source_headers(
                yardi.id, Response(),
                UploadFile(filename="export.csv", file=BytesIO(content)),
                None, db, admin,
            ))
        assert wrong_provider.value.status_code == 404
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize("name,data", [
    ("bad.csv", b"Name,name\nA,B\n"),
    ("credentials.csv", b"API Key,Name\nabc,Property\n"),
    ("macro.xlsm", b"not an actual spreadsheet"),
])
def test_doorloop_inspection_rejects_unsafe_source_files(name, data):
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "doorloop-invalid-source")
        run = create_doorloop_run(DoorLoopRunCreateIn(
            organization_id=org.id, source_account_ref="nonsecret",
        ), db, admin)
        with pytest.raises(HTTPException) as invalid:
            asyncio.run(inspect_doorloop_source_headers(
                run.id, Response(), UploadFile(filename=name, file=BytesIO(data)),
                None, db, admin,
            ))
        assert invalid.value.status_code == 422
        assert db.query(PlatformMigrationUpload).count() == 0
        assert db.query(PlatformMigrationStagedRow).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_doorloop_postgresql_run_and_audit_round_trip():
    """Exercise the production PostgreSQL dialect when the CI DB is configured."""
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base
    from app.models.platform_user import PlatformUser
    from app.models.user import Organization, User

    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("Requires an explicitly configured PostgreSQL test database")
    engine = create_engine(url)
    # Create only the tables needed for this regression, keeping unrelated
    # customer migrations and business data entirely outside its scope.
    Base.metadata.create_all(bind=engine, tables=[
        Organization.__table__, PlatformUser.__table__, User.__table__,
        PlatformMigrationRun.__table__, AuditLog.__table__,
    ])
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "doorloop-postgresql-creation")
        created = create_doorloop_run(
            DoorLoopRunCreateIn(organization_id=org.id, source_account_ref="pg-export"),
            db=db, user=admin,
        )
        saved_id = created.id
        db.close()
        # A separate SQLAlchemy session confirms the transaction is durable.
        verify = factory()
        try:
            saved = verify.query(PlatformMigrationRun).filter_by(id=saved_id).one()
            assert saved.provider == "DOORLOOP"
            assert saved.organization_id == org.id
            assert saved.status == "DRAFT"
            assert saved.source_account_ref == "pg-export"
            logged = verify.query(AuditLog).filter_by(
                entity_id=saved_id, action="doorloop_migration_run_created",
            ).one()
            assert logged.platform_user_id == admin.id
            assert json.loads(logged.new_value)["credentials_stored"] is False
            assert "pg-export" not in logged.new_value
        finally:
            verify.close()
    finally:
        db.close()
        engine.dispose()
