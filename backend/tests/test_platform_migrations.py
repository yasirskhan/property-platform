from __future__ import annotations

from types import SimpleNamespace

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
from app.routers import platform_migrations as api
from app.schemas.platform_migration import (
    AppFolioMigrationRunCreateIn,
    AppFolioPropertyDryRunIn,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _platform_user(db, role: PlatformUserRole) -> PlatformUser:
    row = PlatformUser(
        email=f"{role.value}-{db.query(PlatformUser).count()}@example.com",
        hashed_password=hash_password("migration-test-password"),
        first_name="Platform",
        last_name="Migration",
        role=role,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _org(db, *, name: str = "Migration Target", active: bool = True) -> Organization:
    row = Organization(
        name=name,
        slug=name.lower().replace(" ", "-"),
        is_active=active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _valid_record(**changes):
    record = {
        "Id": "AF-100",
        "Name": "Lake Apartments",
        "Address1": "10 Lake Ave",
        "Address2": "Suite 1",
        "City": "Cleveland",
        "State": "OH",
        "Zip": "44113",
        "PropertyType": "Multi Family",
        "HiddenAt": None,
    }
    record.update(changes)
    return record


def test_appfolio_run_roles_scope_and_no_store_reads():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        sales = _platform_user(db, PlatformUserRole.PLATFORM_SALES)
        org = _org(db)

        created = api.create_run(
            AppFolioMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="account-123",
            ),
            db=db,
            current_user=admin,
        )
        assert created.provider == "APPFOLIO"
        assert created.status == "DRAFT"

        response = Response()
        listed = api.list_runs(
            response=response,
            organization_id=org.id,
            limit=100,
            db=db,
            current_user=support,
        )
        assert [row.id for row in listed] == [created.id]
        assert response.headers["cache-control"] == "no-store"

        response = Response()
        fetched = api.get_run(
            created.id,
            response=response,
            db=db,
            current_user=support,
        )
        assert fetched.id == created.id
        assert response.headers["cache-control"] == "no-store"

        with pytest.raises(HTTPException) as exc:
            api.create_run(
                AppFolioMigrationRunCreateIn(
                    organization_id=org.id,
                    source_account_ref="blocked",
                ),
                db=db,
                current_user=support,
            )
        assert exc.value.status_code == 403

        with pytest.raises(HTTPException) as exc:
            api.list_runs(
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
            api.get_run(
                created.id,
                response=Response(),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 404
    finally:
        db.close()
        engine.dispose()


def test_appfolio_property_dry_run_is_idempotent_and_target_non_mutating():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db)
        run = api.create_run(
            AppFolioMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="portfolio-A",
            ),
            db=db,
            current_user=admin,
        )

        payload = AppFolioPropertyDryRunIn(
            records=[
                _valid_record(),
                _valid_record(Id="AF-200", HiddenAt="2026-01-01"),
                _valid_record(Id="AF-300", Name=""),
                _valid_record(Id="AF-100", Name="Duplicate"),
            ]
        )
        before_properties = db.query(Property).count()

        first = api.dry_run_appfolio_properties(
            run.id,
            payload,
            db=db,
            current_user=admin,
        )
        assert first.total == 4
        assert first.importable == 1
        assert first.skipped_hidden == 1
        assert first.invalid == 2
        assert first.replayed is False
        assert first.rows[0].mapped["property_type"] == "multi_family"
        assert db.query(Property).count() == before_properties

        stored = db.get(PlatformMigrationRun, run.id)
        assert stored.status == "DRY_RUN_READY"
        assert stored.last_dry_run_fingerprint == first.fingerprint
        assert stored.last_dry_run_summary["resource"] == "PROPERTIES"

        audit_before = (
            db.query(AuditLog)
            .filter(
                AuditLog.entity_type == "platform_migration_run",
                AuditLog.entity_id == run.id,
            )
            .count()
        )

        second = api.dry_run_appfolio_properties(
            run.id,
            payload,
            db=db,
            current_user=admin,
        )
        assert second.replayed is True
        assert second.fingerprint == first.fingerprint
        assert db.query(Property).count() == before_properties

        audit_after = (
            db.query(AuditLog)
            .filter(
                AuditLog.entity_type == "platform_migration_run",
                AuditLog.entity_id == run.id,
            )
            .count()
        )
        assert audit_after == audit_before
    finally:
        db.close()
        engine.dispose()


def test_appfolio_dry_run_warns_on_existing_target_and_unknown_property_type():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_DEV)
        org = _org(db)
        db.add(
            Property(
                organization_id=org.id,
                name="Lake Apartments",
                property_type="multi_family",
                address_line1="10 Lake Ave",
                address_line2="Suite 1",
                city="Cleveland",
                state="OH",
                zip_code="44113",
                country="USA",
                is_active=True,
            )
        )
        db.commit()

        run = api.create_run(
            AppFolioMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="portfolio-B",
            ),
            db=db,
            current_user=admin,
        )
        result = api.dry_run_appfolio_properties(
            run.id,
            AppFolioPropertyDryRunIn(
                include_hidden=True,
                records=[_valid_record(PropertyType="Mystery Type", HiddenAt="yes")],
            ),
            db=db,
            current_user=admin,
        )
        assert result.importable == 1
        assert result.skipped_hidden == 0
        assert result.warning_count == 2
        assert result.rows[0].mapped["property_type"] == "other"
        assert any("Unrecognized AppFolio PropertyType" in x for x in result.rows[0].warnings)
        assert any("Possible existing target property match" in x for x in result.rows[0].warnings)
        assert db.query(Property).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_appfolio_schemas_reject_credentials_and_raw_transport_fields():
    with pytest.raises(ValidationError):
        AppFolioMigrationRunCreateIn(
            organization_id=1,
            source_account_ref="portfolio",
            api_key="secret",
        )

    with pytest.raises(ValidationError):
        AppFolioPropertyDryRunIn(
            records=[_valid_record()],
            access_token="secret",
        )
