"""Phase 4.16 RentManager run scope and deny-by-default regressions."""
import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError

from app.models.platform_migration import PlatformMigrationRun
from app.models.platform_user import PlatformUserRole
from app.routers.rentmanager_migrations import (
    create_rentmanager_run, get_rentmanager_run, list_rentmanager_runs,
    get_rentmanager_resource_readiness,
)
from app.schemas.rentmanager_migration import RentManagerRunCreateIn
from test_yardi_migrations import _session, _org, _platform_user


def test_rentmanager_run_is_provider_scoped_and_audited_without_customer_mutation():
    from app.models.property import Property
    from app.models.audit_log import AuditLog
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "rentmanager-foundation-org")
        before = db.query(Property).count()
        result = create_rentmanager_run(
            RentManagerRunCreateIn(organization_id=org.id, source_account_ref="client-01"),
            db, admin,
        )
        assert result.provider == "RENTMANAGER"
        assert result.status == "DRAFT"
        response = Response()
        assert get_rentmanager_run(result.id, response, db, admin).id == result.id
        assert response.headers["cache-control"] == "no-store"
        rows_response = Response()
        rows = list_rentmanager_runs(rows_response, org.id, 100, db, admin)
        assert [row.id for row in rows] == [result.id]
        assert rows_response.headers["cache-control"] == "no-store"
        assert db.query(Property).count() == before
        assert db.query(AuditLog).filter(AuditLog.action == "rentmanager_migration_run_created").count() == 1
        db.add(PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="yardi-01", status="DRAFT",
        ))
        db.commit()
        with pytest.raises(HTTPException) as missing:
            get_rentmanager_run(db.query(PlatformMigrationRun).filter(
                PlatformMigrationRun.provider == "YARDI",
            ).one().id, Response(), db, admin)
        assert missing.value.status_code == 404
    finally:
        db.close()
        engine.dispose()


def test_rentmanager_denies_sales_and_secret_source_reference():
    db, engine = _session()
    try:
        sales = _platform_user(db, PlatformUserRole.PLATFORM_SALES)
        org = _org(db, "rentmanager-role-gate")
        with pytest.raises(HTTPException) as forbidden:
            create_rentmanager_run(
                RentManagerRunCreateIn(organization_id=org.id, source_account_ref="account"),
                db, sales,
            )
        assert forbidden.value.status_code == 403
        assert db.query(PlatformMigrationRun).count() == 0
        with pytest.raises(ValidationError):
            RentManagerRunCreateIn(organization_id=org.id, source_account_ref="Bearer secret")
        with pytest.raises(ValidationError):
            RentManagerRunCreateIn(organization_id=org.id, source_account_ref='{"raw":"value"}')
        with pytest.raises(ValidationError):
            RentManagerRunCreateIn(organization_id=org.id, source_account_ref="ok", password="forbidden")
    finally:
        db.close()
        engine.dispose()


def test_rentmanager_resource_readiness_blocks_unverified_transports():
    db, engine = _session()
    try:
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        sales = _platform_user(db, PlatformUserRole.PLATFORM_SALES)
        response = Response()
        readiness = get_rentmanager_resource_readiness(response, support)
        assert response.headers["cache-control"] == "no-store"
        assert readiness["provider"] == "RENTMANAGER"
        assert readiness["run_foundation_available"] is True
        assert readiness["file_upload_enabled"] is False
        assert readiness["official_api_enabled"] is False
        assert readiness["controlled_commit_enabled"] is False
        assert readiness["customer_business_mutation"] is False
        with pytest.raises(HTTPException) as denied:
            get_rentmanager_resource_readiness(Response(), sales)
        assert denied.value.status_code == 403
    finally:
        db.close()
        engine.dispose()
