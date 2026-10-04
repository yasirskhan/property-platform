from __future__ import annotations

import json
from datetime import datetime

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
    BuildiumPropertyResolutionIn,
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
