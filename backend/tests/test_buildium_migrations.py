from __future__ import annotations

import json

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.property import Property, PropertyType
from app.models.user import Organization
from app.routers import buildium_migrations as api
from app.schemas.buildium_migration import (
    BuildiumMigrationRunCreateIn,
    BuildiumPropertyCommitIn,
    BuildiumPropertyDryRunIn,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _platform_user(db, role: PlatformUserRole) -> PlatformUser:
    row = PlatformUser(
        email=f"{role.value}-{db.query(PlatformUser).count()}@example.com",
        hashed_password=hash_password("buildium-migration-test-password"),
        first_name="Platform",
        last_name="Migration",
        role=role,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _org(db, *, name: str = "Buildium Target", active: bool = True) -> Organization:
    row = Organization(
        name=name,
        slug=name.lower().replace(" ", "-"),
        is_active=active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _record(**changes):
    record = {
        "Id": 1001,
        "Name": "Lake Apartments",
        "IsActive": True,
        "Address": {
            "AddressLine1": "10 Lake Ave",
            "AddressLine2": "Building A",
            "AddressLine3": "",
            "City": "Cleveland",
            "State": "OH",
            "PostalCode": "44113",
            "Country": "United States",
        },
        "YearBuilt": 1998,
        "RentalType": "Residential",
        "RentalSubType": "MultiFamily",
    }
    record.update(changes)
    return record


def test_buildium_run_roles_scope_and_no_store_reads():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        sales = _platform_user(db, PlatformUserRole.PLATFORM_SALES)
        org = _org(db)

        created = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="buildium-account-123",
            ),
            db=db,
            current_user=admin,
        )
        assert created.provider == "BUILDIUM"
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
                BuildiumMigrationRunCreateIn(
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

        appfolio = PlatformMigrationRun(
            organization_id=org.id,
            provider="APPFOLIO",
            source_account_ref="other-provider",
            status="DRAFT",
            created_by_platform_user_id=admin.id,
        )
        db.add(appfolio)
        db.commit()
        db.refresh(appfolio)
        with pytest.raises(HTTPException) as exc:
            api.get_run(
                appfolio.id,
                response=Response(),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 404

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


def test_buildium_property_dry_run_maps_official_fields_without_target_mutation():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db)
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="portfolio-A",
            ),
            db=db,
            current_user=admin,
        )
        inactive = _record(Id=1002, Name="Dormant", IsActive=False)
        condo = _record(Id=1003, Name="Condo Group", RentalSubType="CondoTownhome")
        line3 = _record(
            Id=1004,
            Name="Three Line Address",
            Address={
                "AddressLine1": "1 Main St",
                "AddressLine2": "Floor 2",
                "AddressLine3": "Mail Stop 9",
                "City": "Cleveland",
                "State": "OH",
                "PostalCode": "44113",
                "Country": "United States",
            },
        )
        duplicate = _record(Id=1001, Name="Duplicate Source")
        before = db.query(Property).count()

        result = api.dry_run_buildium_properties(
            run.id,
            BuildiumPropertyDryRunIn(
                records=[_record(), inactive, condo, line3, duplicate]
            ),
            db=db,
            current_user=admin,
        )
        assert result.total == 5
        assert result.importable == 2
        assert result.skipped_inactive == 1
        assert result.invalid == 2
        assert db.query(Property).count() == before
        assert result.rows[0].mapped["property_type"] == PropertyType.MULTI_FAMILY.value
        assert result.rows[0].mapped["year_built"] == 1998
        assert result.rows[0].mapped["country"] == "United States"
        assert result.rows[2].mapped["property_type"] == PropertyType.OTHER.value
        assert any("CondoTownhome" in warning for warning in result.rows[2].warnings)
        assert "Address.AddressLine3" in result.rows[3].reason
        assert "Duplicate Buildium property Id" in result.rows[4].reason

        stored = db.get(PlatformMigrationRun, run.id)
        assert stored.status == "DRY_RUN_READY"
        assert stored.last_dry_run_fingerprint == result.fingerprint
        assert stored.last_dry_run_summary["resource"] == "PROPERTIES"
        assert stored.last_dry_run_summary["provider_credentials_stored"] is False

        audit_text = "\n".join(
            row.new_value or ""
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        lowered = audit_text.lower()
        assert "client-secret" not in lowered
        assert "x-buildium-client-secret" not in lowered
        assert json.dumps(_record()["Address"]) not in audit_text
    finally:
        db.close()
        engine.dispose()


def test_buildium_property_commit_exact_fingerprint_and_replay():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db)
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="portfolio-B",
            ),
            db=db,
            current_user=admin,
        )
        records = [
            _record(),
            _record(Id=1002, Name="Inactive Rental", IsActive=False),
        ]
        preview = api.dry_run_buildium_properties(
            run.id,
            BuildiumPropertyDryRunIn(include_inactive=True, records=records),
            db=db,
            current_user=admin,
        )

        stale_records = [_record(Name="Changed after review"), records[1]]
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_properties(
                run.id,
                BuildiumPropertyCommitIn(
                    include_inactive=True,
                    fingerprint=preview.fingerprint,
                    records=stale_records,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(Property).count() == 0
        assert db.query(PlatformMigrationItem).count() == 0

        first = api.commit_buildium_properties(
            run.id,
            BuildiumPropertyCommitIn(
                include_inactive=True,
                fingerprint=preview.fingerprint,
                records=records,
            ),
            db=db,
            current_user=admin,
        )
        assert first.committed == 2
        assert first.replayed is False
        assert db.query(Property).count() == 2
        assert db.query(PlatformMigrationItem).count() == 2

        inactive_target = (
            db.query(Property)
            .filter(Property.name == "Inactive Rental")
            .one()
        )
        assert inactive_target.is_active is False

        second = api.commit_buildium_properties(
            run.id,
            BuildiumPropertyCommitIn(
                include_inactive=True,
                fingerprint=preview.fingerprint,
                records=records,
            ),
            db=db,
            current_user=admin,
        )
        assert second.committed == 0
        assert second.replayed is True
        assert all(row.replayed for row in second.rows)
        assert db.query(Property).count() == 2
        assert db.query(PlatformMigrationItem).count() == 2

        response = Response()
        items = api.list_migration_items(
            run.id,
            response=response,
            resource="properties",
            limit=200,
            db=db,
            current_user=admin,
        )
        assert {item.source_id for item in items} == {"1001", "1002"}
        assert all(item.provider == "BUILDIUM" for item in items)
        assert all(item.target_exists for item in items)
        assert response.headers["cache-control"] == "no-store"
    finally:
        db.close()
        engine.dispose()


def test_buildium_property_commit_blocks_possible_existing_target_match():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db)
        existing = Property(
            organization_id=org.id,
            name="Lake Apartments",
            property_type=PropertyType.MULTI_FAMILY,
            address_line1="10 Lake Ave",
            address_line2="Building A",
            city="Cleveland",
            state="OH",
            zip_code="44113",
            country="United States",
        )
        db.add(existing)
        db.commit()

        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="portfolio-C",
            ),
            db=db,
            current_user=admin,
        )
        preview = api.dry_run_buildium_properties(
            run.id,
            BuildiumPropertyDryRunIn(records=[_record()]),
            db=db,
            current_user=admin,
        )
        assert preview.importable == 1
        assert any(
            warning.startswith("Possible existing target property match:")
            for warning in preview.rows[0].warnings
        )

        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_properties(
                run.id,
                BuildiumPropertyCommitIn(
                    fingerprint=preview.fingerprint,
                    records=[_record()],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "possible existing target matches" in exc.value.detail
        assert db.query(Property).count() == 1
        assert db.query(PlatformMigrationItem).count() == 0
    finally:
        db.close()
        engine.dispose()
