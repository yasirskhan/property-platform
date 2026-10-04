from __future__ import annotations

import json
from datetime import date, datetime

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
from app.models.property import Property, PropertyOwner, PropertyType, Unit
from app.models.lease import Lease, LeaseStatus
from app.models.charge import Charge
from app.models.gl_transaction import GLTransaction
from app.models.gl_account import GLAccount
from app.models.user import Organization, User, UserRole
from app.models.vendor import Vendor
from app.models.work_order import WorkOrder, WorkOrderStatus
from app.models.bill import Bill
from app.models.bill_line import BillLine
from app.routers import buildium_migrations as api
from app.schemas.buildium_migration import (
    BuildiumMigrationRunCreateIn,
    BuildiumPropertyCommitIn,
    BuildiumPropertyDryRunIn,
    BuildiumPropertyResolutionIn,
    BuildiumUnitCommitIn,
    BuildiumUnitDryRunIn,
    BuildiumUnitResolutionIn,
    BuildiumOwnerCommitIn,
    BuildiumOwnerDryRunIn,
    BuildiumOwnerResolutionIn,
    BuildiumVendorCommitIn,
    BuildiumVendorDryRunIn,
    BuildiumVendorResolutionIn,
    BuildiumTenantCommitIn,
    BuildiumTenantDryRunIn,
    BuildiumTenantResolutionIn,
    BuildiumLeaseCommitIn,
    BuildiumLeaseDryRunIn,
    BuildiumLeaseResolutionIn,
    BuildiumGLAccountCommitIn,
    BuildiumGLAccountDryRunIn,
    BuildiumGLAccountResolutionIn,
    BuildiumWorkOrderCommitIn,
    BuildiumWorkOrderDryRunIn,
    BuildiumWorkOrderResolutionIn,
    BuildiumBillCommitIn,
    BuildiumBillDryRunIn,
    BuildiumBillResolutionIn,
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



def _target_property(db, org, *, name="Lake Apartments", address="10 Lake Ave"):
    row = Property(
        organization_id=org.id,
        name=name,
        property_type=PropertyType.MULTI_FAMILY,
        address_line1=address,
        address_line2="Building A",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        country="United States",
        year_built=1975,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_buildium_match_existing_is_explicit_scoped_revalidated_and_replayed():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Review Target")
        foreign_org = _org(db, name="Foreign Target")
        existing = _target_property(db, org)
        foreign = _target_property(db, foreign_org, name="Foreign Lake")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="review-match",
            ),
            db=db,
            current_user=admin,
        )

        with pytest.raises(HTTPException) as exc:
            api.dry_run_buildium_properties(
                run.id,
                BuildiumPropertyDryRunIn(
                    records=[_record()],
                    resolutions=[
                        BuildiumPropertyResolutionIn(
                            source_id=1001,
                            action="MATCH_EXISTING",
                            target_property_id=foreign.id,
                        )
                    ],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(PlatformMigrationItem).count() == 0

        payload = BuildiumPropertyDryRunIn(
            records=[_record()],
            resolutions=[
                BuildiumPropertyResolutionIn(
                    source_id=1001,
                    action="MATCH_EXISTING",
                    target_property_id=existing.id,
                )
            ],
        )
        preview = api.dry_run_buildium_properties(
            run.id,
            payload,
            db=db,
            current_user=admin,
        )
        assert preview.importable == 1
        assert preview.rows[0].resolution_action == "MATCH_EXISTING"
        assert preview.rows[0].resolution_target_property_id == existing.id

        existing.deleted_at = datetime.utcnow()
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_properties(
                run.id,
                BuildiumPropertyCommitIn(
                    fingerprint=preview.fingerprint,
                    records=payload.records,
                    resolutions=payload.resolutions,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "no longer" in exc.value.detail or "not an active" in exc.value.detail
        assert db.query(PlatformMigrationItem).count() == 0

        existing.deleted_at = None
        db.commit()
        first = api.commit_buildium_properties(
            run.id,
            BuildiumPropertyCommitIn(
                fingerprint=preview.fingerprint,
                records=payload.records,
                resolutions=payload.resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert first.committed == 0
        assert first.matched_existing == 1
        assert first.replayed is False
        assert db.query(Property).filter(Property.organization_id == org.id).count() == 1
        db.refresh(existing)
        assert existing.year_built == 1975

        mapping = db.query(PlatformMigrationItem).one()
        assert mapping.provider == "BUILDIUM"
        assert mapping.source_id == "1001"
        assert mapping.target_id == existing.id

        second = api.commit_buildium_properties(
            run.id,
            BuildiumPropertyCommitIn(
                fingerprint=preview.fingerprint,
                records=payload.records,
                resolutions=payload.resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert second.replayed is True
        assert second.committed == 0
        assert db.query(PlatformMigrationItem).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_buildium_review_decision_is_fingerprint_bound_and_cannot_remap():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Fingerprint Target")
        first_target = _target_property(db, org)
        second_target = _target_property(
            db,
            org,
            name="Other Reviewed Property",
            address="20 Lake Ave",
        )
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="review-fingerprint",
            ),
            db=db,
            current_user=admin,
        )

        reviewed = BuildiumPropertyDryRunIn(
            records=[_record()],
            resolutions=[
                BuildiumPropertyResolutionIn(
                    source_id=1001,
                    action="MATCH_EXISTING",
                    target_property_id=first_target.id,
                )
            ],
        )
        preview = api.dry_run_buildium_properties(
            run.id,
            reviewed,
            db=db,
            current_user=admin,
        )

        changed_resolution = [
            BuildiumPropertyResolutionIn(
                source_id=1001,
                action="MATCH_EXISTING",
                target_property_id=second_target.id,
            )
        ]
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_properties(
                run.id,
                BuildiumPropertyCommitIn(
                    fingerprint=preview.fingerprint,
                    records=reviewed.records,
                    resolutions=changed_resolution,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "fingerprint" in exc.value.detail
        assert db.query(PlatformMigrationItem).count() == 0

        committed = api.commit_buildium_properties(
            run.id,
            BuildiumPropertyCommitIn(
                fingerprint=preview.fingerprint,
                records=reviewed.records,
                resolutions=reviewed.resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert committed.matched_existing == 1

        with pytest.raises(HTTPException) as exc:
            api.dry_run_buildium_properties(
                run.id,
                BuildiumPropertyDryRunIn(
                    records=[_record()],
                    resolutions=[
                        BuildiumPropertyResolutionIn(
                            source_id=1001,
                            action="CREATE_NEW",
                        )
                    ],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "durable mapping" in exc.value.detail
        assert db.query(PlatformMigrationItem).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_buildium_review_allows_deliberate_create_new_and_explicit_skip_only():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Create Skip Target")
        _target_property(db, org)
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="review-create-skip",
            ),
            db=db,
            current_user=admin,
        )
        records = [
            _record(),
            _record(
                Id=1002,
                Name="Skip Me",
                Address={
                    "AddressLine1": "30 Lake Ave",
                    "AddressLine2": "",
                    "AddressLine3": "",
                    "City": "Cleveland",
                    "State": "OH",
                    "PostalCode": "44113",
                    "Country": "United States",
                },
            ),
        ]
        resolutions = [
            BuildiumPropertyResolutionIn(source_id=1001, action="CREATE_NEW"),
            BuildiumPropertyResolutionIn(source_id=1002, action="SKIP"),
        ]
        preview = api.dry_run_buildium_properties(
            run.id,
            BuildiumPropertyDryRunIn(
                records=records,
                resolutions=resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert preview.importable == 1
        assert preview.skipped_review == 1
        assert preview.rows[0].resolution_action == "CREATE_NEW"
        assert preview.rows[1].resolution_action == "SKIP"
        assert preview.rows[1].importable is False

        result = api.commit_buildium_properties(
            run.id,
            BuildiumPropertyCommitIn(
                fingerprint=preview.fingerprint,
                records=records,
                resolutions=resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert result.committed == 1
        assert result.matched_existing == 0
        assert result.skipped_review == 1
        assert db.query(Property).filter(Property.organization_id == org.id).count() == 2
        assert (
            db.query(Property)
            .filter(Property.organization_id == org.id, Property.name == "Skip Me")
            .count()
            == 0
        )
        mappings = db.query(PlatformMigrationItem).all()
        assert len(mappings) == 1
        assert mappings[0].source_id == "1001"
    finally:
        db.close()
        engine.dispose()


def test_buildium_review_rejects_create_new_without_possible_match_and_invalid_source_scope():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Review Validation Target")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="review-invalid",
            ),
            db=db,
            current_user=admin,
        )

        with pytest.raises(HTTPException) as exc:
            api.dry_run_buildium_properties(
                run.id,
                BuildiumPropertyDryRunIn(
                    records=[_record(Name="Unique New Property")],
                    resolutions=[
                        BuildiumPropertyResolutionIn(
                            source_id=1001,
                            action="CREATE_NEW",
                        )
                    ],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "only valid" in exc.value.detail

        with pytest.raises(HTTPException) as exc:
            api.dry_run_buildium_properties(
                run.id,
                BuildiumPropertyDryRunIn(
                    records=[_record()],
                    resolutions=[
                        BuildiumPropertyResolutionIn(
                            source_id=9999,
                            action="SKIP",
                        )
                    ],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "otherwise valid" in exc.value.detail
        assert db.query(Property).count() == 0
        assert db.query(PlatformMigrationItem).count() == 0
    finally:
        db.close()
        engine.dispose()



def test_buildium_skip_only_commit_records_reviewed_noop_and_replays():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Skip Only Target")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="skip-only",
            ),
            db=db,
            current_user=admin,
        )
        records = [_record(Name="Reviewed Skip")]
        resolutions = [
            BuildiumPropertyResolutionIn(source_id=1001, action="SKIP")
        ]
        preview = api.dry_run_buildium_properties(
            run.id,
            BuildiumPropertyDryRunIn(
                records=records,
                resolutions=resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert preview.importable == 0
        assert preview.skipped_review == 1

        first = api.commit_buildium_properties(
            run.id,
            BuildiumPropertyCommitIn(
                fingerprint=preview.fingerprint,
                records=records,
                resolutions=resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert first.replayed is False
        assert first.committed == 0
        assert first.skipped_review == 1
        assert db.get(PlatformMigrationRun, run.id).status == "PROPERTIES_REVIEWED"
        assert db.query(Property).count() == 0
        assert db.query(PlatformMigrationItem).count() == 0

        second = api.commit_buildium_properties(
            run.id,
            BuildiumPropertyCommitIn(
                fingerprint=preview.fingerprint,
                records=records,
                resolutions=resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert second.replayed is True
        assert db.query(Property).count() == 0
        assert db.query(PlatformMigrationItem).count() == 0
    finally:
        db.close()
        engine.dispose()


def _unit_record(**changes):
    record = {
        "Id": 2001,
        "PropertyId": 1001,
        "BuildingName": "Lake Apartments",
        "UnitNumber": "1A",
        "Description": "",
        "MarketRent": 1250,
        "Address": {
            "AddressLine1": "10 Lake Ave",
            "AddressLine2": "Building A",
            "AddressLine3": "",
            "City": "Cleveland",
            "State": "OH",
            "PostalCode": "44113",
            "Country": "United States",
        },
        "UnitBedrooms": "TwoBed",
        "UnitBathrooms": "OnePointFiveBath",
        "UnitSize": 900,
        "IsUnitListed": True,
        "IsUnitOccupied": True,
    }
    record.update(changes)
    return record


def _buildium_property_mapping(db, run, org, *, source_id="1001", name="Lake Apartments"):
    target = Property(
        organization_id=org.id,
        name=name,
        property_type=PropertyType.MULTI_FAMILY,
        address_line1="10 Lake Ave",
        address_line2="Building A",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        country="United States",
        is_active=True,
    )
    db.add(target)
    db.flush()
    mapping = PlatformMigrationItem(
        run_id=run.id,
        organization_id=org.id,
        provider="BUILDIUM",
        resource="PROPERTIES",
        source_id=str(source_id),
        target_entity="PROPERTY",
        target_id=target.id,
        source_fingerprint="a" * 64,
        created_by_platform_user_id=run.created_by_platform_user_id,
    )
    db.add(mapping)
    db.commit()
    db.refresh(target)
    db.refresh(mapping)
    return target, mapping


def test_buildium_units_require_durable_property_mapping_and_never_infer_occupancy():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Unit Foundation")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="unit-foundation",
            ),
            db=db,
            current_user=admin,
        )

        blocked = api.dry_run_buildium_units(
            run.id,
            BuildiumUnitDryRunIn(records=[_unit_record()]),
            db=db,
            current_user=admin,
        )
        assert blocked.invalid == 1
        assert blocked.importable == 0
        assert "no durable Property mapping" in blocked.rows[0].reason
        assert db.query(Unit).count() == 0

        target_property, _ = _buildium_property_mapping(db, run, org)
        preview = api.dry_run_buildium_units(
            run.id,
            BuildiumUnitDryRunIn(records=[_unit_record()]),
            db=db,
            current_user=admin,
        )
        assert preview.invalid == 0
        assert preview.importable == 1
        assert preview.rows[0].mapped["target_property_id"] == target_property.id
        assert preview.rows[0].mapped["unit_number"] == "1A"
        assert preview.rows[0].mapped["bedrooms"] == 2
        assert str(preview.rows[0].mapped["bathrooms"]) == "1.5"
        assert str(preview.rows[0].mapped["monthly_rent"]) == "1250.00"
        assert preview.rows[0].mapped["is_available"] is None
        assert any("IsUnitOccupied is source evidence only" in x for x in preview.rows[0].warnings)
        assert db.query(Unit).count() == 0
        assert db.query(Lease).count() == 0
        assert db.query(Charge).count() == 0
        assert db.query(GLTransaction).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_buildium_unit_commit_is_fingerprint_bound_replay_safe_and_visible():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Unit Commit")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="unit-commit",
            ),
            db=db,
            current_user=admin,
        )
        target_property, _ = _buildium_property_mapping(db, run, org)
        records = [_unit_record()]
        preview = api.dry_run_buildium_units(
            run.id,
            BuildiumUnitDryRunIn(records=records),
            db=db,
            current_user=admin,
        )

        changed = [_unit_record(MarketRent=1300)]
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_units(
                run.id,
                BuildiumUnitCommitIn(
                    fingerprint=preview.fingerprint,
                    records=changed,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(Unit).count() == 0

        first = api.commit_buildium_units(
            run.id,
            BuildiumUnitCommitIn(
                fingerprint=preview.fingerprint,
                records=records,
            ),
            db=db,
            current_user=admin,
        )
        assert first.committed == 1
        assert first.replayed is False
        unit = db.query(Unit).one()
        assert unit.property_id == target_property.id
        assert unit.unit_number == "1A"
        assert unit.is_available is None
        assert unit.is_listed is True

        second = api.commit_buildium_units(
            run.id,
            BuildiumUnitCommitIn(
                fingerprint=preview.fingerprint,
                records=records,
            ),
            db=db,
            current_user=admin,
        )
        assert second.replayed is True
        assert second.committed == 0
        assert db.query(Unit).count() == 1

        response = Response()
        items = api.list_migration_items(
            run.id,
            response=response,
            resource="units",
            limit=200,
            db=db,
            current_user=admin,
        )
        assert len(items) == 1
        assert items[0].provider == "BUILDIUM"
        assert items[0].target_entity == "UNIT"
        assert items[0].target_exists is True
        assert items[0].target_label == "1A"
        assert response.headers["cache-control"] == "no-store"
    finally:
        db.close()
        engine.dispose()


def test_buildium_unit_possible_match_requires_explicit_review_without_overwrite():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Unit Match")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="unit-match",
            ),
            db=db,
            current_user=admin,
        )
        target_property, _ = _buildium_property_mapping(db, run, org)
        existing = Unit(
            property_id=target_property.id,
            unit_number="1A",
            bedrooms=3,
            bathrooms=2,
            square_feet=1100,
            monthly_rent=1500,
            is_available=False,
            is_listed=False,
            is_active=True,
        )
        db.add(existing)
        db.commit()
        existing_id = existing.id

        preview = api.dry_run_buildium_units(
            run.id,
            BuildiumUnitDryRunIn(records=[_unit_record()]),
            db=db,
            current_user=admin,
        )
        assert any("Possible existing target Unit match" in x for x in preview.rows[0].warnings)

        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_units(
                run.id,
                BuildiumUnitCommitIn(
                    fingerprint=preview.fingerprint,
                    records=[_unit_record()],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(Unit).count() == 1

        reviewed = BuildiumUnitDryRunIn(
            records=[_unit_record()],
            resolutions=[
                BuildiumUnitResolutionIn(
                    source_id=2001,
                    action="MATCH_EXISTING",
                    target_unit_id=existing_id,
                )
            ],
        )
        reviewed_preview = api.dry_run_buildium_units(
            run.id,
            reviewed,
            db=db,
            current_user=admin,
        )
        committed = api.commit_buildium_units(
            run.id,
            BuildiumUnitCommitIn(
                fingerprint=reviewed_preview.fingerprint,
                records=reviewed.records,
                resolutions=reviewed.resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert committed.committed == 0
        assert committed.matched_existing == 1
        db.refresh(existing)
        assert existing.bedrooms == 3
        assert str(existing.monthly_rent) == "1500.00"
        assert existing.is_available is False
        assert db.query(Unit).count() == 1
        mapping = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "UNITS"
        ).one()
        assert mapping.target_id == existing_id
    finally:
        db.close()
        engine.dispose()


def test_buildium_unit_property_mapping_state_invalidates_stale_preview():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Unit Mapping Fingerprint")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="unit-map-fingerprint",
            ),
            db=db,
            current_user=admin,
        )
        target_property, mapping = _buildium_property_mapping(db, run, org)
        records = [_unit_record()]
        preview = api.dry_run_buildium_units(
            run.id,
            BuildiumUnitDryRunIn(records=records),
            db=db,
            current_user=admin,
        )

        mapping.source_fingerprint = "b" * 64
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_units(
                run.id,
                BuildiumUnitCommitIn(
                    fingerprint=preview.fingerprint,
                    records=records,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "Property mapping state" in exc.value.detail
        assert db.query(Unit).count() == 0

        refreshed = api.dry_run_buildium_units(
            run.id,
            BuildiumUnitDryRunIn(records=records),
            db=db,
            current_user=admin,
        )
        target_property.deleted_at = datetime.utcnow()
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_units(
                run.id,
                BuildiumUnitCommitIn(
                    fingerprint=refreshed.fingerprint,
                    records=records,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(Unit).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_buildium_unit_review_rejects_cross_property_and_lossy_source_contracts():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Unit Safety")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="unit-safety",
            ),
            db=db,
            current_user=admin,
        )
        mapped_property, _ = _buildium_property_mapping(db, run, org)
        other_property = Property(
            organization_id=org.id,
            name="Other",
            property_type=PropertyType.MULTI_FAMILY,
            address_line1="99 Other Rd",
            city="Cleveland",
            state="OH",
            zip_code="44114",
            country="United States",
            is_active=True,
        )
        db.add(other_property)
        db.flush()
        foreign_unit = Unit(
            property_id=other_property.id,
            unit_number="1A",
            bedrooms=2,
            bathrooms=1.5,
            monthly_rent=1200,
            is_active=True,
        )
        db.add(foreign_unit)
        db.commit()

        with pytest.raises(HTTPException) as exc:
            api.dry_run_buildium_units(
                run.id,
                BuildiumUnitDryRunIn(
                    records=[_unit_record()],
                    resolutions=[
                        BuildiumUnitResolutionIn(
                            source_id=2001,
                            action="MATCH_EXISTING",
                            target_unit_id=foreign_unit.id,
                        )
                    ],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "not active under the mapped Property" in exc.value.detail

        lossy = [
            _unit_record(Description="Private patio"),
            _unit_record(Id=2002, UnitNumber="2A", UnitBedrooms="NotSet"),
            _unit_record(
                Id=2003,
                UnitNumber="3A",
                Address={
                    **_unit_record()["Address"],
                    "AddressLine3": "Rear building",
                },
            ),
        ]
        preview = api.dry_run_buildium_units(
            run.id,
            BuildiumUnitDryRunIn(records=lossy),
            db=db,
            current_user=admin,
        )
        assert preview.invalid == 3
        assert preview.importable == 0
        reasons = " ".join(row.reason or "" for row in preview.rows)
        assert "Description is populated" in reasons
        assert "UnitBedrooms is not set" in reasons
        assert "Address.AddressLine3 is populated" in reasons
        assert db.query(Unit).count() == 1
        assert db.query(Lease).count() == 0
        assert db.query(Charge).count() == 0
        assert db.query(GLTransaction).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_buildium_unit_routes_are_exposed():
    from app.main import app

    paths = set(app.openapi()["paths"])
    assert "/api/platform/migrations/buildium/runs/{run_id}/units/dry-run" in paths
    assert "/api/platform/migrations/buildium/runs/{run_id}/units/commit" in paths


def _owner_record(**changes):
    record = {
        "Id": 3001,
        "IsCompany": False,
        "IsActive": True,
        "FirstName": "Olivia",
        "LastName": "Owner",
        "CompanyName": None,
        "Email": "olivia.owner@example.com",
        "AlternateEmail": "alternate@example.com",
        "PhoneNumbers": [{"Number": "2165550100", "Type": "Mobile"}],
        "Address": {
            "AddressLine1": "55 Owner Way",
            "AddressLine2": "",
            "AddressLine3": "",
            "City": "Cleveland",
            "State": "OH",
            "PostalCode": "44113",
            "Country": "United States",
        },
        "PropertyIds": [1001],
        "TaxInformation": {
            "TaxPayerId": "DO-NOT-STORE",
            "TaxPayerName1": "Olivia Owner",
            "IncludeIn1099": True,
        },
    }
    record.update(changes)
    return record


def _customer_owner(db, org, *, email="olivia.owner@example.com"):
    row = User(
        email=email,
        hashed_password=hash_password("owner-password"),
        first_name="Olivia",
        last_name="Owner",
        role=UserRole.OWNER,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_buildium_owner_mapping_requires_property_reconciliation_and_explicit_existing_owner():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Owner Mapping")
        target_owner = _customer_owner(db, org)
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="owner-map",
            ),
            db=db,
            current_user=admin,
        )

        missing_property = api.dry_run_buildium_owners(
            run.id,
            BuildiumOwnerDryRunIn(records=[_owner_record()]),
            db=db,
            current_user=admin,
        )
        assert missing_property.invalid == 1
        assert "no durable Property mapping" in missing_property.rows[0].reason
        assert db.query(PropertyOwner).count() == 0

        target_property, _ = _buildium_property_mapping(db, run, org)
        preview = api.dry_run_buildium_owners(
            run.id,
            BuildiumOwnerDryRunIn(records=[_owner_record()]),
            db=db,
            current_user=admin,
        )
        assert preview.invalid == 0
        assert preview.reviewable == 1
        assert preview.rows[0].mapped["target_property_ids"] == [target_property.id]
        assert preview.rows[0].mapped["email"] == target_owner.email
        assert any("explicit MATCH_EXISTING" in x for x in preview.rows[0].warnings)
        assert db.query(PropertyOwner).count() == 0

        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_owners(
                run.id,
                BuildiumOwnerCommitIn(
                    fingerprint=preview.fingerprint,
                    records=[_owner_record()],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "OWNERS"
        ).count() == 0

        reviewed = BuildiumOwnerDryRunIn(
            records=[_owner_record()],
            resolutions=[
                BuildiumOwnerResolutionIn(
                    source_id=3001,
                    action="MATCH_EXISTING",
                    target_owner_user_id=target_owner.id,
                )
            ],
        )
        reviewed_preview = api.dry_run_buildium_owners(
            run.id, reviewed, db=db, current_user=admin
        )
        first = api.commit_buildium_owners(
            run.id,
            BuildiumOwnerCommitIn(
                fingerprint=reviewed_preview.fingerprint,
                records=reviewed.records,
                resolutions=reviewed.resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert first.matched_existing == 1
        assert first.replayed is False
        assert db.query(User).filter(User.role == UserRole.OWNER).count() == 1
        assert db.query(PropertyOwner).count() == 0
        mapping = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "OWNERS"
        ).one()
        assert mapping.target_entity == "OWNER_USER"
        assert mapping.target_id == target_owner.id

        second = api.commit_buildium_owners(
            run.id,
            BuildiumOwnerCommitIn(
                fingerprint=reviewed_preview.fingerprint,
                records=reviewed.records,
                resolutions=reviewed.resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert second.replayed is True
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "OWNERS"
        ).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_buildium_owner_mapping_rejects_cross_org_stale_email_and_sensitive_audit():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Owner Safety")
        foreign_org = _org(db, name="Owner Foreign")
        owner = _customer_owner(db, org)
        foreign_owner = _customer_owner(
            db, foreign_org, email="foreign.owner@example.com"
        )
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="owner-safety",
            ),
            db=db,
            current_user=admin,
        )
        _buildium_property_mapping(db, run, org)

        with pytest.raises(HTTPException) as exc:
            api.dry_run_buildium_owners(
                run.id,
                BuildiumOwnerDryRunIn(
                    records=[_owner_record()],
                    resolutions=[
                        BuildiumOwnerResolutionIn(
                            source_id=3001,
                            action="MATCH_EXISTING",
                            target_owner_user_id=foreign_owner.id,
                        )
                    ],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        payload = BuildiumOwnerDryRunIn(
            records=[_owner_record()],
            resolutions=[
                BuildiumOwnerResolutionIn(
                    source_id=3001,
                    action="MATCH_EXISTING",
                    target_owner_user_id=owner.id,
                )
            ],
        )
        preview = api.dry_run_buildium_owners(
            run.id, payload, db=db, current_user=admin
        )
        owner.email = "changed.owner@example.com"
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_owners(
                run.id,
                BuildiumOwnerCommitIn(
                    fingerprint=preview.fingerprint,
                    records=payload.records,
                    resolutions=payload.resolutions,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "OWNERS"
        ).count() == 0
        assert db.query(PropertyOwner).count() == 0

        audit_text = "\n".join(
            row.new_value or ""
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        assert "DO-NOT-STORE" not in audit_text
        assert "olivia.owner@example.com" not in audit_text
    finally:
        db.close()
        engine.dispose()


def test_buildium_owner_skip_records_reviewed_noop_without_login_or_ownership_creation():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Owner Skip")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="owner-skip",
            ),
            db=db,
            current_user=admin,
        )
        _buildium_property_mapping(db, run, org)
        records = [_owner_record(Email="skip.owner@example.com")]
        resolutions = [BuildiumOwnerResolutionIn(source_id=3001, action="SKIP")]
        preview = api.dry_run_buildium_owners(
            run.id,
            BuildiumOwnerDryRunIn(records=records, resolutions=resolutions),
            db=db,
            current_user=admin,
        )
        assert preview.reviewable == 0
        assert preview.skipped_review == 1
        result = api.commit_buildium_owners(
            run.id,
            BuildiumOwnerCommitIn(
                fingerprint=preview.fingerprint,
                records=records,
                resolutions=resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert result.matched_existing == 0
        assert result.replayed is False
        assert db.get(PlatformMigrationRun, run.id).status == "OWNERS_REVIEWED"
        assert db.query(User).filter(User.role == UserRole.OWNER).count() == 0
        assert db.query(PropertyOwner).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_buildium_owner_routes_are_exposed():
    from app.main import app

    paths = set(app.openapi()["paths"])
    assert "/api/platform/migrations/buildium/runs/{run_id}/owners/dry-run" in paths
    assert "/api/platform/migrations/buildium/runs/{run_id}/owners/commit" in paths


def _vendor_record(**changes):
    record = {
        "Id": 4001,
        "FirstName": "",
        "LastName": "",
        "CompanyName": "Lake Plumbing",
        "PrimaryEmail": "service@lakeplumbing.example.com",
        "AlternateEmail": "",
        "PhoneNumbers": [{"Number": "2165550199", "Type": "Work"}],
        "Website": "https://example.com",
        "IsCompany": True,
    }
    record.update(changes)
    return record


def _target_vendor(db, org, *, company_name="Lake Plumbing", email="service@lakeplumbing.example.com"):
    row = Vendor(
        organization_id=org.id,
        company_name=company_name,
        business_email=email,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_buildium_vendor_mapping_requires_explicit_existing_target_and_replays():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Vendor Mapping")
        vendor = _target_vendor(db, org)
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="vendor-map",
            ),
            db=db,
            current_user=admin,
        )
        preview = api.dry_run_buildium_vendors(
            run.id,
            BuildiumVendorDryRunIn(records=[_vendor_record()]),
            db=db,
            current_user=admin,
        )
        assert preview.invalid == 0
        assert preview.reviewable == 1
        assert any("explicit MATCH_EXISTING" in warning for warning in preview.rows[0].warnings)

        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_vendors(
                run.id,
                BuildiumVendorCommitIn(
                    fingerprint=preview.fingerprint,
                    records=[_vendor_record()],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "VENDORS"
        ).count() == 0

        reviewed = BuildiumVendorDryRunIn(
            records=[_vendor_record()],
            resolutions=[
                BuildiumVendorResolutionIn(
                    source_id=4001,
                    action="MATCH_EXISTING",
                    target_vendor_id=vendor.id,
                )
            ],
        )
        reviewed_preview = api.dry_run_buildium_vendors(
            run.id, reviewed, db=db, current_user=admin
        )
        first = api.commit_buildium_vendors(
            run.id,
            BuildiumVendorCommitIn(
                fingerprint=reviewed_preview.fingerprint,
                records=reviewed.records,
                resolutions=reviewed.resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert first.matched_existing == 1
        assert first.replayed is False
        mapping = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "VENDORS"
        ).one()
        assert mapping.target_entity == "VENDOR"
        assert mapping.target_id == vendor.id
        assert db.query(Vendor).count() == 1

        second = api.commit_buildium_vendors(
            run.id,
            BuildiumVendorCommitIn(
                fingerprint=reviewed_preview.fingerprint,
                records=reviewed.records,
                resolutions=reviewed.resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert second.replayed is True
        assert db.query(Vendor).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_buildium_vendor_mapping_rejects_cross_org_and_stale_identity():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Vendor Safety")
        foreign_org = _org(db, name="Vendor Foreign")
        vendor = _target_vendor(db, org)
        foreign_vendor = _target_vendor(
            db,
            foreign_org,
            company_name="Foreign Plumbing",
            email="foreign@example.com",
        )
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="vendor-safety",
            ),
            db=db,
            current_user=admin,
        )
        with pytest.raises(HTTPException) as exc:
            api.dry_run_buildium_vendors(
                run.id,
                BuildiumVendorDryRunIn(
                    records=[_vendor_record()],
                    resolutions=[
                        BuildiumVendorResolutionIn(
                            source_id=4001,
                            action="MATCH_EXISTING",
                            target_vendor_id=foreign_vendor.id,
                        )
                    ],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        payload = BuildiumVendorDryRunIn(
            records=[_vendor_record()],
            resolutions=[
                BuildiumVendorResolutionIn(
                    source_id=4001,
                    action="MATCH_EXISTING",
                    target_vendor_id=vendor.id,
                )
            ],
        )
        preview = api.dry_run_buildium_vendors(
            run.id, payload, db=db, current_user=admin
        )
        vendor.company_name = "Changed Vendor"
        vendor.business_email = "changed@example.com"
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_vendors(
                run.id,
                BuildiumVendorCommitIn(
                    fingerprint=preview.fingerprint,
                    records=payload.records,
                    resolutions=payload.resolutions,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "VENDORS"
        ).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_buildium_vendor_individual_and_skip_do_not_create_vendor_or_relationships():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Vendor Skip")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="vendor-skip",
            ),
            db=db,
            current_user=admin,
        )
        record = _vendor_record(
            Id=4002,
            IsCompany=False,
            CompanyName="",
            FirstName="Pat",
            LastName="Plumber",
            PrimaryEmail="pat@example.com",
        )
        resolutions = [BuildiumVendorResolutionIn(source_id=4002, action="SKIP")]
        preview = api.dry_run_buildium_vendors(
            run.id,
            BuildiumVendorDryRunIn(records=[record], resolutions=resolutions),
            db=db,
            current_user=admin,
        )
        assert preview.skipped_review == 1
        assert any(
            "individual" in warning.lower()
            for warning in preview.rows[0].warnings
        )
        result = api.commit_buildium_vendors(
            run.id,
            BuildiumVendorCommitIn(
                fingerprint=preview.fingerprint,
                records=[record],
                resolutions=resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert result.replayed is False
        assert result.matched_existing == 0
        assert db.query(Vendor).count() == 0
        assert db.get(PlatformMigrationRun, run.id).status == "VENDORS_REVIEWED"
    finally:
        db.close()
        engine.dispose()


def test_buildium_vendor_routes_and_item_visibility():
    from app.main import app

    paths = set(app.openapi()["paths"])
    assert "/api/platform/migrations/buildium/runs/{run_id}/vendors/dry-run" in paths
    assert "/api/platform/migrations/buildium/runs/{run_id}/vendors/commit" in paths


def _tenant_record(**changes):
    record = {
        "Id": 5001,
        "UserLeaseId": 9001,
        "FirstName": "Tina",
        "LastName": "Tenant",
        "Email": "tina.tenant@example.com",
        "AlternateEmail": "alternate.tenant@example.com",
        "PhoneNumbers": [{"Number": "2165550188", "Type": "Mobile"}],
        "PrimaryAddress": {
            "AddressLine1": "10 Lake Ave",
            "AddressLine2": "1A",
            "AddressLine3": "",
            "City": "Cleveland",
            "State": "OH",
            "PostalCode": "44113",
            "Country": "United States",
        },
        "TaxId": "DO-NOT-STORE",
        "MoveInDate": "2026-01-01",
    }
    record.update(changes)
    return record


def _customer_tenant(db, org, *, email="tina.tenant@example.com"):
    row = User(
        email=email,
        hashed_password=hash_password("tenant-password"),
        first_name="Tina",
        last_name="Tenant",
        role=UserRole.TENANT,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_buildium_tenant_maps_existing_identity_only_and_preserves_membership_as_evidence():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Tenant Mapping")
        tenant = _customer_tenant(db, org)
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="tenant-map",
            ),
            db=db,
            current_user=admin,
        )

        preview = api.dry_run_buildium_tenants(
            run.id,
            BuildiumTenantDryRunIn(records=[_tenant_record()]),
            db=db,
            current_user=admin,
        )
        assert preview.invalid == 0
        assert preview.reviewable == 1
        assert preview.rows[0].mapped["email"] == tenant.email
        assert preview.rows[0].mapped["user_lease_id"] == "9001"
        assert any("creates no Lease" in x for x in preview.rows[0].warnings)
        assert db.query(Lease).count() == 0

        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_tenants(
                run.id,
                BuildiumTenantCommitIn(
                    fingerprint=preview.fingerprint,
                    records=[_tenant_record()],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        reviewed = BuildiumTenantDryRunIn(
            records=[_tenant_record()],
            resolutions=[
                BuildiumTenantResolutionIn(
                    source_id=5001,
                    action="MATCH_EXISTING",
                    target_tenant_user_id=tenant.id,
                )
            ],
        )
        reviewed_preview = api.dry_run_buildium_tenants(
            run.id, reviewed, db=db, current_user=admin
        )
        first = api.commit_buildium_tenants(
            run.id,
            BuildiumTenantCommitIn(
                fingerprint=reviewed_preview.fingerprint,
                records=reviewed.records,
                resolutions=reviewed.resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert first.matched_existing == 1
        assert first.replayed is False
        mapping = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "TENANTS"
        ).one()
        assert mapping.target_entity == "TENANT_USER"
        assert mapping.target_id == tenant.id
        assert db.query(User).filter(User.role == UserRole.TENANT).count() == 1
        assert db.query(Lease).count() == 0
        assert db.query(Charge).count() == 0
        assert db.query(GLTransaction).count() == 0

        replay = api.commit_buildium_tenants(
            run.id,
            BuildiumTenantCommitIn(
                fingerprint=reviewed_preview.fingerprint,
                records=reviewed.records,
                resolutions=reviewed.resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert replay.replayed is True
    finally:
        db.close()
        engine.dispose()


def test_buildium_tenant_rejects_cross_org_stale_email_and_sensitive_audit():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Tenant Safety")
        foreign_org = _org(db, name="Tenant Foreign")
        tenant = _customer_tenant(db, org)
        foreign = _customer_tenant(
            db, foreign_org, email="foreign.tenant@example.com"
        )
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="tenant-safety",
            ),
            db=db,
            current_user=admin,
        )
        with pytest.raises(HTTPException) as exc:
            api.dry_run_buildium_tenants(
                run.id,
                BuildiumTenantDryRunIn(
                    records=[_tenant_record()],
                    resolutions=[
                        BuildiumTenantResolutionIn(
                            source_id=5001,
                            action="MATCH_EXISTING",
                            target_tenant_user_id=foreign.id,
                        )
                    ],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        payload = BuildiumTenantDryRunIn(
            records=[_tenant_record()],
            resolutions=[
                BuildiumTenantResolutionIn(
                    source_id=5001,
                    action="MATCH_EXISTING",
                    target_tenant_user_id=tenant.id,
                )
            ],
        )
        preview = api.dry_run_buildium_tenants(
            run.id, payload, db=db, current_user=admin
        )
        tenant.email = "changed.tenant@example.com"
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_tenants(
                run.id,
                BuildiumTenantCommitIn(
                    fingerprint=preview.fingerprint,
                    records=payload.records,
                    resolutions=payload.resolutions,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        audit_text = "\n".join(
            row.new_value or ""
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        assert "DO-NOT-STORE" not in audit_text
        assert "tina.tenant@example.com" not in audit_text
    finally:
        db.close()
        engine.dispose()


def test_buildium_tenant_skip_and_routes():
    from app.main import app

    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Tenant Skip")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="tenant-skip",
            ),
            db=db,
            current_user=admin,
        )
        record = _tenant_record(Id=5002, Email="skip.tenant@example.com")
        resolutions = [BuildiumTenantResolutionIn(source_id=5002, action="SKIP")]
        preview = api.dry_run_buildium_tenants(
            run.id,
            BuildiumTenantDryRunIn(records=[record], resolutions=resolutions),
            db=db,
            current_user=admin,
        )
        assert preview.skipped_review == 1
        result = api.commit_buildium_tenants(
            run.id,
            BuildiumTenantCommitIn(
                fingerprint=preview.fingerprint,
                records=[record],
                resolutions=resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert result.replayed is False
        assert result.matched_existing == 0
        assert db.query(User).filter(User.role == UserRole.TENANT).count() == 0
        assert db.query(Lease).count() == 0

        paths = set(app.openapi()["paths"])
        assert "/api/platform/migrations/buildium/runs/{run_id}/tenants/dry-run" in paths
        assert "/api/platform/migrations/buildium/runs/{run_id}/tenants/commit" in paths
    finally:
        db.close()
        engine.dispose()

def _lease_record(**changes):
    record = {
        "Id": 6001,
        "PropertyId": 1001,
        "UnitId": 2001,
        "UnitNumber": "1A",
        "LeaseFromDate": "2026-01-01",
        "LeaseToDate": "2026-12-31",
        "LeaseType": "Fixed",
        "LeaseStatus": "Active",
        "TermType": "Fixed",
        "PaymentDueDay": 1,
        "IsEvictionPending": False,
        "CurrentTenants": [
            {
                "Id": 5001,
                "FirstName": "Tina",
                "LastName": "Tenant",
                "Email": "tina.tenant@example.com",
                "TaxId": "DO-NOT-PROMOTE",
            }
        ],
        "RentAmount": 1300,
        "SecurityDepositAmount": 500,
    }
    record.update(changes)
    return record


def _lease_dependencies(db, run, org):
    target_property, _ = _buildium_property_mapping(db, run, org)
    unit = Unit(
        property_id=target_property.id,
        unit_number="1A",
        bedrooms=2,
        bathrooms=1.5,
        square_feet=900,
        monthly_rent=1250,
        is_available=None,
        is_listed=True,
        is_active=True,
    )
    db.add(unit)
    db.flush()
    db.add(
        PlatformMigrationItem(
            run_id=run.id,
            organization_id=org.id,
            provider="BUILDIUM",
            resource="UNITS",
            source_id="2001",
            target_entity="UNIT",
            target_id=unit.id,
            source_fingerprint="b" * 64,
            created_by_platform_user_id=run.created_by_platform_user_id,
        )
    )
    tenant = _customer_tenant(db, org)
    db.add(
        PlatformMigrationItem(
            run_id=run.id,
            organization_id=org.id,
            provider="BUILDIUM",
            resource="TENANTS",
            source_id="5001",
            target_entity="TENANT_USER",
            target_id=tenant.id,
            source_fingerprint="c" * 64,
            created_by_platform_user_id=run.created_by_platform_user_id,
        )
    )
    lease = Lease(
        unit_id=unit.id,
        tenant_id=tenant.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        monthly_rent=1300,
        security_deposit=500,
        due_day=1,
        status=LeaseStatus.ACTIVE,
    )
    db.add(lease)
    db.commit()
    db.refresh(unit)
    db.refresh(tenant)
    db.refresh(lease)
    return target_property, unit, tenant, lease


def test_buildium_lease_reconciles_exact_existing_relationship_only_and_replays():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Lease Reconciliation")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="lease-rel",
            ),
            db=db,
            current_user=admin,
        )
        _, unit, tenant, lease = _lease_dependencies(db, run, org)

        preview = api.dry_run_buildium_leases(
            run.id,
            BuildiumLeaseDryRunIn(records=[_lease_record()]),
            db=db,
            current_user=admin,
        )
        assert preview.invalid == 0
        assert preview.reviewable == 1
        assert preview.rows[0].mapped["target_unit_id"] == unit.id
        assert preview.rows[0].mapped["target_tenant_user_id"] == tenant.id
        assert any("never creates or updates" in warning for warning in preview.rows[0].warnings)

        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_leases(
                run.id,
                BuildiumLeaseCommitIn(
                    fingerprint=preview.fingerprint,
                    records=[_lease_record()],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        reviewed = BuildiumLeaseDryRunIn(
            records=[_lease_record()],
            resolutions=[
                BuildiumLeaseResolutionIn(
                    source_id=6001,
                    action="MATCH_EXISTING",
                    target_lease_id=lease.id,
                )
            ],
        )
        reviewed_preview = api.dry_run_buildium_leases(
            run.id, reviewed, db=db, current_user=admin
        )
        first = api.commit_buildium_leases(
            run.id,
            BuildiumLeaseCommitIn(
                fingerprint=reviewed_preview.fingerprint,
                records=reviewed.records,
                resolutions=reviewed.resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert first.matched_existing == 1
        assert first.replayed is False
        mapping = (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "LEASES")
            .one()
        )
        assert mapping.target_entity == "LEASE_RELATIONSHIP"
        assert mapping.target_id == lease.id
        assert db.query(Lease).count() == 1
        assert db.query(Charge).count() == 0
        assert db.query(GLTransaction).count() == 0

        replay = api.commit_buildium_leases(
            run.id,
            BuildiumLeaseCommitIn(
                fingerprint=reviewed_preview.fingerprint,
                records=reviewed.records,
                resolutions=reviewed.resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert replay.replayed is True

        response = Response()
        items = api.list_migration_items(
            run.id,
            response=response,
            resource="leases",
            limit=200,
            db=db,
            current_user=admin,
        )
        assert len(items) == 1
        assert items[0].target_exists is True
        assert items[0].target_label == f"Lease #{lease.id}"
        assert response.headers["cache-control"] == "no-store"
    finally:
        db.close()
        engine.dispose()


def test_buildium_lease_blocks_missing_or_ambiguous_membership_and_stale_dependency_fingerprint():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Lease Safety")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="lease-safety",
            ),
            db=db,
            current_user=admin,
        )

        missing = api.dry_run_buildium_leases(
            run.id,
            BuildiumLeaseDryRunIn(records=[_lease_record()]),
            db=db,
            current_user=admin,
        )
        assert missing.invalid == 1
        assert "Property, Unit, Tenant" in missing.rows[0].reason

        _, unit, _, lease = _lease_dependencies(db, run, org)
        ambiguous = api.dry_run_buildium_leases(
            run.id,
            BuildiumLeaseDryRunIn(
                records=[
                    _lease_record(
                        CurrentTenants=[
                            {"Id": 5001},
                            {"Id": 5002},
                        ]
                    )
                ]
            ),
            db=db,
            current_user=admin,
        )
        assert ambiguous.invalid == 1
        assert "Exactly one current Buildium tenant" in ambiguous.rows[0].reason

        reviewed = BuildiumLeaseDryRunIn(
            records=[_lease_record()],
            resolutions=[
                BuildiumLeaseResolutionIn(
                    source_id=6001,
                    action="MATCH_EXISTING",
                    target_lease_id=lease.id,
                )
            ],
        )
        preview = api.dry_run_buildium_leases(
            run.id, reviewed, db=db, current_user=admin
        )
        unit_mapping = (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "UNITS")
            .one()
        )
        unit_mapping.source_fingerprint = "d" * 64
        db.commit()

        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_leases(
                run.id,
                BuildiumLeaseCommitIn(
                    fingerprint=preview.fingerprint,
                    records=reviewed.records,
                    resolutions=reviewed.resolutions,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "dependency mapping state" in exc.value.detail
        assert db.query(Lease).count() == 1
        assert db.query(Charge).count() == 0
        assert db.query(GLTransaction).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_buildium_lease_skip_routes_and_sensitive_audit_boundary():
    from app.main import app

    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Lease Skip")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="lease-skip",
            ),
            db=db,
            current_user=admin,
        )
        _lease_dependencies(db, run, org)
        record = _lease_record(
            Id=6002,
            CurrentTenants=[{"Id": 5001, "TaxId": "LEASE-SECRET"}],
        )
        resolutions = [BuildiumLeaseResolutionIn(source_id=6002, action="SKIP")]
        preview = api.dry_run_buildium_leases(
            run.id,
            BuildiumLeaseDryRunIn(records=[record], resolutions=resolutions),
            db=db,
            current_user=admin,
        )
        assert preview.skipped_review == 1
        result = api.commit_buildium_leases(
            run.id,
            BuildiumLeaseCommitIn(
                fingerprint=preview.fingerprint,
                records=[record],
                resolutions=resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert result.replayed is False
        assert result.matched_existing == 0
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "LEASES"
        ).count() == 0
        audit_text = "\n".join(
            row.new_value or ""
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        assert "LEASE-SECRET" not in audit_text
        paths = set(app.openapi()["paths"])
        assert "/api/platform/migrations/buildium/runs/{run_id}/leases/dry-run" in paths
        assert "/api/platform/migrations/buildium/runs/{run_id}/leases/commit" in paths
    finally:
        db.close()
        engine.dispose()

def _gl_record(**changes):
    record = {
        "Id": 7001,
        "AccountNumber": "4100",
        "Name": "Rental Income",
        "Description": "Provider description only",
        "Type": "Income",
        "SubType": "Income",
        "IsDefaultGLAccount": True,
        "DefaultAccountName": "Rental Income",
        "IsContraAccount": False,
        "IsBankAccount": False,
        "CashFlowClassification": "OperatingActivities",
        "ExcludeFromCashBalances": False,
        "SubAccounts": [],
        "IsActive": True,
        "ParentGLAccountId": None,
        "IsCreditCardAccount": False,
    }
    record.update(changes)
    return record


def _target_gl(db, org, *, number="4100", name="Rental Income", account_type="INCOME", parent_id=None):
    row = GLAccount(
        organization_id=org.id,
        gl_number=number,
        name=name,
        account_type=account_type,
        sub_account_of=parent_id,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_buildium_gl_account_maps_existing_identity_only_and_replays():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="GL Mapping")
        target = _target_gl(db, org)
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="gl-map",
            ),
            db=db,
            current_user=admin,
        )

        preview = api.dry_run_buildium_gl_accounts(
            run.id,
            BuildiumGLAccountDryRunIn(records=[_gl_record()]),
            db=db,
            current_user=admin,
        )
        assert preview.invalid == 0
        assert preview.reviewable == 1
        assert any("exact account number" in x for x in preview.rows[0].warnings)

        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_gl_accounts(
                run.id,
                BuildiumGLAccountCommitIn(
                    fingerprint=preview.fingerprint,
                    records=[_gl_record()],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        reviewed = BuildiumGLAccountDryRunIn(
            records=[_gl_record()],
            resolutions=[
                BuildiumGLAccountResolutionIn(
                    source_id=7001,
                    action="MATCH_EXISTING",
                    target_gl_account_id=target.id,
                )
            ],
        )
        reviewed_preview = api.dry_run_buildium_gl_accounts(
            run.id, reviewed, db=db, current_user=admin
        )
        first = api.commit_buildium_gl_accounts(
            run.id,
            BuildiumGLAccountCommitIn(
                fingerprint=reviewed_preview.fingerprint,
                records=reviewed.records,
                resolutions=reviewed.resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert first.matched_existing == 1
        assert first.replayed is False
        mapping = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "GL_ACCOUNTS"
        ).one()
        assert mapping.target_entity == "GL_ACCOUNT"
        assert mapping.target_id == target.id
        assert db.query(GLAccount).count() == 1
        assert db.query(GLTransaction).count() == 0

        replay = api.commit_buildium_gl_accounts(
            run.id,
            BuildiumGLAccountCommitIn(
                fingerprint=reviewed_preview.fingerprint,
                records=reviewed.records,
                resolutions=reviewed.resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert replay.replayed is True

        response = Response()
        items = api.list_migration_items(
            run.id,
            response=response,
            resource="gl_accounts",
            limit=200,
            db=db,
            current_user=admin,
        )
        assert len(items) == 1
        assert items[0].target_exists is True
        assert items[0].target_label == "4100 Rental Income"
        assert response.headers["cache-control"] == "no-store"
    finally:
        db.close()
        engine.dispose()


def test_buildium_gl_account_parent_mapping_is_required_and_fingerprint_protected():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="GL Parent")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="gl-parent",
            ),
            db=db,
            current_user=admin,
        )
        parent = _target_gl(
            db,
            org,
            number="6100",
            name="Utilities",
            account_type="EXPENSE",
        )
        child = _target_gl(
            db,
            org,
            number="6110",
            name="Electric",
            account_type="EXPENSE",
            parent_id=parent.id,
        )
        child_record = _gl_record(
            Id=7011,
            AccountNumber="6110",
            Name="Electric",
            Type="Expense",
            SubType="OperatingExpenses",
            ParentGLAccountId=7010,
        )

        blocked = api.dry_run_buildium_gl_accounts(
            run.id,
            BuildiumGLAccountDryRunIn(records=[child_record]),
            db=db,
            current_user=admin,
        )
        assert blocked.invalid == 1
        assert "parent GL account 7010" in blocked.rows[0].reason

        parent_mapping = PlatformMigrationItem(
            run_id=run.id,
            organization_id=org.id,
            provider="BUILDIUM",
            resource="GL_ACCOUNTS",
            source_id="7010",
            target_entity="GL_ACCOUNT",
            target_id=parent.id,
            source_fingerprint="a" * 64,
            created_by_platform_user_id=admin.id,
        )
        db.add(parent_mapping)
        db.commit()

        reviewed = BuildiumGLAccountDryRunIn(
            records=[child_record],
            resolutions=[
                BuildiumGLAccountResolutionIn(
                    source_id=7011,
                    action="MATCH_EXISTING",
                    target_gl_account_id=child.id,
                )
            ],
        )
        preview = api.dry_run_buildium_gl_accounts(
            run.id, reviewed, db=db, current_user=admin
        )
        assert preview.invalid == 0
        parent_mapping.source_fingerprint = "b" * 64
        db.commit()

        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_gl_accounts(
                run.id,
                BuildiumGLAccountCommitIn(
                    fingerprint=preview.fingerprint,
                    records=reviewed.records,
                    resolutions=reviewed.resolutions,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "parent mapping state" in exc.value.detail
        assert db.query(GLAccount).count() == 2
        assert db.query(GLTransaction).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_buildium_gl_account_rejects_wrong_type_cross_org_and_supports_skip():
    from app.main import app

    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="GL Safety")
        foreign_org = _org(db, name="GL Foreign")
        target = _target_gl(db, org)
        foreign = _target_gl(db, foreign_org, number="4100", name="Foreign Income")
        wrong_type = _target_gl(
            db,
            org,
            number="4200",
            name="Other Asset",
            account_type="ASSET",
        )
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="gl-safety",
            ),
            db=db,
            current_user=admin,
        )

        for bad_target in (foreign, wrong_type):
            with pytest.raises(HTTPException) as exc:
                api.dry_run_buildium_gl_accounts(
                    run.id,
                    BuildiumGLAccountDryRunIn(
                        records=[_gl_record(AccountNumber=bad_target.gl_number)],
                        resolutions=[
                            BuildiumGLAccountResolutionIn(
                                source_id=7001,
                                action="MATCH_EXISTING",
                                target_gl_account_id=bad_target.id,
                            )
                        ],
                    ),
                    db=db,
                    current_user=admin,
                )
            assert exc.value.status_code == 409

        record = _gl_record(Id=7002, AccountNumber="4300", Name="Skip Income")
        resolutions = [
            BuildiumGLAccountResolutionIn(source_id=7002, action="SKIP")
        ]
        preview = api.dry_run_buildium_gl_accounts(
            run.id,
            BuildiumGLAccountDryRunIn(
                records=[record],
                resolutions=resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert preview.skipped_review == 1
        result = api.commit_buildium_gl_accounts(
            run.id,
            BuildiumGLAccountCommitIn(
                fingerprint=preview.fingerprint,
                records=[record],
                resolutions=resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert result.matched_existing == 0
        assert result.replayed is False
        assert db.query(GLAccount).count() == 3
        assert db.query(GLTransaction).count() == 0

        paths = set(app.openapi()["paths"])
        assert "/api/platform/migrations/buildium/runs/{run_id}/gl-accounts/dry-run" in paths
        assert "/api/platform/migrations/buildium/runs/{run_id}/gl-accounts/commit" in paths
    finally:
        db.close()
        engine.dispose()



def _work_order_record(**changes):
    record = {
        "Id": 8001,
        "Title": "Kitchen sink leak",
        "Status": "Open",
        "DueDate": "2026-10-10",
        "Priority": "High",
        "VendorId": 4001,
        "EntryAllowed": True,
        "EntryNotes": "DO-NOT-PERSIST-ENTRY-NOTES",
        "Amount": 275.50,
        "BillTransactionIds": [99001],
        "LineItems": [{"Description": "DO-NOT-PROMOTE-LINE", "Amount": 275.50}],
        "Task": {
            "Id": 7001,
            "PropertyId": 1001,
            "UnitId": 2001,
            "Description": "DO-NOT-PROMOTE-TASK-TEXT",
        },
    }
    record.update(changes)
    return record


def _work_order_dependencies(db, run, org):
    target_property, _ = _buildium_property_mapping(db, run, org)
    unit = Unit(
        property_id=target_property.id,
        unit_number="1A",
        bedrooms=2,
        bathrooms=1.5,
        square_feet=900,
        monthly_rent=1250,
        is_available=None,
        is_listed=True,
        is_active=True,
    )
    db.add(unit)
    db.flush()
    db.add(
        PlatformMigrationItem(
            run_id=run.id,
            organization_id=org.id,
            provider="BUILDIUM",
            resource="UNITS",
            source_id="2001",
            target_entity="UNIT",
            target_id=unit.id,
            source_fingerprint="u" * 64,
            created_by_platform_user_id=run.created_by_platform_user_id,
        )
    )
    vendor = _target_vendor(db, org)
    db.add(
        PlatformMigrationItem(
            run_id=run.id,
            organization_id=org.id,
            provider="BUILDIUM",
            resource="VENDORS",
            source_id="4001",
            target_entity="VENDOR",
            target_id=vendor.id,
            source_fingerprint="v" * 64,
            created_by_platform_user_id=run.created_by_platform_user_id,
        )
    )
    tenant = _customer_tenant(db, org)
    work_order = WorkOrder(
        unit_id=unit.id,
        property_id=target_property.id,
        tenant_id=tenant.id,
        vendor_id=vendor.id,
        title="Kitchen sink leak",
        description="Existing local maintenance description",
        status=WorkOrderStatus.SUBMITTED,
        permission_to_enter=False,
    )
    db.add(work_order)
    db.commit()
    db.refresh(unit)
    db.refresh(vendor)
    db.refresh(work_order)
    return target_property, unit, vendor, tenant, work_order


def test_buildium_work_order_reconciles_existing_relationship_only_and_replays():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Work Order Reconciliation")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="work-order-rel",
            ),
            db=db,
            current_user=admin,
        )
        _, unit, vendor, tenant, work_order = _work_order_dependencies(db, run, org)
        original = {
            "tenant_id": work_order.tenant_id,
            "assigned_to_id": work_order.assigned_to_id,
            "status": work_order.status,
            "permission_to_enter": work_order.permission_to_enter,
            "total_cost": work_order.total_cost,
            "description": work_order.description,
        }

        preview = api.dry_run_buildium_work_orders(
            run.id,
            BuildiumWorkOrderDryRunIn(records=[_work_order_record()]),
            db=db,
            current_user=admin,
        )
        assert preview.invalid == 0
        assert preview.reviewable == 1
        assert preview.rows[0].mapped["target_property_id"] == work_order.property_id
        assert preview.rows[0].mapped["target_unit_id"] == unit.id
        assert preview.rows[0].mapped["target_vendor_id"] == vendor.id
        assert any("explicit MATCH_EXISTING" in x for x in preview.rows[0].warnings)

        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_work_orders(
                run.id,
                BuildiumWorkOrderCommitIn(
                    fingerprint=preview.fingerprint,
                    records=[_work_order_record()],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        reviewed = BuildiumWorkOrderDryRunIn(
            records=[_work_order_record()],
            resolutions=[
                BuildiumWorkOrderResolutionIn(
                    source_id=8001,
                    action="MATCH_EXISTING",
                    target_work_order_id=work_order.id,
                )
            ],
        )
        reviewed_preview = api.dry_run_buildium_work_orders(
            run.id, reviewed, db=db, current_user=admin
        )
        first = api.commit_buildium_work_orders(
            run.id,
            BuildiumWorkOrderCommitIn(
                fingerprint=reviewed_preview.fingerprint,
                records=reviewed.records,
                resolutions=reviewed.resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert first.matched_existing == 1
        mapping = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "WORK_ORDERS"
        ).one()
        assert mapping.target_entity == "WORK_ORDER_RELATIONSHIP"
        assert mapping.target_id == work_order.id
        assert db.query(WorkOrder).count() == 1
        db.refresh(work_order)
        assert work_order.tenant_id == original["tenant_id"] == tenant.id
        assert work_order.assigned_to_id == original["assigned_to_id"]
        assert work_order.status == original["status"]
        assert work_order.permission_to_enter == original["permission_to_enter"]
        assert work_order.total_cost == original["total_cost"]
        assert work_order.description == original["description"]
        assert db.query(GLTransaction).count() == 0

        replay = api.commit_buildium_work_orders(
            run.id,
            BuildiumWorkOrderCommitIn(
                fingerprint=reviewed_preview.fingerprint,
                records=reviewed.records,
                resolutions=reviewed.resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert replay.replayed is True
        assert db.query(WorkOrder).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_buildium_work_order_requires_durable_relationships_and_rejects_stale_dependencies():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Work Order Dependencies")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="work-order-deps",
            ),
            db=db,
            current_user=admin,
        )
        missing = api.dry_run_buildium_work_orders(
            run.id,
            BuildiumWorkOrderDryRunIn(records=[_work_order_record()]),
            db=db,
            current_user=admin,
        )
        assert missing.invalid == 1
        assert "Property" in missing.rows[0].reason
        assert "Unit" in missing.rows[0].reason
        assert "Vendor" in missing.rows[0].reason

        _, _, _, _, work_order = _work_order_dependencies(db, run, org)
        payload = BuildiumWorkOrderDryRunIn(
            records=[_work_order_record()],
            resolutions=[
                BuildiumWorkOrderResolutionIn(
                    source_id=8001,
                    action="MATCH_EXISTING",
                    target_work_order_id=work_order.id,
                )
            ],
        )
        preview = api.dry_run_buildium_work_orders(
            run.id, payload, db=db, current_user=admin
        )
        unit_mapping = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "UNITS"
        ).one()
        unit_mapping.source_fingerprint = "x" * 64
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_work_orders(
                run.id,
                BuildiumWorkOrderCommitIn(
                    fingerprint=preview.fingerprint,
                    records=payload.records,
                    resolutions=payload.resolutions,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "WORK_ORDERS"
        ).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_buildium_work_order_rejects_cross_relationship_and_does_not_persist_sensitive_evidence():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Work Order Safety")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="work-order-safety",
            ),
            db=db,
            current_user=admin,
        )
        _, _, vendor, _, work_order = _work_order_dependencies(db, run, org)

        other_unit = Unit(
            property_id=work_order.property_id,
            unit_number="2B",
            bedrooms=1,
            bathrooms=1,
            square_feet=600,
            monthly_rent=900,
            is_available=True,
            is_listed=True,
            is_active=True,
        )
        db.add(other_unit)
        db.commit()
        bad_target = WorkOrder(
            unit_id=other_unit.id,
            property_id=work_order.property_id,
            tenant_id=work_order.tenant_id,
            vendor_id=vendor.id,
            title=work_order.title,
            description="Other unit",
            status=WorkOrderStatus.SUBMITTED,
        )
        db.add(bad_target)
        db.commit()

        with pytest.raises(HTTPException) as exc:
            api.dry_run_buildium_work_orders(
                run.id,
                BuildiumWorkOrderDryRunIn(
                    records=[_work_order_record()],
                    resolutions=[
                        BuildiumWorkOrderResolutionIn(
                            source_id=8001,
                            action="MATCH_EXISTING",
                            target_work_order_id=bad_target.id,
                        )
                    ],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        skip_payload = BuildiumWorkOrderDryRunIn(
            records=[_work_order_record(Id=8002)],
            resolutions=[
                BuildiumWorkOrderResolutionIn(source_id=8002, action="SKIP")
            ],
        )
        skip_preview = api.dry_run_buildium_work_orders(
            run.id, skip_payload, db=db, current_user=admin
        )
        assert skip_preview.skipped_review == 1
        skipped = api.commit_buildium_work_orders(
            run.id,
            BuildiumWorkOrderCommitIn(
                fingerprint=skip_preview.fingerprint,
                records=skip_payload.records,
                resolutions=skip_payload.resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert skipped.matched_existing == 0
        assert db.query(WorkOrder).count() == 2
        audit_text = "\n".join(
            row.new_value or ""
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        assert "DO-NOT-PERSIST-ENTRY-NOTES" not in audit_text
        assert "DO-NOT-PROMOTE-TASK-TEXT" not in audit_text
        assert "DO-NOT-PROMOTE-LINE" not in audit_text
        assert db.query(GLTransaction).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_buildium_work_order_routes_and_item_visibility():
    from app.main import app

    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        org = _org(db, name="Work Order Visibility")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="work-order-visible",
            ),
            db=db,
            current_user=admin,
        )
        _, _, _, _, work_order = _work_order_dependencies(db, run, org)
        reviewed = BuildiumWorkOrderDryRunIn(
            records=[_work_order_record()],
            resolutions=[
                BuildiumWorkOrderResolutionIn(
                    source_id=8001,
                    action="MATCH_EXISTING",
                    target_work_order_id=work_order.id,
                )
            ],
        )
        preview = api.dry_run_buildium_work_orders(
            run.id, reviewed, db=db, current_user=admin
        )
        api.commit_buildium_work_orders(
            run.id,
            BuildiumWorkOrderCommitIn(
                fingerprint=preview.fingerprint,
                records=reviewed.records,
                resolutions=reviewed.resolutions,
            ),
            db=db,
            current_user=admin,
        )
        response = Response()
        items = api.list_migration_items(
            run.id,
            response=response,
            resource="WORK_ORDERS",
            limit=200,
            db=db,
            current_user=support,
        )
        assert len(items) == 1
        assert items[0].target_exists is True
        assert "Kitchen sink leak" in items[0].target_label
        assert response.headers["cache-control"] == "no-store"

        paths = set(app.openapi()["paths"])
        assert "/api/platform/migrations/buildium/runs/{run_id}/work-orders/dry-run" in paths
        assert "/api/platform/migrations/buildium/runs/{run_id}/work-orders/commit" in paths
    finally:
        db.close()
        engine.dispose()



def _bill_record(**changes):
    record = {
        "Id": 9001,
        "Date": "2026-09-15",
        "DueDate": "2026-10-15",
        "PaidDate": None,
        "PaidStatus": "Unpaid",
        "Memo": "DO-NOT-PERSIST-BILL-MEMO",
        "VendorId": 4001,
        "WorkOrderId": None,
        "ReferenceNumber": "INV-9001",
        "ApprovalStatus": "Approved",
        "Lines": [
            {
                "Id": 9101,
                "AccountingEntity": {
                    "Id": 1001,
                    "AccountingEntityType": "Rental",
                    "Href": "provider-only",
                    "Unit": {"Id": 2001, "Href": "provider-only"},
                },
                "GLAccount": {
                    "Id": 7001,
                    "AccountNumber": "6100",
                    "Name": "Repairs",
                    "Type": "Expense",
                },
                "Amount": 125.50,
                "Markup": None,
                "Memo": "DO-NOT-PERSIST-BILL-LINE-MEMO",
            }
        ],
    }
    record.update(changes)
    return record


def _bill_dependencies(db, run, org):
    target_property, _ = _buildium_property_mapping(db, run, org)
    unit = Unit(
        property_id=target_property.id,
        unit_number="1A",
        bedrooms=2,
        bathrooms=1.5,
        square_feet=900,
        monthly_rent=1250,
        is_available=None,
        is_listed=True,
        is_active=True,
    )
    db.add(unit)
    db.flush()
    db.add(
        PlatformMigrationItem(
            run_id=run.id,
            organization_id=org.id,
            provider="BUILDIUM",
            resource="UNITS",
            source_id="2001",
            target_entity="UNIT",
            target_id=unit.id,
            source_fingerprint="u" * 64,
            created_by_platform_user_id=run.created_by_platform_user_id,
        )
    )
    vendor = _target_vendor(db, org)
    db.add(
        PlatformMigrationItem(
            run_id=run.id,
            organization_id=org.id,
            provider="BUILDIUM",
            resource="VENDORS",
            source_id="4001",
            target_entity="VENDOR",
            target_id=vendor.id,
            source_fingerprint="v" * 64,
            created_by_platform_user_id=run.created_by_platform_user_id,
        )
    )
    expense = _target_gl(
        db, org, number="6100", name="Repairs", account_type="EXPENSE"
    )
    db.add(
        PlatformMigrationItem(
            run_id=run.id,
            organization_id=org.id,
            provider="BUILDIUM",
            resource="GL_ACCOUNTS",
            source_id="7001",
            target_entity="GL_ACCOUNT",
            target_id=expense.id,
            source_fingerprint="g" * 64,
            created_by_platform_user_id=run.created_by_platform_user_id,
        )
    )
    payable = _target_gl(
        db, org, number="2100", name="Accounts Payable", account_type="LIABILITY"
    )
    bill = Bill(
        organization_id=org.id,
        bill_number="B-09001",
        payee_name=vendor.company_name,
        vendor_id=vendor.id,
        bill_date=date(2026, 9, 15),
        due_date=date(2026, 10, 15),
        reference_number="INV-9001",
        amount=125.50,
        amount_paid=0,
        status="UNPAID",
        property_id=target_property.id,
        unit_id=unit.id,
        payable_gl_account_id=payable.id,
        is_reversed=False,
        is_active=True,
    )
    db.add(bill)
    db.flush()
    db.add(
        BillLine(
            organization_id=org.id,
            bill_id=bill.id,
            gl_account_id=expense.id,
            property_id=target_property.id,
            unit_id=unit.id,
            description="Existing local line",
            amount=125.50,
        )
    )
    db.commit()
    db.refresh(unit)
    db.refresh(vendor)
    db.refresh(expense)
    db.refresh(bill)
    return target_property, unit, vendor, expense, payable, bill


def test_buildium_bill_reconciles_existing_relationship_only_and_replays():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Bill Reconciliation")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="bill-rel",
            ),
            db=db,
            current_user=admin,
        )
        _, _, _, _, _, bill = _bill_dependencies(db, run, org)
        original = {
            "status": bill.status,
            "amount_paid": bill.amount_paid,
            "payable_gl_account_id": bill.payable_gl_account_id,
            "cash_gl_account_id": bill.cash_gl_account_id,
            "remarks": bill.remarks,
        }

        preview = api.dry_run_buildium_bills(
            run.id,
            BuildiumBillDryRunIn(records=[_bill_record()]),
            db=db,
            current_user=admin,
        )
        assert preview.invalid == 0
        assert preview.reviewable == 1
        assert preview.rows[0].mapped["amount"] == "125.50"
        assert len(preview.rows[0].mapped["lines"]) == 1
        assert any("explicit MATCH_EXISTING" in x for x in preview.rows[0].warnings)

        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_bills(
                run.id,
                BuildiumBillCommitIn(
                    fingerprint=preview.fingerprint,
                    records=[_bill_record()],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        reviewed = BuildiumBillDryRunIn(
            records=[_bill_record()],
            resolutions=[
                BuildiumBillResolutionIn(
                    source_id=9001,
                    action="MATCH_EXISTING",
                    target_bill_id=bill.id,
                )
            ],
        )
        reviewed_preview = api.dry_run_buildium_bills(
            run.id, reviewed, db=db, current_user=admin
        )
        first = api.commit_buildium_bills(
            run.id,
            BuildiumBillCommitIn(
                fingerprint=reviewed_preview.fingerprint,
                records=reviewed.records,
                resolutions=reviewed.resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert first.matched_existing == 1
        mapping = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "BILLS"
        ).one()
        assert mapping.target_entity == "BILL_RELATIONSHIP"
        assert mapping.target_id == bill.id
        assert db.query(Bill).count() == 1
        assert db.query(BillLine).count() == 1
        db.refresh(bill)
        assert bill.status == original["status"]
        assert bill.amount_paid == original["amount_paid"]
        assert bill.payable_gl_account_id == original["payable_gl_account_id"]
        assert bill.cash_gl_account_id == original["cash_gl_account_id"]
        assert bill.remarks == original["remarks"]
        assert db.query(GLTransaction).count() == 0

        replay = api.commit_buildium_bills(
            run.id,
            BuildiumBillCommitIn(
                fingerprint=reviewed_preview.fingerprint,
                records=reviewed.records,
                resolutions=reviewed.resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert replay.replayed is True
        assert db.query(Bill).count() == 1
        assert db.query(BillLine).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_buildium_bill_requires_durable_dependencies_and_rejects_stale_mapping():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Bill Dependencies")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="bill-deps",
            ),
            db=db,
            current_user=admin,
        )
        missing = api.dry_run_buildium_bills(
            run.id,
            BuildiumBillDryRunIn(records=[_bill_record()]),
            db=db,
            current_user=admin,
        )
        assert missing.invalid == 1
        assert "Vendor mapping" in missing.rows[0].reason

        _, _, _, _, _, bill = _bill_dependencies(db, run, org)
        reviewed = BuildiumBillDryRunIn(
            records=[_bill_record()],
            resolutions=[
                BuildiumBillResolutionIn(
                    source_id=9001,
                    action="MATCH_EXISTING",
                    target_bill_id=bill.id,
                )
            ],
        )
        preview = api.dry_run_buildium_bills(
            run.id, reviewed, db=db, current_user=admin
        )
        gl_mapping = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "GL_ACCOUNTS"
        ).one()
        gl_mapping.source_fingerprint = "x" * 64
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_bills(
                run.id,
                BuildiumBillCommitIn(
                    fingerprint=preview.fingerprint,
                    records=reviewed.records,
                    resolutions=reviewed.resolutions,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "dependency mapping state" in exc.value.detail
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "BILLS"
        ).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_buildium_bill_blocks_unsupported_markup_and_mismatched_target():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Bill Safety")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="bill-safety",
            ),
            db=db,
            current_user=admin,
        )
        _, unit, vendor, expense, payable, bill = _bill_dependencies(db, run, org)

        marked = _bill_record()
        marked["Lines"][0]["Markup"] = {"Amount": 10, "Type": "Percent"}
        blocked = api.dry_run_buildium_bills(
            run.id,
            BuildiumBillDryRunIn(records=[marked]),
            db=db,
            current_user=admin,
        )
        assert blocked.invalid == 1
        assert "non-zero Buildium markup" in blocked.rows[0].reason

        other = Bill(
            organization_id=org.id,
            bill_number="B-OTHER",
            payee_name=vendor.company_name,
            vendor_id=vendor.id,
            bill_date=date(2026, 9, 15),
            due_date=date(2026, 10, 15),
            reference_number="INV-9001",
            amount=125.50,
            amount_paid=0,
            status="UNPAID",
            property_id=bill.property_id,
            unit_id=unit.id,
            payable_gl_account_id=payable.id,
            is_reversed=False,
            is_active=True,
        )
        db.add(other)
        db.flush()
        other_gl = _target_gl(
            db, org, number="6200", name="Wrong Expense", account_type="EXPENSE"
        )
        db.add(
            BillLine(
                organization_id=org.id,
                bill_id=other.id,
                gl_account_id=other_gl.id,
                property_id=bill.property_id,
                unit_id=unit.id,
                amount=125.50,
            )
        )
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.dry_run_buildium_bills(
                run.id,
                BuildiumBillDryRunIn(
                    records=[_bill_record()],
                    resolutions=[
                        BuildiumBillResolutionIn(
                            source_id=9001,
                            action="MATCH_EXISTING",
                            target_bill_id=other.id,
                        )
                    ],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "exact mapped Buildium Bill relationship contract" in exc.value.detail
        assert db.query(GLTransaction).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_buildium_bill_skip_routes_item_visibility_and_sensitive_audit_boundary():
    from app.main import app

    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        org = _org(db, name="Bill Visibility")
        run = api.create_run(
            BuildiumMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="bill-visible",
            ),
            db=db,
            current_user=admin,
        )
        _, _, _, _, _, bill = _bill_dependencies(db, run, org)

        skip_record = _bill_record(Id=9002, ReferenceNumber="INV-SKIP")
        skip_payload = BuildiumBillDryRunIn(
            records=[skip_record],
            resolutions=[BuildiumBillResolutionIn(source_id=9002, action="SKIP")],
        )
        skip_preview = api.dry_run_buildium_bills(
            run.id, skip_payload, db=db, current_user=admin
        )
        skipped = api.commit_buildium_bills(
            run.id,
            BuildiumBillCommitIn(
                fingerprint=skip_preview.fingerprint,
                records=skip_payload.records,
                resolutions=skip_payload.resolutions,
            ),
            db=db,
            current_user=admin,
        )
        assert skipped.matched_existing == 0

        reviewed = BuildiumBillDryRunIn(
            records=[_bill_record()],
            resolutions=[
                BuildiumBillResolutionIn(
                    source_id=9001,
                    action="MATCH_EXISTING",
                    target_bill_id=bill.id,
                )
            ],
        )
        preview = api.dry_run_buildium_bills(
            run.id, reviewed, db=db, current_user=admin
        )
        api.commit_buildium_bills(
            run.id,
            BuildiumBillCommitIn(
                fingerprint=preview.fingerprint,
                records=reviewed.records,
                resolutions=reviewed.resolutions,
            ),
            db=db,
            current_user=admin,
        )

        response = Response()
        items = api.list_migration_items(
            run.id,
            response=response,
            resource="BILLS",
            limit=200,
            db=db,
            current_user=support,
        )
        assert len(items) == 1
        assert items[0].target_exists is True
        assert "Lake Plumbing" in items[0].target_label
        assert response.headers["cache-control"] == "no-store"

        audit_text = "\n".join(
            row.new_value or ""
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        assert "DO-NOT-PERSIST-BILL-MEMO" not in audit_text
        assert "DO-NOT-PERSIST-BILL-LINE-MEMO" not in audit_text
        assert db.query(GLTransaction).count() == 0

        paths = set(app.openapi()["paths"])
        assert "/api/platform/migrations/buildium/runs/{run_id}/bills/dry-run" in paths
        assert "/api/platform/migrations/buildium/runs/{run_id}/bills/commit" in paths
    finally:
        db.close()
        engine.dispose()
