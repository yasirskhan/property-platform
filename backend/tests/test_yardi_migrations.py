from __future__ import annotations

import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.platform_migration import PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.property import Property
from app.models.user import Organization
from app.routers import yardi_migrations as api
from app.schemas.yardi_migration import YardiMigrationRunCreateIn


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _platform_user(db, role):
    row = PlatformUser(
        email=f"yardi-{role.value.lower()}-{db.query(PlatformUser).count()}@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Yardi",
        last_name="Tester",
        role=role,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _org(db, slug="yardi-org"):
    row = Organization(name="Yardi Org", slug=slug, is_active=True)
    db.add(row)
    db.commit()
    return row


def test_yardi_run_roles_scope_no_store_and_no_business_mutation():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        sales = _platform_user(db, PlatformUserRole.PLATFORM_SALES)
        org = _org(db)
        before_properties = db.query(Property).count()

        created = api.create_yardi_run(
            YardiMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="voyager-client-001",
            ),
            db=db,
            current_user=admin,
        )
        assert created.provider == "YARDI"
        assert created.status == "DRAFT"
        assert db.query(Property).count() == before_properties

        response = Response()
        listed = api.list_yardi_runs(
            response=response,
            organization_id=org.id,
            limit=100,
            db=db,
            current_user=support,
        )
        assert [row.id for row in listed] == [created.id]
        assert response.headers["cache-control"] == "no-store"

        response = Response()
        fetched = api.get_yardi_run(
            created.id,
            response=response,
            db=db,
            current_user=support,
        )
        assert fetched.id == created.id
        assert response.headers["cache-control"] == "no-store"

        with pytest.raises(HTTPException) as exc:
            api.create_yardi_run(
                YardiMigrationRunCreateIn(
                    organization_id=org.id,
                    source_account_ref="blocked",
                ),
                db=db,
                current_user=support,
            )
        assert exc.value.status_code == 403

        with pytest.raises(HTTPException) as exc:
            api.list_yardi_runs(
                response=Response(),
                organization_id=None,
                limit=100,
                db=db,
                current_user=sales,
            )
        assert exc.value.status_code == 403

        org.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.get_yardi_run(
                created.id,
                response=Response(),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 404
    finally:
        db.close()
        engine.dispose()


def test_yardi_run_rejects_credentials_raw_payloads_and_audit_is_redacted():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, slug="yardi-redaction")

        with pytest.raises(ValidationError):
            YardiMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="token=PRIVATE",
            )
        with pytest.raises(ValidationError):
            YardiMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref='{"property":"raw"}',
            )
        with pytest.raises(ValidationError):
            YardiMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="voyager-001",
                password="PRIVATE",
            )

        created = api.create_yardi_run(
            YardiMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="voyager-portfolio-redacted",
            ),
            db=db,
            current_user=admin,
        )
        assert created.provider == "YARDI"

        audit = db.query(AuditLog).filter(
            AuditLog.entity_type == "platform_migration_run",
            AuditLog.entity_id == created.id,
        ).one()
        audit_text = str(audit.new_value or "")
        assert "voyager-portfolio-redacted" not in audit_text
        assert "source_account_bound" in audit_text
        assert "credentials_stored" in audit_text
        assert "raw_provider_payload_stored" in audit_text
    finally:
        db.close()
        engine.dispose()


def test_yardi_run_is_provider_isolated_and_routes_are_exposed():
    from app.main import app

    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, slug="yardi-isolation")
        yardi = api.create_yardi_run(
            YardiMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="voyager-isolated",
            ),
            db=db,
            current_user=admin,
        )
        other = PlatformMigrationRun(
            organization_id=org.id,
            provider="APPFOLIO",
            source_account_ref="appfolio-other",
            status="DRAFT",
            created_by_platform_user_id=admin.id,
        )
        db.add(other)
        db.commit()

        listed = api.list_yardi_runs(
            response=Response(),
            organization_id=org.id,
            limit=100,
            db=db,
            current_user=admin,
        )
        assert [row.id for row in listed] == [yardi.id]

        with pytest.raises(HTTPException) as exc:
            api.get_yardi_run(
                other.id,
                response=Response(),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 404

        paths = set(app.openapi()["paths"])
        assert "/api/platform/migrations/yardi/runs" in paths
        assert "/api/platform/migrations/yardi/runs/{run_id}" in paths
    finally:
        db.close()
        engine.dispose()
