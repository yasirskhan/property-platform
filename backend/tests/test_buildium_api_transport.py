from __future__ import annotations

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
from app.models.property import Property, PropertyType, Unit
from app.models.user import Organization
from app.routers import buildium_migrations as api
from app.schemas.buildium_migration import (
    BuildiumApiPropertyCommitIn,
    BuildiumApiPropertyDryRunIn,
    BuildiumApiUnitCommitIn,
    BuildiumApiUnitDryRunIn,
)
from app.services import buildium_api_transport as transport
from app.services.buildium_api_transport import BuildiumApiFetchResult, BuildiumApiTransportError


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _admin(db):
    row = PlatformUser(
        email="buildium-api-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Buildium",
        last_name="Api",
        role=PlatformUserRole.PLATFORM_ADMIN,
        is_active=True,
    )
    db.add(row); db.commit(); return row


def _org(db):
    row = Organization(name="Buildium API Target", slug="buildium-api-target", is_active=True)
    db.add(row); db.commit(); return row


def _run(db, org, source_ref="sandbox-account-A"):
    row = PlatformMigrationRun(
        organization_id=org.id,
        provider="BUILDIUM",
        source_account_ref=source_ref,
        status="DRAFT",
    )
    db.add(row); db.commit(); return row


def _record(**changes):
    row = {
        "Id": 6001,
        "Name": "API Lake Apartments",
        "IsActive": True,
        "Address": {
            "AddressLine1": "PRIVATE PROVIDER ADDRESS",
            "AddressLine2": "",
            "AddressLine3": "",
            "City": "Cleveland",
            "State": "OH",
            "PostalCode": "44113",
            "Country": "United States",
        },
        "YearBuilt": 2000,
        "RentalType": "Residential",
        "RentalSubType": "MultiFamily",
    }
    row.update(changes)
    return row


def _target_property_mapping(db, run):
    prop = Property(
        organization_id=run.organization_id,
        name="API Lake Apartments",
        property_type=PropertyType.MULTI_FAMILY,
        address_line1="10 Lake Ave",
        address_line2=None,
        city="Cleveland",
        state="OH",
        zip_code="44113",
        country="United States",
        is_active=True,
    )
    db.add(prop)
    db.flush()
    db.add(PlatformMigrationItem(
        run_id=run.id,
        organization_id=run.organization_id,
        provider="BUILDIUM",
        resource="PROPERTIES",
        source_id="6001",
        target_entity="PROPERTY",
        target_id=prop.id,
        source_fingerprint="a" * 64,
    ))
    db.commit()
    return prop


def _unit_record(**changes):
    row = {
        "Id": 6101,
        "PropertyId": 6001,
        "BuildingName": "API Lake Apartments",
        "UnitNumber": "A-1",
        "Description": None,
        "MarketRent": 1200,
        "Address": {
            "AddressLine1": "10 Lake Ave",
            "AddressLine2": "",
            "AddressLine3": "",
            "City": "Cleveland",
            "State": "OH",
            "PostalCode": "44113",
            "Country": "United States",
        },
        "UnitBedrooms": "TwoBed",
        "UnitBathrooms": "OneBath",
        "UnitSize": 900,
        "IsUnitListed": True,
        "IsUnitOccupied": True,
    }
    row.update(changes)
    return row


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def test_buildium_transport_uses_fixed_server_headers_bounds_and_redacted_errors(monkeypatch):
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_MODE", "sandbox")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_ID", "client-id")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_SECRET", "TOP-SECRET")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_SOURCE_ACCOUNT_REF", "sandbox-account-A")
    calls = []
    def fake_get(url, *, headers, params, timeout):
        calls.append((url, headers.copy(), params.copy(), timeout))
        return _Response(200, [_record()])
    monkeypatch.setattr(transport.requests, "get", fake_get)

    result = transport.fetch_rental_properties(expected_source_account_ref="sandbox-account-A")
    assert result.mode == "sandbox" and result.request_count == 1
    assert result.records[0]["Id"] == 6001
    assert calls[0][0] == "https://apisandbox.buildium.com/v1/rentals"
    assert calls[0][1]["x-buildium-client-id"] == "client-id"
    assert calls[0][1]["x-buildium-client-secret"] == "TOP-SECRET"
    assert calls[0][2] == {"offset": 0, "limit": 500}

    with pytest.raises(BuildiumApiTransportError) as exc:
        transport.fetch_rental_properties(expected_source_account_ref="wrong-account")
    assert exc.value.code == "source_account_mismatch"
    assert "TOP-SECRET" not in str(exc.value)

    def unauthorized(*args, **kwargs):
        return _Response(401, {"message": "TOP-SECRET PRIVATE RESPONSE"})
    monkeypatch.setattr(transport.requests, "get", unauthorized)
    with pytest.raises(BuildiumApiTransportError) as exc:
        transport.fetch_rental_properties(expected_source_account_ref="sandbox-account-A")
    assert exc.value.code == "unauthorized"
    assert "PRIVATE RESPONSE" not in str(exc.value)
    assert "TOP-SECRET" not in str(exc.value)


def test_buildium_transport_rejects_silent_truncation(monkeypatch):
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_MODE", "production")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_ID", "client-id")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_SECRET", "secret")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_SOURCE_ACCOUNT_REF", "prod-A")
    def fake_get(url, *, headers, params, timeout):
        if params["offset"] == 0:
            return _Response(200, [{"Id": i + 1} for i in range(500)])
        return _Response(200, [{"Id": 501}])
    monkeypatch.setattr(transport.requests, "get", fake_get)
    with pytest.raises(BuildiumApiTransportError) as exc:
        transport.fetch_rental_properties(expected_source_account_ref="prod-A")
    assert exc.value.code == "source_too_large"


def test_buildium_api_property_route_reuses_existing_fingerprint_commit_without_credentials(monkeypatch):
    db, engine = _session()
    try:
        admin = _admin(db); org = _org(db); run = _run(db, org)
        def fetched(*, expected_source_account_ref):
            assert expected_source_account_ref == "sandbox-account-A"
            return BuildiumApiFetchResult(records=[_record()], mode="sandbox", request_count=1)
        monkeypatch.setattr(api, "fetch_rental_properties", fetched)

        reviewed = api.api_dry_run_buildium_properties(
            run.id,
            BuildiumApiPropertyDryRunIn(),
            db=db,
            current_user=admin,
        )
        assert reviewed.total == 1 and reviewed.importable == 1
        committed = api.api_commit_buildium_properties(
            run.id,
            BuildiumApiPropertyCommitIn(fingerprint=reviewed.fingerprint),
            db=db,
            current_user=admin,
        )
        assert committed.committed == 1
        assert db.query(Property).count() == 1
        mapping = db.query(PlatformMigrationItem).one()
        assert mapping.provider == "BUILDIUM" and mapping.resource == "PROPERTIES"

        with pytest.raises(ValidationError):
            BuildiumApiPropertyDryRunIn(client_secret="secret")
        with pytest.raises(ValidationError):
            BuildiumApiPropertyCommitIn(fingerprint=reviewed.fingerprint, records=[_record()])

        audit = "\n".join(
            str(row.new_value or "")
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        assert "PRIVATE PROVIDER ADDRESS" not in audit
        assert "TOP-SECRET" not in audit
        assert '"credentials_stored":false' in audit.lower()
        assert '"raw_response_stored":false' in audit.lower()
    finally:
        db.close(); engine.dispose()


def test_buildium_api_commit_refetch_detects_source_drift_and_routes_exist(monkeypatch):
    from app.main import app
    db, engine = _session()
    try:
        admin = _admin(db); org = _org(db); run = _run(db, org)
        state = {"changed": False}
        def fetched(*, expected_source_account_ref):
            record = _record(Name="Changed after review") if state["changed"] else _record()
            return BuildiumApiFetchResult(records=[record], mode="sandbox", request_count=1)
        monkeypatch.setattr(api, "fetch_rental_properties", fetched)
        reviewed = api.api_dry_run_buildium_properties(
            run.id, BuildiumApiPropertyDryRunIn(), db=db, current_user=admin
        )
        state["changed"] = True
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_properties(
                run.id,
                BuildiumApiPropertyCommitIn(fingerprint=reviewed.fingerprint),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(Property).count() == 0
        assert db.query(PlatformMigrationItem).count() == 0

        paths = set(app.openapi()["paths"])
        assert "/api/platform/migrations/buildium/transport/status" in paths
        assert "/api/platform/migrations/buildium/runs/{run_id}/properties/api-dry-run" in paths
        assert "/api/platform/migrations/buildium/runs/{run_id}/properties/api-commit" in paths
    finally:
        db.close(); engine.dispose()


def test_buildium_transport_fetches_units_from_fixed_endpoint(monkeypatch):
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_MODE", "sandbox")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_ID", "client-id")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_SECRET", "unit-secret")
    monkeypatch.setattr(
        transport.settings, "BUILDIUM_API_SOURCE_ACCOUNT_REF", "sandbox-account-A"
    )
    calls = []
    def fake_get(url, *, headers, params, timeout):
        calls.append((url, headers.copy(), params.copy(), timeout))
        return _Response(200, [_unit_record()])
    monkeypatch.setattr(transport.requests, "get", fake_get)

    result = transport.fetch_rental_units(
        expected_source_account_ref="sandbox-account-A"
    )
    assert result.records[0]["Id"] == 6101
    assert calls[0][0] == "https://apisandbox.buildium.com/v1/rentals/units"
    assert calls[0][1]["x-buildium-client-secret"] == "unit-secret"
    assert calls[0][2] == {"offset": 0, "limit": 500}


def test_buildium_api_unit_route_reuses_property_mapping_and_does_not_infer_occupancy(monkeypatch):
    db, engine = _session()
    try:
        admin = _admin(db); org = _org(db); run = _run(db, org)
        _target_property_mapping(db, run)
        def fetched(*, expected_source_account_ref):
            assert expected_source_account_ref == "sandbox-account-A"
            return BuildiumApiFetchResult(
                records=[_unit_record()], mode="sandbox", request_count=1
            )
        monkeypatch.setattr(api, "fetch_rental_units", fetched)

        reviewed = api.api_dry_run_buildium_units(
            run.id, BuildiumApiUnitDryRunIn(), db=db, current_user=admin
        )
        assert reviewed.invalid == 0 and reviewed.importable == 1
        assert any("source evidence only" in warning for warning in reviewed.rows[0].warnings)

        committed = api.api_commit_buildium_units(
            run.id,
            BuildiumApiUnitCommitIn(fingerprint=reviewed.fingerprint),
            db=db,
            current_user=admin,
        )
        assert committed.committed == 1
        unit = db.query(Unit).one()
        assert unit.unit_number == "A-1"
        assert unit.is_available is None
        mapping = (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "UNITS")
            .one()
        )
        assert mapping.target_entity == "UNIT"
        assert mapping.target_id == unit.id

        with pytest.raises(ValidationError):
            BuildiumApiUnitDryRunIn(client_secret="secret")
        with pytest.raises(ValidationError):
            BuildiumApiUnitCommitIn(
                fingerprint=reviewed.fingerprint, records=[_unit_record()]
            )
    finally:
        db.close(); engine.dispose()


def test_buildium_api_unit_commit_refetch_detects_source_drift_and_routes_exist(monkeypatch):
    from app.main import app
    db, engine = _session()
    try:
        admin = _admin(db); org = _org(db); run = _run(db, org)
        _target_property_mapping(db, run)
        state = {"changed": False}
        def fetched(*, expected_source_account_ref):
            record = (
                _unit_record(MarketRent=1300)
                if state["changed"] else _unit_record()
            )
            return BuildiumApiFetchResult(
                records=[record], mode="sandbox", request_count=1
            )
        monkeypatch.setattr(api, "fetch_rental_units", fetched)
        reviewed = api.api_dry_run_buildium_units(
            run.id, BuildiumApiUnitDryRunIn(), db=db, current_user=admin
        )
        state["changed"] = True
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_units(
                run.id,
                BuildiumApiUnitCommitIn(fingerprint=reviewed.fingerprint),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(Unit).count() == 0
        assert (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "UNITS")
            .count()
            == 0
        )

        paths = set(app.openapi()["paths"])
        assert "/api/platform/migrations/buildium/runs/{run_id}/units/api-dry-run" in paths
        assert "/api/platform/migrations/buildium/runs/{run_id}/units/api-commit" in paths
    finally:
        db.close(); engine.dispose()
