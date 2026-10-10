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
from app.models.property_group import PropertyGroup, PropertyGroupMembership
from app.models.user import Organization
from app.routers import buildium_migrations as api
from app.schemas.buildium_migration import (
    BuildiumApiPropertyGroupCommitIn,
    BuildiumApiPropertyGroupDryRunIn,
    BuildiumPropertyGroupResolutionIn,
)
from app.services import buildium_api_transport as transport
from app.services.buildium_api_transport import BuildiumApiFetchResult


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _platform_admin(db):
    row = PlatformUser(
        email="buildium-api-property-group-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Buildium",
        last_name="PropertyGroup",
        role=PlatformUserRole.PLATFORM_ADMIN,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _org(db):
    row = Organization(
        name="Buildium API Property Group Target",
        slug="buildium-api-property-group-target",
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
        "Id": 4401,
        "Name": "Cleveland Portfolio",
        "Description": "DO-NOT-PERSIST-PROVIDER-GROUP-DESCRIPTION",
        "Properties": [{"Id": 1001}],
        "CreatedByUser": {
            "Id": 77,
            "Name": "DO-NOT-PERSIST-PROVIDER-CREATOR",
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
    group = PropertyGroup(
        organization_id=run.organization_id,
        name="Cleveland Portfolio",
        name_key="cleveland portfolio",
        description="LOCAL-DESCRIPTION-MUST-STAY",
    )
    db.add(group)
    db.flush()
    db.add(
        PropertyGroupMembership(
            organization_id=run.organization_id,
            group_id=group.id,
            property_id=prop.id,
        )
    )
    db.commit()
    return prop, group


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def _configure_transport(monkeypatch):
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_MODE", "sandbox")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_ID", "client-id")
    monkeypatch.setattr(
        transport.settings, "BUILDIUM_API_CLIENT_SECRET", "property-group-secret"
    )
    monkeypatch.setattr(
        transport.settings, "BUILDIUM_API_SOURCE_ACCOUNT_REF", "sandbox-account-A"
    )


def test_buildium_transport_fetches_bounded_property_groups(monkeypatch):
    _configure_transport(monkeypatch)
    calls = []

    def fake_get(url, *, headers, params, timeout):
        calls.append((url, headers.copy(), params.copy(), timeout))
        return _Response(200, [_provider_record()])

    monkeypatch.setattr(transport.requests, "get", fake_get)
    result = transport.fetch_property_groups(
        expected_source_account_ref="sandbox-account-A"
    )
    assert result.records == [_provider_record()]
    assert result.request_count == 1
    assert calls[0][0] == "https://apisandbox.buildium.com/v1/propertygroups"
    assert calls[0][2] == {"offset": 0, "limit": 500}
    assert calls[0][1]["x-buildium-client-secret"] == "property-group-secret"


def test_buildium_api_property_group_maps_exact_existing_group_only(monkeypatch):
    db, engine = _session()
    try:
        admin = _platform_admin(db)
        org = _org(db)
        run = _run(db, org)
        prop, group = _target(db, run)

        def fetched(*, expected_source_account_ref):
            assert expected_source_account_ref == "sandbox-account-A"
            return BuildiumApiFetchResult(
                records=[_provider_record()],
                mode="sandbox",
                request_count=1,
            )

        monkeypatch.setattr(api, "fetch_property_groups", fetched)
        resolution = BuildiumPropertyGroupResolutionIn(
            source_id=4401,
            action="MATCH_EXISTING",
            target_property_group_id=group.id,
        )
        reviewed = api.api_dry_run_buildium_property_groups(
            run.id,
            BuildiumApiPropertyGroupDryRunIn(resolutions=[resolution]),
            db=db,
            current_user=admin,
        )
        assert reviewed.invalid == 0
        assert reviewed.reviewable == 1
        assert reviewed.rows[0].mapped["target_property_ids"] == [prop.id]
        assert reviewed.rows[0].mapped["candidate_property_group_id"] == group.id

        committed = api.api_commit_buildium_property_groups(
            run.id,
            BuildiumApiPropertyGroupCommitIn(
                fingerprint=reviewed.fingerprint,
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert committed.matched_existing == 1
        db.refresh(group)
        assert group.description == "LOCAL-DESCRIPTION-MUST-STAY"
        assert db.query(PropertyGroup).count() == 1
        assert db.query(PropertyGroupMembership).count() == 1

        mapping = (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "PROPERTY_GROUPS")
            .one()
        )
        assert mapping.target_entity == "PROPERTY_GROUP"
        assert mapping.target_id == group.id

        with pytest.raises(ValidationError):
            BuildiumApiPropertyGroupDryRunIn(records=[_provider_record()])
        with pytest.raises(ValidationError):
            BuildiumApiPropertyGroupCommitIn(
                fingerprint=reviewed.fingerprint,
                client_secret="secret",
            )

        audit = "\n".join(
            row.new_value or ""
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        assert "DO-NOT-PERSIST-PROVIDER-GROUP-DESCRIPTION" not in audit
        assert "DO-NOT-PERSIST-PROVIDER-CREATOR" not in audit
        assert '"raw_response_stored":false' in audit.lower()
        assert '"provider_description_stored":false' in audit.lower()
    finally:
        db.close()
        engine.dispose()


def test_buildium_api_property_group_fresh_fetch_and_dependency_state_fail_closed(monkeypatch):
    db, engine = _session()
    try:
        admin = _platform_admin(db)
        org = _org(db)
        run = _run(db, org)
        _, group = _target(db, run)
        state = {"description": "ORIGINAL"}

        def fetched(*, expected_source_account_ref):
            assert expected_source_account_ref == "sandbox-account-A"
            return BuildiumApiFetchResult(
                records=[_provider_record(Description=state["description"])],
                mode="sandbox",
                request_count=1,
            )

        monkeypatch.setattr(api, "fetch_property_groups", fetched)
        resolution = BuildiumPropertyGroupResolutionIn(
            source_id=4401,
            action="MATCH_EXISTING",
            target_property_group_id=group.id,
        )
        reviewed = api.api_dry_run_buildium_property_groups(
            run.id,
            BuildiumApiPropertyGroupDryRunIn(resolutions=[resolution]),
            db=db,
            current_user=admin,
        )

        group.name = "Changed After Review"
        group.name_key = "changed after review"
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_property_groups(
                run.id,
                BuildiumApiPropertyGroupCommitIn(
                    fingerprint=reviewed.fingerprint,
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert (
            "stale" in exc.value.detail.lower()
            or "changed" in exc.value.detail.lower()
            or "match" in exc.value.detail.lower()
        )
        assert (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "PROPERTY_GROUPS")
            .count()
            == 0
        )

        group.name = "Cleveland Portfolio"
        group.name_key = "cleveland portfolio"
        db.commit()
        state["description"] = "PROVIDER-DESCRIPTION-CHANGED-AFTER-REVIEW"
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_property_groups(
                run.id,
                BuildiumApiPropertyGroupCommitIn(
                    fingerprint=reviewed.fingerprint,
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "stale" in exc.value.detail.lower()
        assert db.query(PropertyGroupMembership).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_buildium_api_property_group_routes_and_transport_status(monkeypatch):
    from app.main import app

    db, engine = _session()
    try:
        admin = _platform_admin(db)
        monkeypatch.setattr(api, "transport_status", lambda: type(
            "TransportState",
            (),
            {"mode": "sandbox", "configured": True, "source_account_bound": True},
        )())
        status = api.get_buildium_transport_status(current_user=admin)
        assert "PROPERTY_GROUPS" in status.supported_resources

        paths = set(app.openapi()["paths"])
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/property-groups/api-dry-run"
            in paths
        )
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/property-groups/api-commit"
            in paths
        )
    finally:
        db.close()
        engine.dispose()
