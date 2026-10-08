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
from app.models.charge import Charge
from app.models.gl_transaction import GLTransaction
from app.models.hoa_association import HOAAssociation, HOAPropertyMembership
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.property import Property, Unit
from app.models.user import Organization
from app.routers import buildium_association_unit_migrations as api
from app.routers import buildium_migrations as base_api
from app.schemas.buildium_association_unit_migration import (
    BuildiumApiAssociationUnitCommitIn,
    BuildiumApiAssociationUnitDryRunIn,
    BuildiumAssociationUnitCommitIn,
    BuildiumAssociationUnitDryRunIn,
    BuildiumAssociationUnitResolutionIn,
)
from app.services import buildium_api_transport as transport
from app.services.buildium_api_transport import BuildiumApiFetchResult, BuildiumApiTransportError


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _admin(db):
    row = PlatformUser(
        email="buildium-hoa-unit-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Buildium",
        last_name="HoaUnit",
        role=PlatformUserRole.PLATFORM_ADMIN,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _org(db, name="HOA Unit Migration Org"):
    row = Organization(name=name, slug=name.lower().replace(" ", "-"), is_active=True)
    db.add(row)
    db.commit()
    return row


def _run(db, org):
    row = PlatformMigrationRun(
        organization_id=org.id,
        provider="BUILDIUM",
        source_account_ref="buildium-hoa-units",
        status="DRAFT",
    )
    db.add(row)
    db.commit()
    return row


def _association(db, org, name="Lakeview HOA"):
    row = HOAAssociation(
        organization_id=org.id,
        name=name,
        name_key=name.casefold(),
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _property_unit(db, org, *, name="Lake Building", unit_number="A-1"):
    prop = Property(
        organization_id=org.id,
        name=name,
        property_type="multi_family",
        address_line1="100 Lake Ave",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        country="USA",
        is_active=True,
    )
    db.add(prop)
    db.flush()
    unit = Unit(
        property_id=prop.id,
        unit_number=unit_number,
        bedrooms=2,
        bathrooms=1,
        monthly_rent=1000,
        is_active=True,
    )
    db.add(unit)
    db.commit()
    return prop, unit


def _association_mapping(db, run, association, *, source_id="9401"):
    row = PlatformMigrationItem(
        run_id=run.id,
        organization_id=run.organization_id,
        provider="BUILDIUM",
        resource="HOA_ASSOCIATIONS",
        source_id=source_id,
        target_entity="HOA_ASSOCIATION",
        target_id=association.id,
        source_fingerprint="a" * 64,
    )
    db.add(row)
    db.commit()
    return row


def _membership(db, org, association, prop):
    row = HOAPropertyMembership(
        organization_id=org.id,
        association_id=association.id,
        property_id=prop.id,
    )
    db.add(row)
    db.commit()
    return row


def _record(**changes):
    row = {
        "Id": 9501,
        "AssociationId": 9401,
        "AssociationName": "Lakeview HOA",
        "UnitNumber": "A-1",
        "UnitSize": 900,
        "UnitBedrooms": "Two",
        "UnitBathrooms": "One",
        "Address": {
            "AddressLine1": "PRIVATE SOURCE ADDRESS",
            "City": "Cleveland",
            "State": "OH",
            "PostalCode": "44113",
            "Country": "United States",
        },
    }
    row.update(changes)
    return row


def test_buildium_hoa_unit_reconciles_existing_membership_and_replays_without_customer_mutation():
    db, engine = _session()
    try:
        admin = _admin(db)
        org = _org(db)
        run = _run(db, org)
        association = _association(db, org)
        _association_mapping(db, run, association)
        prop, unit = _property_unit(db, org)
        _membership(db, org, association, prop)

        before = (
            db.query(Property).count(),
            db.query(Unit).count(),
            db.query(HOAPropertyMembership).count(),
            db.query(Charge).count(),
            db.query(GLTransaction).count(),
        )

        preview = api.dry_run_buildium_association_units(
            run.id,
            BuildiumAssociationUnitDryRunIn(records=[_record()]),
            db=db,
            current_user=admin,
        )
        assert preview.invalid == 0
        assert preview.reviewable == 1
        assert preview.rows[0].mapped["target_hoa_association_id"] == association.id

        resolution = BuildiumAssociationUnitResolutionIn(
            source_id=9501,
            action="MATCH_EXISTING",
            target_unit_id=unit.id,
        )
        reviewed = api.dry_run_buildium_association_units(
            run.id,
            BuildiumAssociationUnitDryRunIn(
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        committed = api.commit_buildium_association_units(
            run.id,
            BuildiumAssociationUnitCommitIn(
                fingerprint=reviewed.fingerprint,
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert committed.matched_existing == 1

        mapping = (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "HOA_UNITS")
            .one()
        )
        assert mapping.target_entity == "HOA_UNIT_RELATIONSHIP"
        assert mapping.target_id == unit.id
        assert before == (
            db.query(Property).count(),
            db.query(Unit).count(),
            db.query(HOAPropertyMembership).count(),
            db.query(Charge).count(),
            db.query(GLTransaction).count(),
        )

        replay_preview = api.dry_run_buildium_association_units(
            run.id,
            BuildiumAssociationUnitDryRunIn(
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        replay = api.commit_buildium_association_units(
            run.id,
            BuildiumAssociationUnitCommitIn(
                fingerprint=replay_preview.fingerprint,
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert replay.replayed is True
        assert replay.rows[0].replayed is True

        items = base_api.list_migration_items(
            run.id,
            response=Response(),
            resource="hoa_units",
            limit=20,
            db=db,
            current_user=admin,
        )
        assert len(items) == 1
        assert items[0].target_exists is True
        assert "A-1" in items[0].target_label

        audit_text = "\n".join(
            str(row.new_value or "")
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        assert "PRIVATE SOURCE ADDRESS" not in audit_text
        assert "UnitSize" not in audit_text
    finally:
        db.close()
        engine.dispose()


def test_buildium_hoa_unit_requires_mapped_association_existing_membership_and_fingerprint_stability():
    db, engine = _session()
    try:
        admin = _admin(db)
        org = _org(db)
        run = _run(db, org)
        association = _association(db, org)
        prop, unit = _property_unit(db, org)

        missing_dependency = api.dry_run_buildium_association_units(
            run.id,
            BuildiumAssociationUnitDryRunIn(records=[_record()]),
            db=db,
            current_user=admin,
        )
        assert missing_dependency.invalid == 1

        _association_mapping(db, run, association)
        resolution = BuildiumAssociationUnitResolutionIn(
            source_id=9501,
            action="MATCH_EXISTING",
            target_unit_id=unit.id,
        )
        with pytest.raises(HTTPException) as exc:
            api.dry_run_buildium_association_units(
                run.id,
                BuildiumAssociationUnitDryRunIn(
                    records=[_record()],
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        membership = _membership(db, org, association, prop)
        reviewed = api.dry_run_buildium_association_units(
            run.id,
            BuildiumAssociationUnitDryRunIn(
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )

        db.delete(membership)
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_association_units(
                run.id,
                BuildiumAssociationUnitCommitIn(
                    fingerprint=reviewed.fingerprint,
                    records=[_record()],
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "fingerprint" in exc.value.detail.lower()
        assert (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "HOA_UNITS")
            .count()
            == 0
        )
    finally:
        db.close()
        engine.dispose()


def test_buildium_hoa_unit_skip_validation_scope_and_routes():
    from app.main import app

    db, engine = _session()
    try:
        admin = _admin(db)
        org = _org(db)
        run = _run(db, org)
        association = _association(db, org)
        _association_mapping(db, run, association)
        prop, unit = _property_unit(db, org)
        _membership(db, org, association, prop)

        wrong_prop, wrong_unit = _property_unit(
            db, org, name="Not HOA Linked", unit_number="A-1"
        )
        with pytest.raises(HTTPException) as exc:
            api.dry_run_buildium_association_units(
                run.id,
                BuildiumAssociationUnitDryRunIn(
                    records=[_record()],
                    resolutions=[
                        BuildiumAssociationUnitResolutionIn(
                            source_id=9501,
                            action="MATCH_EXISTING",
                            target_unit_id=wrong_unit.id,
                        )
                    ],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        skip = BuildiumAssociationUnitResolutionIn(source_id=9501, action="SKIP")
        reviewed = api.dry_run_buildium_association_units(
            run.id,
            BuildiumAssociationUnitDryRunIn(
                records=[_record()],
                resolutions=[skip],
            ),
            db=db,
            current_user=admin,
        )
        result = api.commit_buildium_association_units(
            run.id,
            BuildiumAssociationUnitCommitIn(
                fingerprint=reviewed.fingerprint,
                records=[_record()],
                resolutions=[skip],
            ),
            db=db,
            current_user=admin,
        )
        assert result.matched_existing == 0
        assert result.skipped_review == 1

        duplicate = api.dry_run_buildium_association_units(
            run.id,
            BuildiumAssociationUnitDryRunIn(
                records=[_record(), _record(UnitNumber="B-2")]
            ),
            db=db,
            current_user=admin,
        )
        assert duplicate.invalid == 1

        mismatch = api.dry_run_buildium_association_units(
            run.id,
            BuildiumAssociationUnitDryRunIn(
                records=[_record(AssociationName="Wrong HOA")]
            ),
            db=db,
            current_user=admin,
        )
        assert mismatch.invalid == 1

        with pytest.raises(ValidationError):
            BuildiumAssociationUnitDryRunIn(
                records=[_record()],
                client_secret="secret",
            )

        paths = set(app.openapi()["paths"])
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/hoa-units/dry-run"
            in paths
        )
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/hoa-units/commit"
            in paths
        )
    finally:
        db.close()
        engine.dispose()



class _AssociationUnitApiResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def _configure_association_unit_transport(monkeypatch):
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_MODE", "sandbox")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_ID", "hoa-unit-client")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_SECRET", "hoa-unit-secret")
    monkeypatch.setattr(
        transport.settings,
        "BUILDIUM_API_SOURCE_ACCOUNT_REF",
        "buildium-hoa-units",
    )


def test_buildium_api_fetches_bounded_association_unit_collection(monkeypatch):
    _configure_association_unit_transport(monkeypatch)
    calls = []

    def fake_get(url, *, headers, params, timeout):
        calls.append((url, params.copy(), headers.copy()))
        return _AssociationUnitApiResponse(200, [_record()])

    monkeypatch.setattr(transport.requests, "get", fake_get)
    fetched = transport.fetch_association_units(
        expected_source_account_ref="buildium-hoa-units"
    )
    assert fetched.records == [_record()]
    assert fetched.request_count == 1
    assert calls[0][0] == "https://apisandbox.buildium.com/v1/associations/units"
    assert calls[0][1] == {"offset": 0, "limit": 500}
    assert calls[0][2]["x-buildium-client-secret"] == "hoa-unit-secret"

    def full_page(url, *, headers, params, timeout):
        if params["offset"] == 0:
            return _AssociationUnitApiResponse(200, [{"Id": i + 1} for i in range(500)])
        return _AssociationUnitApiResponse(200, [{"Id": 501}])

    monkeypatch.setattr(transport.requests, "get", full_page)
    with pytest.raises(BuildiumApiTransportError) as exc:
        transport.fetch_association_units(
            expected_source_account_ref="buildium-hoa-units"
        )
    assert exc.value.code == "source_too_large"


def test_buildium_api_association_unit_reconciles_replays_and_fails_closed(monkeypatch):
    db, engine = _session()
    try:
        admin = _admin(db)
        org = _org(db)
        run = _run(db, org)
        association = _association(db, org)
        association_mapping = _association_mapping(db, run, association)
        prop, unit = _property_unit(db, org)
        membership = _membership(db, org, association, prop)
        state = {"unit_number": "A-1"}

        def fetched(*, expected_source_account_ref):
            assert expected_source_account_ref == "buildium-hoa-units"
            return BuildiumApiFetchResult(
                records=[_record(UnitNumber=state["unit_number"])],
                mode="sandbox",
                request_count=1,
            )

        monkeypatch.setattr(api, "fetch_association_units", fetched)
        resolution = BuildiumAssociationUnitResolutionIn(
            source_id=9501,
            action="MATCH_EXISTING",
            target_unit_id=unit.id,
        )
        reviewed = api.api_dry_run_buildium_association_units(
            run.id,
            BuildiumApiAssociationUnitDryRunIn(resolutions=[resolution]),
            db=db,
            current_user=admin,
        )
        assert reviewed.invalid == 0
        committed = api.api_commit_buildium_association_units(
            run.id,
            BuildiumApiAssociationUnitCommitIn(
                fingerprint=reviewed.fingerprint,
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert committed.matched_existing == 1

        replay_reviewed = api.api_dry_run_buildium_association_units(
            run.id,
            BuildiumApiAssociationUnitDryRunIn(resolutions=[resolution]),
            db=db,
            current_user=admin,
        )
        replay = api.api_commit_buildium_association_units(
            run.id,
            BuildiumApiAssociationUnitCommitIn(
                fingerprint=replay_reviewed.fingerprint,
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert replay.replayed is True

        state["unit_number"] = "B-2"
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_association_units(
                run.id,
                BuildiumApiAssociationUnitCommitIn(
                    fingerprint=replay_reviewed.fingerprint,
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        state["unit_number"] = "A-1"

        association_mapping.source_fingerprint = "b" * 64
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_association_units(
                run.id,
                BuildiumApiAssociationUnitCommitIn(
                    fingerprint=replay_reviewed.fingerprint,
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        association_mapping.source_fingerprint = "a" * 64
        db.commit()
        reviewed_again = api.api_dry_run_buildium_association_units(
            run.id,
            BuildiumApiAssociationUnitDryRunIn(resolutions=[resolution]),
            db=db,
            current_user=admin,
        )
        db.delete(membership)
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_association_units(
                run.id,
                BuildiumApiAssociationUnitCommitIn(
                    fingerprint=reviewed_again.fingerprint,
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        audit = "\n".join(
            str(row.new_value or "")
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        assert "PRIVATE SOURCE ADDRESS" not in audit
        assert "hoa-unit-secret" not in audit

        with pytest.raises(ValidationError):
            BuildiumApiAssociationUnitDryRunIn(records=[_record()])
    finally:
        db.close()
        engine.dispose()


def test_buildium_api_association_unit_routes_and_status(monkeypatch):
    from app.main import app

    db, engine = _session()
    try:
        admin = _admin(db)
        org = _org(db)
        _run(db, org)
        monkeypatch.setattr(
            base_api,
            "transport_status",
            lambda: type(
                "TransportState",
                (),
                {"mode": "sandbox", "configured": True, "source_account_bound": True},
            )(),
        )
        assert "HOA_UNITS" in base_api.get_buildium_transport_status(
            current_user=admin
        ).supported_resources
        paths = set(app.openapi()["paths"])
        assert "/api/platform/migrations/buildium/runs/{run_id}/hoa-units/api-dry-run" in paths
        assert "/api/platform/migrations/buildium/runs/{run_id}/hoa-units/api-commit" in paths
    finally:
        db.close()
        engine.dispose()
