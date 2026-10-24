from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
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
    BuildiumApiPropertyReserveCommitIn,
    BuildiumApiPropertyReserveDryRunIn,
    BuildiumPropertyReserveResolutionIn,
)
from app.services.buildium_api_transport import BuildiumApiFetchResult


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _platform_admin(db):
    row = PlatformUser(
        email="buildium-api-reserve-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Buildium",
        last_name="Reserve",
        role=PlatformUserRole.PLATFORM_ADMIN,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _org(db):
    row = Organization(
        name="Buildium API Reserve Target",
        slug="buildium-api-reserve-target",
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _run(db, org):
    row = PlatformMigrationRun(
        organization_id=org.id,
        provider="BUILDIUM",
        source_account_ref="sandbox-account-A",
        status="DRAFT",
    )
    db.add(row)
    db.commit()
    return row


def _provider_record(**changes):
    row = {
        "Id": 1001,
        "Name": "Mapped Property",
        "IsActive": True,
        "Reserve": 125.50,
        "StructureDescription": "DO-NOT-PERSIST-PROVIDER-PROPERTY-DESCRIPTION",
        "OperatingBankAccountId": 991,
        "PropertyManager": {
            "Id": 77,
            "FirstName": "DO-NOT-PERSIST-PROVIDER-MANAGER",
            "LastName": "Secret",
        },
        "Address": {
            "AddressLine1": "DO-NOT-PERSIST-PROVIDER-ADDRESS",
            "City": "Cleveland",
            "State": "OH",
            "PostalCode": "44113",
            "Country": "United States",
        },
    }
    row.update(changes)
    return row


def _target(db, run):
    prop = Property(
        organization_id=run.organization_id,
        name="Mapped Property",
        property_type=PropertyType.MULTI_FAMILY,
        address_line1="10 Lake Ave",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        country="United States",
        is_active=True,
        required_reserve_amount=Decimal("0.00"),
    )
    db.add(prop)
    db.flush()
    db.add(
        PlatformMigrationItem(
            run_id=run.id,
            organization_id=run.organization_id,
            provider="BUILDIUM",
            resource="PROPERTIES",
            source_id="1001",
            target_entity="PROPERTY",
            target_id=prop.id,
            source_fingerprint="p" * 64,
        )
    )
    db.commit()
    return prop


def test_buildium_api_property_reserve_applies_reviewed_source_and_replays(monkeypatch):
    db, engine = _session()
    try:
        admin = _platform_admin(db)
        org = _org(db)
        run = _run(db, org)
        target = _target(db, run)

        def fetched(*, expected_source_account_ref):
            assert expected_source_account_ref == "sandbox-account-A"
            return BuildiumApiFetchResult(
                records=[_provider_record()],
                mode="sandbox",
                request_count=1,
            )

        monkeypatch.setattr(api, "fetch_rental_properties", fetched)
        resolution = BuildiumPropertyReserveResolutionIn(
            source_id=1001,
            action="APPLY_SOURCE",
            expected_target_reserve=Decimal("0.00"),
        )
        reviewed = api.api_dry_run_buildium_property_reserves(
            run.id,
            BuildiumApiPropertyReserveDryRunIn(resolutions=[resolution]),
            db=db,
            current_user=admin,
        )
        assert reviewed.invalid == 0
        assert reviewed.reviewable == 1
        assert reviewed.apply_source == 1
        assert reviewed.rows[0].mapped["source_reserve"] == "125.50"
        assert reviewed.rows[0].mapped["target_required_reserve"] == "0.00"

        committed = api.api_commit_buildium_property_reserves(
            run.id,
            BuildiumApiPropertyReserveCommitIn(
                fingerprint=reviewed.fingerprint,
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert committed.updated == 1
        assert committed.matched_existing == 0
        db.refresh(target)
        assert Decimal(target.required_reserve_amount) == Decimal("125.50")

        mapping = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.resource == "PROPERTY_RESERVES",
                PlatformMigrationItem.source_id == "1001",
            )
            .one()
        )
        assert mapping.target_entity == "PROPERTY"
        assert mapping.target_id == target.id

        replay = api.api_commit_buildium_property_reserves(
            run.id,
            BuildiumApiPropertyReserveCommitIn(
                fingerprint=reviewed.fingerprint,
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert replay.replayed is True
        assert (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "PROPERTY_RESERVES")
            .count()
            == 1
        )

        audit = "\n".join(
            row.new_value or ""
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        assert "125.50" not in audit
        assert "DO-NOT-PERSIST-PROVIDER-PROPERTY-DESCRIPTION" not in audit
        assert "DO-NOT-PERSIST-PROVIDER-MANAGER" not in audit
        assert "DO-NOT-PERSIST-PROVIDER-ADDRESS" not in audit
        assert '"raw_response_stored":false' in audit.lower()
        assert '"reserve_amounts_audited":false' in audit.lower()
    finally:
        db.close()
        engine.dispose()


def test_buildium_api_property_reserve_provider_and_target_drift_fail_closed(monkeypatch):
    db, engine = _session()
    try:
        admin = _platform_admin(db)
        org = _org(db)
        run = _run(db, org)
        target = _target(db, run)
        state = {"reserve": 125.50}

        def fetched(*, expected_source_account_ref):
            assert expected_source_account_ref == "sandbox-account-A"
            return BuildiumApiFetchResult(
                records=[_provider_record(Reserve=state["reserve"])],
                mode="sandbox",
                request_count=1,
            )

        monkeypatch.setattr(api, "fetch_rental_properties", fetched)
        resolution = BuildiumPropertyReserveResolutionIn(
            source_id=1001,
            action="APPLY_SOURCE",
            expected_target_reserve=Decimal("0.00"),
        )
        reviewed = api.api_dry_run_buildium_property_reserves(
            run.id,
            BuildiumApiPropertyReserveDryRunIn(resolutions=[resolution]),
            db=db,
            current_user=admin,
        )

        state["reserve"] = 126.00
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_property_reserves(
                run.id,
                BuildiumApiPropertyReserveCommitIn(
                    fingerprint=reviewed.fingerprint,
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "stale" in exc.value.detail.lower()
        db.refresh(target)
        assert Decimal(target.required_reserve_amount) == Decimal("0.00")
        assert (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "PROPERTY_RESERVES")
            .count()
            == 0
        )

        state["reserve"] = 125.50
        reviewed = api.api_dry_run_buildium_property_reserves(
            run.id,
            BuildiumApiPropertyReserveDryRunIn(resolutions=[resolution]),
            db=db,
            current_user=admin,
        )
        target.required_reserve_amount = Decimal("10.00")
        db.commit()

        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_property_reserves(
                run.id,
                BuildiumApiPropertyReserveCommitIn(
                    fingerprint=reviewed.fingerprint,
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "changed" in exc.value.detail.lower() or "stale" in exc.value.detail.lower()
        db.refresh(target)
        assert Decimal(target.required_reserve_amount) == Decimal("10.00")
        assert (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "PROPERTY_RESERVES")
            .count()
            == 0
        )
    finally:
        db.close()
        engine.dispose()


def test_buildium_api_property_reserve_request_boundary_routes_and_status(monkeypatch):
    from app.main import app

    db, engine = _session()
    try:
        admin = _platform_admin(db)

        with pytest.raises(ValidationError):
            BuildiumApiPropertyReserveDryRunIn(records=[_provider_record()])
        with pytest.raises(ValidationError):
            BuildiumApiPropertyReserveCommitIn(
                fingerprint="a" * 64,
                client_secret="secret",
            )

        monkeypatch.setattr(
            api,
            "transport_status",
            lambda: type(
                "TransportState",
                (),
                {
                    "mode": "sandbox",
                    "configured": True,
                    "source_account_bound": True,
                },
            )(),
        )
        status = api.get_buildium_transport_status(current_user=admin)
        assert "PROPERTY_RESERVES" in status.supported_resources

        paths = set(app.openapi()["paths"])
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/property-reserves/api-dry-run"
            in paths
        )
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/property-reserves/api-commit"
            in paths
        )
    finally:
        db.close()
        engine.dispose()
