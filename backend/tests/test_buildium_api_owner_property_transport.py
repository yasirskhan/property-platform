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
from app.models.property import Property, PropertyOwner, PropertyType
from app.models.user import Organization, User, UserRole
from app.routers import buildium_migrations as api
from app.schemas.buildium_migration import (
    BuildiumApiOwnerPropertyCommitIn,
    BuildiumApiOwnerPropertyDryRunIn,
    BuildiumOwnerPropertyResolutionIn,
)
from app.services.buildium_api_transport import BuildiumApiFetchResult


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _platform_admin(db):
    row = PlatformUser(
        email="buildium-api-owner-property-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Buildium",
        last_name="OwnerProperty",
        role=PlatformUserRole.PLATFORM_ADMIN,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _org(db):
    row = Organization(
        name="Buildium API Owner Property Target",
        slug="buildium-api-owner-property-target",
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
        "Id": 3001,
        "IsCompany": False,
        "IsActive": True,
        "FirstName": "Olivia",
        "LastName": "Owner",
        "Email": "DO-NOT-PERSIST-OWNER-EMAIL@example.com",
        "AlternateEmail": "DO-NOT-PERSIST-OWNER-ALT@example.com",
        "Comment": "DO-NOT-PERSIST-OWNER-COMMENT",
        "PropertyIds": [1001],
        "TaxInformation": {
            "TaxPayerId": "DO-NOT-PERSIST-TAX-ID",
            "TaxPayerName1": "DO-NOT-PERSIST-TAX-NAME",
            "IncludeIn1099": True,
        },
    }
    row.update(changes)
    return row


def _target(db, run):
    prop = Property(
        organization_id=run.organization_id,
        name="Owner Property Target",
        property_type=PropertyType.MULTI_FAMILY,
        address_line1="10 Lake Ave",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        country="United States",
        is_active=True,
    )
    owner = User(
        email="local-owner@example.com",
        hashed_password=hash_password("owner-password"),
        first_name="Local",
        last_name="Owner",
        role=UserRole.OWNER,
        organization_id=run.organization_id,
        is_active=True,
        is_verified=True,
    )
    db.add_all([prop, owner])
    db.flush()
    relationship = PropertyOwner(
        organization_id=run.organization_id,
        property_id=prop.id,
        user_id=owner.id,
        ownership_pct=Decimal("37.50"),
        is_primary=False,
        is_active=True,
    )
    db.add(relationship)
    db.flush()
    for resource, source_id, target_entity, target_id, fingerprint in (
        ("PROPERTIES", "1001", "PROPERTY", prop.id, "p" * 64),
        ("OWNERS", "3001", "OWNER_USER", owner.id, "o" * 64),
    ):
        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource=resource,
                source_id=source_id,
                target_entity=target_entity,
                target_id=target_id,
                source_fingerprint=fingerprint,
            )
        )
    db.commit()
    return prop, owner, relationship


def test_buildium_api_owner_property_reconciles_existing_relationship_only(monkeypatch):
    db, engine = _session()
    try:
        admin = _platform_admin(db)
        org = _org(db)
        run = _run(db, org)
        prop, owner, relationship = _target(db, run)

        def fetched(*, expected_source_account_ref):
            assert expected_source_account_ref == "sandbox-account-A"
            return BuildiumApiFetchResult(
                records=[_provider_record()],
                mode="sandbox",
                request_count=1,
            )

        monkeypatch.setattr(api, "fetch_rental_owners", fetched)
        resolution = BuildiumOwnerPropertyResolutionIn(
            source_owner_id=3001,
            source_property_id=1001,
            action="MATCH_EXISTING",
            target_property_owner_id=relationship.id,
        )
        reviewed = api.api_dry_run_buildium_owner_property_relationships(
            run.id,
            BuildiumApiOwnerPropertyDryRunIn(resolutions=[resolution]),
            db=db,
            current_user=admin,
        )
        assert reviewed.invalid == 0
        assert reviewed.reviewable == 1
        assert reviewed.rows[0].mapped["target_owner_user_id"] == owner.id
        assert reviewed.rows[0].mapped["target_property_id"] == prop.id

        committed = api.api_commit_buildium_owner_property_relationships(
            run.id,
            BuildiumApiOwnerPropertyCommitIn(
                fingerprint=reviewed.fingerprint,
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert committed.matched_existing == 1
        db.refresh(relationship)
        db.refresh(prop)
        assert relationship.ownership_pct == Decimal("37.50")
        assert relationship.is_primary is False
        assert prop.owner_id is None
        assert db.query(PropertyOwner).count() == 1

        mapping = (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "OWNER_PROPERTY_RELATIONSHIPS")
            .one()
        )
        assert mapping.source_id == "3001:1001"
        assert mapping.target_entity == "PROPERTY_OWNER_RELATIONSHIP"
        assert mapping.target_id == relationship.id

        with pytest.raises(ValidationError):
            BuildiumApiOwnerPropertyDryRunIn(records=[_provider_record()])
        with pytest.raises(ValidationError):
            BuildiumApiOwnerPropertyCommitIn(
                fingerprint=reviewed.fingerprint,
                client_secret="secret",
            )

        audit = "\n".join(
            row.new_value or ""
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        for secret in (
            "DO-NOT-PERSIST-OWNER-EMAIL",
            "DO-NOT-PERSIST-OWNER-ALT",
            "DO-NOT-PERSIST-OWNER-COMMENT",
            "DO-NOT-PERSIST-TAX-ID",
            "DO-NOT-PERSIST-TAX-NAME",
        ):
            assert secret not in audit
        assert '"raw_response_stored":false' in audit.lower()
        assert '"tax_information_stored":false' in audit.lower()
    finally:
        db.close()
        engine.dispose()


def test_buildium_api_owner_property_fresh_fetch_and_dependency_state_fail_closed(monkeypatch):
    db, engine = _session()
    try:
        admin = _platform_admin(db)
        org = _org(db)
        run = _run(db, org)
        _, _, relationship = _target(db, run)
        state = {"property_ids": [1001]}

        def fetched(*, expected_source_account_ref):
            assert expected_source_account_ref == "sandbox-account-A"
            return BuildiumApiFetchResult(
                records=[_provider_record(PropertyIds=list(state["property_ids"]))],
                mode="sandbox",
                request_count=1,
            )

        monkeypatch.setattr(api, "fetch_rental_owners", fetched)
        resolution = BuildiumOwnerPropertyResolutionIn(
            source_owner_id=3001,
            source_property_id=1001,
            action="MATCH_EXISTING",
            target_property_owner_id=relationship.id,
        )
        reviewed = api.api_dry_run_buildium_owner_property_relationships(
            run.id,
            BuildiumApiOwnerPropertyDryRunIn(resolutions=[resolution]),
            db=db,
            current_user=admin,
        )

        relationship.ownership_pct = Decimal("40.00")
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_owner_property_relationships(
                run.id,
                BuildiumApiOwnerPropertyCommitIn(
                    fingerprint=reviewed.fingerprint,
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "stale" in exc.value.detail.lower()
        assert (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "OWNER_PROPERTY_RELATIONSHIPS")
            .count()
            == 0
        )

        relationship.ownership_pct = Decimal("37.50")
        db.commit()
        state["property_ids"] = [1001, 1002]
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_owner_property_relationships(
                run.id,
                BuildiumApiOwnerPropertyCommitIn(
                    fingerprint=reviewed.fingerprint,
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "stale" in exc.value.detail.lower()
        assert db.query(PropertyOwner).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_buildium_api_owner_property_routes_and_transport_status(monkeypatch):
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
        assert "OWNER_PROPERTY_RELATIONSHIPS" in status.supported_resources

        paths = set(app.openapi()["paths"])
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/owner-property-relationships/api-dry-run"
            in paths
        )
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/owner-property-relationships/api-commit"
            in paths
        )
    finally:
        db.close()
        engine.dispose()
