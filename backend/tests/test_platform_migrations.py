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
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.property import Property, Unit
from app.models.user import Organization
from app.routers import platform_migrations as api
from app.schemas.platform_migration import (
    AppFolioMigrationRunCreateIn,
    AppFolioPropertyCommitIn,
    AppFolioPropertyDryRunIn,
    AppFolioStagedPropertyCommitIn,
    AppFolioStagedRowResolutionIn,
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



def test_appfolio_property_commit_is_atomic_mapped_and_replay_safe():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db)
        run = api.create_run(
            AppFolioMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="portfolio-commit",
            ),
            db=db,
            current_user=admin,
        )
        records = [
            _valid_record(),
            _valid_record(
                Id="AF-200",
                Name="River Apartments",
                Address1="20 River Rd",
                Address2=None,
            ),
            _valid_record(Id="AF-HIDDEN", HiddenAt="2026-09-01"),
        ]
        dry = api.dry_run_appfolio_properties(
            run.id,
            AppFolioPropertyDryRunIn(records=records),
            db=db,
            current_user=admin,
        )
        assert dry.importable == 2
        assert dry.skipped_hidden == 1
        before_commit_audit = db.query(AuditLog).filter(
            AuditLog.entity_type == "platform_migration_run",
            AuditLog.entity_id == run.id,
            AuditLog.action == "appfolio_properties_committed",
        ).count()

        committed = api.commit_appfolio_properties(
            run.id,
            AppFolioPropertyCommitIn(
                records=records,
                fingerprint=dry.fingerprint,
            ),
            db=db,
            current_user=admin,
        )
        assert committed.replayed is False
        assert committed.committed == 2
        assert committed.skipped_hidden == 1
        assert db.query(Property).filter(Property.organization_id == org.id).count() == 2
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "PROPERTIES",
        ).count() == 2
        assert db.get(PlatformMigrationRun, run.id).status == "PROPERTIES_COMMITTED"
        assert all(row.replayed is False for row in committed.rows)

        after_first_audit = db.query(AuditLog).filter(
            AuditLog.entity_type == "platform_migration_run",
            AuditLog.entity_id == run.id,
            AuditLog.action == "appfolio_properties_committed",
        ).count()
        assert after_first_audit == before_commit_audit + 1

        replay = api.commit_appfolio_properties(
            run.id,
            AppFolioPropertyCommitIn(
                records=records,
                fingerprint=dry.fingerprint,
            ),
            db=db,
            current_user=admin,
        )
        assert replay.replayed is True
        assert replay.committed == 0
        assert db.query(Property).filter(Property.organization_id == org.id).count() == 2
        assert all(row.replayed is True for row in replay.rows)
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "platform_migration_run",
            AuditLog.entity_id == run.id,
            AuditLog.action == "appfolio_properties_committed",
        ).count() == after_first_audit
    finally:
        db.close()
        engine.dispose()


def test_appfolio_property_commit_blocks_changed_invalid_and_existing_targets():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_TECH)
        org = _org(db)
        run = api.create_run(
            AppFolioMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="portfolio-blocks",
            ),
            db=db,
            current_user=admin,
        )
        valid = [_valid_record()]
        dry = api.dry_run_appfolio_properties(
            run.id,
            AppFolioPropertyDryRunIn(records=valid),
            db=db,
            current_user=admin,
        )

        changed = [_valid_record(Name="Changed after preview")]
        with pytest.raises(HTTPException) as exc:
            api.commit_appfolio_properties(
                run.id,
                AppFolioPropertyCommitIn(
                    records=changed,
                    fingerprint=dry.fingerprint,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(Property).count() == 0

        invalid = [_valid_record(Name="")]
        invalid_dry = api.dry_run_appfolio_properties(
            run.id,
            AppFolioPropertyDryRunIn(records=invalid),
            db=db,
            current_user=admin,
        )
        with pytest.raises(HTTPException) as exc:
            api.commit_appfolio_properties(
                run.id,
                AppFolioPropertyCommitIn(
                    records=invalid,
                    fingerprint=invalid_dry.fingerprint,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(Property).count() == 0

        existing = Property(
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
        db.add(existing)
        db.commit()
        conflict_dry = api.dry_run_appfolio_properties(
            run.id,
            AppFolioPropertyDryRunIn(records=valid),
            db=db,
            current_user=admin,
        )
        assert conflict_dry.warning_count == 1
        with pytest.raises(HTTPException) as exc:
            api.commit_appfolio_properties(
                run.id,
                AppFolioPropertyCommitIn(
                    records=valid,
                    fingerprint=conflict_dry.fingerprint,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(Property).count() == 1
        assert db.query(PlatformMigrationItem).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_appfolio_commit_schema_rejects_credentials_and_router_is_exposed():
    with pytest.raises(ValidationError):
        AppFolioPropertyCommitIn(
            records=[_valid_record()],
            fingerprint="0" * 64,
            access_token="secret",
        )

    from app.main import app

    paths = set(app.openapi()["paths"])
    assert "/api/platform/migrations/appfolio/runs" in paths
    assert "/api/platform/migrations/appfolio/runs/{run_id}/properties/dry-run" in paths
    assert "/api/platform/migrations/appfolio/runs/{run_id}/properties/commit" in paths



def test_appfolio_mapping_visibility_is_read_only_scoped_and_no_store():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        sales = _platform_user(db, PlatformUserRole.PLATFORM_SALES)
        org = _org(db)
        other_org = _org(db, name="Other Migration Org")
        run = api.create_run(
            AppFolioMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="portfolio-visibility",
            ),
            db=db,
            current_user=admin,
        )
        records = [_valid_record()]
        dry = api.dry_run_appfolio_properties(
            run.id,
            AppFolioPropertyDryRunIn(records=records),
            db=db,
            current_user=admin,
        )
        committed = api.commit_appfolio_properties(
            run.id,
            AppFolioPropertyCommitIn(
                records=records,
                fingerprint=dry.fingerprint,
            ),
            db=db,
            current_user=admin,
        )
        assert committed.committed == 1
        target_id = committed.rows[0].target_property_id

        response = Response()
        rows = api.list_appfolio_migration_items(
            run.id,
            response=response,
            resource=None,
            limit=200,
            db=db,
            current_user=support,
        )
        assert response.headers["cache-control"] == "no-store"
        assert len(rows) == 1
        assert rows[0].source_id == "AF-100"
        assert rows[0].target_entity == "PROPERTY"
        assert rows[0].target_id == target_id
        assert rows[0].target_exists is True
        assert rows[0].target_label == "Lake Apartments"
        assert rows[0].source_fingerprint == dry.fingerprint

        filtered = api.list_appfolio_migration_items(
            run.id,
            response=Response(),
            resource="properties",
            limit=200,
            db=db,
            current_user=support,
        )
        assert [row.id for row in filtered] == [rows[0].id]

        assert api.list_appfolio_migration_items(
            run.id,
            response=Response(),
            resource="UNITS",
            limit=200,
            db=db,
            current_user=support,
        ) == []

        with pytest.raises(HTTPException) as exc:
            api.list_appfolio_migration_items(
                run.id,
                response=Response(),
                resource=None,
                limit=200,
                db=db,
                current_user=sales,
            )
        assert exc.value.status_code == 403

        # A mapping cannot leak or rebind to another organization even if a
        # same numeric target id is otherwise meaningful there.
        db.get(PlatformMigrationRun, run.id).organization_id = other_org.id
        db.flush()
        with pytest.raises(HTTPException) as exc:
            api.list_appfolio_migration_items(
                run.id,
                response=Response(),
                resource=None,
                limit=200,
                db=db,
                current_user=support,
            )
        assert exc.value.status_code == 404

        assert db.query(PlatformMigrationItem).count() == 1
        assert db.query(Property).count() == 1
    finally:
        db.rollback()
        db.close()
        engine.dispose()


def test_appfolio_mapping_visibility_marks_missing_target_without_mutation():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db)
        run = api.create_run(
            AppFolioMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="portfolio-recovery",
            ),
            db=db,
            current_user=admin,
        )
        item = PlatformMigrationItem(
            run_id=run.id,
            organization_id=org.id,
            provider="APPFOLIO",
            resource="PROPERTIES",
            source_id="AF-MISSING",
            target_entity="PROPERTY",
            target_id=999999,
            source_fingerprint="a" * 64,
            created_by_platform_user_id=admin.id,
        )
        db.add(item)
        db.commit()

        rows = api.list_appfolio_migration_items(
            run.id,
            response=Response(),
            resource="PROPERTIES",
            limit=200,
            db=db,
            current_user=admin,
        )
        assert len(rows) == 1
        assert rows[0].target_exists is False
        assert rows[0].target_label is None
        assert db.query(Property).count() == 0
    finally:
        db.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# Phase 4.13 CSV/XLSX ingestion + staging foundation
# ---------------------------------------------------------------------------

import asyncio
from io import BytesIO
import json as _json

from fastapi import UploadFile
from openpyxl import Workbook

from app.models.platform_migration import PlatformMigrationStagedRow, PlatformMigrationUpload


def _upload_file(name: str, content: bytes) -> UploadFile:
    return UploadFile(filename=name, file=BytesIO(content))


def test_appfolio_csv_upload_detects_stages_and_replays_without_target_mutation():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="CSV Stage Org")
        run = api.create_run(
            AppFolioMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="csv-stage",
            ),
            db=db,
            current_user=admin,
        )
        content = (
            "Property Id,Property Name,Address 1,City,State,Zip,Property Type\n"
            "AF-CSV-1,Lake CSV,10 Lake Ave,Cleveland,OH,44113,Multi Family\n"
        ).encode()

        first = asyncio.run(
            api.stage_appfolio_upload(
                run.id,
                file=_upload_file("properties.csv", content),
                resource=None,
                sheet_name=None,
                column_mapping_json=None,
                db=db,
                current_user=admin,
            )
        )
        assert first.detected_resource == "PROPERTIES"
        assert first.status == "STAGED"
        assert first.replayed is False
        assert first.validation_summary == {
            "total": 1,
            "valid": 1,
            "warnings": 0,
            "invalid": 0,
            "duplicates": 0,
            "possible_existing_matches": 0,
            "missing_required_columns": [],
            "ambiguous_mapping_fields": [],
        }
        assert db.query(Property).count() == 0
        assert db.query(PlatformMigrationUpload).count() == 1
        row = db.query(PlatformMigrationStagedRow).one()
        assert row.source_id == "AF-CSV-1"
        assert row.disposition == "NEW"
        assert row.normalized_data["name"] == "Lake CSV"

        audit_before = db.query(AuditLog).filter(
            AuditLog.entity_type == "platform_migration_run",
            AuditLog.entity_id == run.id,
            AuditLog.action == "appfolio_file_staged",
        ).count()
        replay = asyncio.run(
            api.stage_appfolio_upload(
                run.id,
                file=_upload_file("renamed.csv", content),
                resource=None,
                sheet_name=None,
                column_mapping_json=None,
                db=db,
                current_user=admin,
            )
        )
        assert replay.replayed is True
        assert replay.id == first.id
        assert replay.normalized_fingerprint == first.normalized_fingerprint
        assert db.query(PlatformMigrationUpload).count() == 1
        assert db.query(PlatformMigrationStagedRow).count() == 1
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "platform_migration_run",
            AuditLog.entity_id == run.id,
            AuditLog.action == "appfolio_file_staged",
        ).count() == audit_before
    finally:
        db.close()
        engine.dispose()


def test_appfolio_explicit_mapping_changes_staging_fingerprint_and_clears_old_dry_run():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_TECH)
        org = _org(db, name="Explicit Map Org")
        run = api.create_run(
            AppFolioMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="explicit-map",
            ),
            db=db,
            current_user=admin,
        )
        valid = [_valid_record()]
        dry = api.dry_run_appfolio_properties(
            run.id,
            AppFolioPropertyDryRunIn(records=valid),
            db=db,
            current_user=admin,
        )
        assert db.get(PlatformMigrationRun, run.id).last_dry_run_fingerprint == dry.fingerprint

        content = (
            "External Key,Display Label,StreetAddr,Town,Province,Postal\n"
            "PX-1,Mapped Property,1 Main St,Cleveland,OH,44113\n"
        ).encode()
        uncertain = asyncio.run(
            api.stage_appfolio_upload(
                run.id,
                file=_upload_file("uncertain.csv", content),
                resource="PROPERTIES",
                sheet_name=None,
                column_mapping_json=None,
                db=db,
                current_user=admin,
            )
        )
        assert uncertain.status == "MAPPING_REQUIRED"
        assert uncertain.validation_summary["invalid"] == 1

        mapping = {
            "source_id": "External Key",
            "name": "Display Label",
            "address_line1": "StreetAddr",
            "city": "Town",
            "state": "Province",
            "zip_code": "Postal",
        }
        mapped = asyncio.run(
            api.stage_appfolio_upload(
                run.id,
                file=_upload_file("uncertain.csv", content),
                resource="PROPERTIES",
                sheet_name=None,
                column_mapping_json=_json.dumps(mapping),
                db=db,
                current_user=admin,
            )
        )
        assert mapped.status == "STAGED"
        assert mapped.normalized_fingerprint != uncertain.normalized_fingerprint
        assert mapped.column_mapping["source_id"] == "External Key"
        assert db.get(PlatformMigrationRun, run.id).last_dry_run_fingerprint is None
        assert db.get(PlatformMigrationRun, run.id).status == "STAGED"
        assert db.query(Property).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_appfolio_xlsx_is_data_only_and_formula_or_credentials_fail_closed():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_DEV)
        org = _org(db, name="XLSX Stage Org")
        run = api.create_run(
            AppFolioMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="xlsx-stage",
            ),
            db=db,
            current_user=admin,
        )

        wb = Workbook()
        ws = wb.active
        ws.title = "Property Directory"
        ws.append(["Property Id", "Property Name", "Address 1", "City", "State", "Zip"])
        ws.append(["X-1", "XLSX Property", "1 Excel Way", "Cleveland", "OH", "44113"])
        buf = BytesIO()
        wb.save(buf)
        staged = asyncio.run(
            api.stage_appfolio_upload(
                run.id,
                file=_upload_file("properties.xlsx", buf.getvalue()),
                resource=None,
                sheet_name=None,
                column_mapping_json=None,
                db=db,
                current_user=admin,
            )
        )
        assert staged.file_format == "XLSX"
        assert staged.sheet_name == "Property Directory"
        assert staged.status == "STAGED"

        wb2 = Workbook()
        ws2 = wb2.active
        ws2.append(["Property Id", "Property Name", "Address 1", "City", "State", "Zip", "Calc"])
        ws2.append(["X-2", "Formula Property", "2 Excel Way", "Cleveland", "OH", "44113", "=1+1"])
        buf2 = BytesIO()
        wb2.save(buf2)
        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                api.stage_appfolio_upload(
                    run.id,
                    file=_upload_file("formula.xlsx", buf2.getvalue()),
                    resource=None,
                    sheet_name=None,
                    column_mapping_json=None,
                    db=db,
                    current_user=admin,
                )
            )
        assert exc.value.status_code == 422
        assert "formula" in exc.value.detail.lower()

        secret_csv = (
            "Property Id,Property Name,Address 1,City,State,Zip,Client Secret\n"
            "S-1,Secret,3 Secret Way,Cleveland,OH,44113,do-not-store\n"
        ).encode()
        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                api.stage_appfolio_upload(
                    run.id,
                    file=_upload_file("secret.csv", secret_csv),
                    resource=None,
                    sheet_name=None,
                    column_mapping_json=None,
                    db=db,
                    current_user=admin,
                )
            )
        assert exc.value.status_code == 422
        assert "credential" in exc.value.detail.lower()
    finally:
        db.close()
        engine.dispose()


def test_appfolio_staging_dispositions_existing_mapping_possible_match_and_scope():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        org = _org(db, name="Disposition Org")
        other_org = _org(db, name="Disposition Other")
        existing = Property(
            organization_id=org.id,
            name="Existing Property",
            property_type="multi_family",
            address_line1="10 Match St",
            city="Cleveland",
            state="OH",
            zip_code="44113",
            country="USA",
            is_active=True,
        )
        db.add(existing)
        db.commit()

        run = api.create_run(
            AppFolioMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="dispositions",
            ),
            db=db,
            current_user=admin,
        )
        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=org.id,
                provider="APPFOLIO",
                resource="PROPERTIES",
                source_id="ALREADY-1",
                target_entity="PROPERTY",
                target_id=existing.id,
                source_fingerprint="b" * 64,
                created_by_platform_user_id=admin.id,
            )
        )
        db.commit()

        content = (
            "Property Id,Property Name,Address 1,City,State,Zip\n"
            "ALREADY-1,Previously Imported,1 Old St,Cleveland,OH,44113\n"
            "MATCH-1,Existing Property,10 Match St,Cleveland,OH,44113\n"
            "DUP-1,First Duplicate,20 Dup St,Cleveland,OH,44113\n"
            "DUP-1,Second Duplicate,21 Dup St,Cleveland,OH,44113\n"
        ).encode()
        staged = asyncio.run(
            api.stage_appfolio_upload(
                run.id,
                file=_upload_file("dispositions.csv", content),
                resource=None,
                sheet_name=None,
                column_mapping_json=None,
                db=db,
                current_user=admin,
            )
        )
        rows = api.list_appfolio_staged_rows(
            run.id,
            staged.id,
            response=Response(),
            offset=0,
            limit=200,
            db=db,
            current_user=support,
        )
        assert [row.disposition for row in rows] == [
            "ALREADY_MAPPED",
            "POSSIBLE_MATCH",
            "NEW",
            "INVALID",
        ]
        assert staged.validation_summary["duplicates"] == 1
        assert staged.validation_summary["possible_existing_matches"] == 1

        other_run = api.create_run(
            AppFolioMigrationRunCreateIn(
                organization_id=other_org.id,
                source_account_ref="other-scope",
            ),
            db=db,
            current_user=admin,
        )
        with pytest.raises(HTTPException) as exc:
            api.list_appfolio_staged_rows(
                other_run.id,
                staged.id,
                response=Response(),
                offset=0,
                limit=200,
                db=db,
                current_user=support,
            )
        assert exc.value.status_code == 404
    finally:
        db.close()
        engine.dispose()


def test_appfolio_upload_endpoint_is_exposed_and_business_targets_unchanged():
    from app.main import app

    paths = set(app.openapi()["paths"])
    assert "/api/platform/migrations/appfolio/runs/{run_id}/uploads" in paths
    assert "/api/platform/migrations/appfolio/runs/{run_id}/uploads/{upload_id}/rows" in paths



def test_staged_property_upload_reuses_existing_dry_run_engine_and_binds_source_fingerprint():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Staged Dry Run Org")
        run = api.create_run(
            AppFolioMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="staged-dry-run",
            ),
            db=db,
            current_user=admin,
        )
        content = (
            "Property Id,Property Name,Address 1,City,State,Zip,Property Type\n"
            "STAGE-1,Staged One,100 Stage St,Cleveland,OH,44113,Multi Family\n"
        ).encode()
        upload = asyncio.run(
            api.stage_appfolio_upload(
                run.id,
                file=_upload_file("properties.csv", content),
                resource=None,
                sheet_name=None,
                column_mapping_json=None,
                db=db,
                current_user=admin,
            )
        )
        before = db.query(Property).count()
        preview = api.dry_run_staged_appfolio_properties(
            run.id,
            upload.id,
            db=db,
            current_user=admin,
        )
        assert preview.total == 1
        assert preview.importable == 1
        assert preview.invalid == 0
        assert preview.replayed is False
        assert preview.rows[0].source_id == "STAGE-1"
        assert db.query(Property).count() == before

        stored = db.get(PlatformMigrationRun, run.id)
        assert stored.last_dry_run_fingerprint == preview.fingerprint
        staged_rows = (
            db.query(PlatformMigrationStagedRow)
            .filter(PlatformMigrationStagedRow.upload_id == upload.id)
            .order_by(PlatformMigrationStagedRow.row_number.asc())
            .all()
        )
        assert (
            stored.last_dry_run_summary["source_context_fingerprint"]
            == api._staged_review_fingerprint(upload, staged_rows)
        )
        assert (
            stored.last_dry_run_summary["source_context_fingerprint"]
            != upload.normalized_fingerprint
        )
        assert preview.fingerprint != upload.normalized_fingerprint

        audit_before = db.query(AuditLog).filter(
            AuditLog.entity_type == "platform_migration_run",
            AuditLog.entity_id == run.id,
            AuditLog.action == "appfolio_staged_properties_dry_run",
        ).count()
        replay = api.dry_run_staged_appfolio_properties(
            run.id,
            upload.id,
            db=db,
            current_user=admin,
        )
        assert replay.replayed is True
        assert replay.fingerprint == preview.fingerprint
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "platform_migration_run",
            AuditLog.entity_id == run.id,
            AuditLog.action == "appfolio_staged_properties_dry_run",
        ).count() == audit_before
        assert db.query(Property).count() == before
    finally:
        db.close()
        engine.dispose()


def test_staged_property_dry_run_blocks_invalid_possible_match_and_review_rows():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_TECH)
        org = _org(db, name="Staged Block Org")
        run = api.create_run(
            AppFolioMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="staged-block",
            ),
            db=db,
            current_user=admin,
        )

        invalid_content = (
            "Property Id,Property Name,Address 1,City,State,Zip\n"
            "BAD-1,,1 Bad St,Cleveland,OH,44113\n"
        ).encode()
        invalid_upload = asyncio.run(
            api.stage_appfolio_upload(
                run.id,
                file=_upload_file("invalid.csv", invalid_content),
                resource=None,
                sheet_name=None,
                column_mapping_json=None,
                db=db,
                current_user=admin,
            )
        )
        with pytest.raises(HTTPException) as exc:
            api.dry_run_staged_appfolio_properties(
                run.id, invalid_upload.id, db=db, current_user=admin
            )
        assert exc.value.status_code == 409
        assert "INVALID=1" in exc.value.detail

        existing = Property(
            organization_id=org.id,
            name="Existing Stage",
            property_type="multi_family",
            address_line1="2 Match St",
            city="Cleveland",
            state="OH",
            zip_code="44113",
            country="USA",
            is_active=True,
        )
        db.add(existing)
        db.commit()
        match_content = (
            "Property Id,Property Name,Address 1,City,State,Zip\n"
            "MATCH-STAGE,Existing Stage,2 Match St,Cleveland,OH,44113\n"
        ).encode()
        match_upload = asyncio.run(
            api.stage_appfolio_upload(
                run.id,
                file=_upload_file("match.csv", match_content),
                resource=None,
                sheet_name=None,
                column_mapping_json=None,
                db=db,
                current_user=admin,
            )
        )
        with pytest.raises(HTTPException) as exc:
            api.dry_run_staged_appfolio_properties(
                run.id, match_upload.id, db=db, current_user=admin
            )
        assert exc.value.status_code == 409
        assert "POSSIBLE_MATCH=1" in exc.value.detail

        review_content = (
            "Property Id,Property Name,Address 1,City,State,Zip,Hidden At\n"
            "HIDDEN-STAGE,Hidden Stage,3 Hide St,Cleveland,OH,44113,2026-01-01\n"
        ).encode()
        review_upload = asyncio.run(
            api.stage_appfolio_upload(
                run.id,
                file=_upload_file("review.csv", review_content),
                resource=None,
                sheet_name=None,
                column_mapping_json=None,
                db=db,
                current_user=admin,
            )
        )
        with pytest.raises(HTTPException) as exc:
            api.dry_run_staged_appfolio_properties(
                run.id, review_upload.id, db=db, current_user=admin
            )
        assert exc.value.status_code == 409
        assert "REVIEW=1" in exc.value.detail
    finally:
        db.close()
        engine.dispose()


def test_staged_property_dry_run_allows_already_mapped_replay_and_blocks_cross_run_upload():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Staged Replay Org")
        other_org = _org(db, name="Staged Replay Other")
        target = Property(
            organization_id=org.id,
            name="Mapped Target",
            property_type="multi_family",
            address_line1="10 Target St",
            city="Cleveland",
            state="OH",
            zip_code="44113",
            country="USA",
            is_active=True,
        )
        db.add(target)
        db.commit()
        run = api.create_run(
            AppFolioMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="staged-replay",
            ),
            db=db,
            current_user=admin,
        )
        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=org.id,
                provider="APPFOLIO",
                resource="PROPERTIES",
                source_id="MAPPED-1",
                target_entity="PROPERTY",
                target_id=target.id,
                source_fingerprint="c" * 64,
                created_by_platform_user_id=admin.id,
            )
        )
        db.commit()
        content = (
            "Property Id,Property Name,Address 1,City,State,Zip\n"
            "MAPPED-1,Mapped Target,10 Target St,Cleveland,OH,44113\n"
        ).encode()
        upload = asyncio.run(
            api.stage_appfolio_upload(
                run.id,
                file=_upload_file("mapped.csv", content),
                resource=None,
                sheet_name=None,
                column_mapping_json=None,
                db=db,
                current_user=admin,
            )
        )
        staged_row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.id
        ).one()
        assert staged_row.disposition == "ALREADY_MAPPED"

        preview = api.dry_run_staged_appfolio_properties(
            run.id, upload.id, db=db, current_user=admin
        )
        assert preview.importable == 1
        assert preview.warning_count == 2
        assert any(
            "Possible existing target property match" in warning
            for warning in preview.rows[0].warnings
        )
        assert db.query(Property).count() == 1

        other_run = api.create_run(
            AppFolioMigrationRunCreateIn(
                organization_id=other_org.id,
                source_account_ref="other",
            ),
            db=db,
            current_user=admin,
        )
        with pytest.raises(HTTPException) as exc:
            api.dry_run_staged_appfolio_properties(
                other_run.id, upload.id, db=db, current_user=admin
            )
        assert exc.value.status_code == 404
    finally:
        db.close()
        engine.dispose()


def test_staged_property_dry_run_route_is_exposed():
    from app.main import app
    assert (
        "/api/platform/migrations/appfolio/runs/{run_id}/uploads/{upload_id}/properties/dry-run"
        in set(app.openapi()["paths"])
    )


def test_staged_property_resolution_match_existing_and_controlled_commit_is_replay_safe():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Resolution Match Org")
        existing = Property(
            organization_id=org.id,
            name="Existing Match",
            property_type="multi_family",
            address_line1="10 Match Way",
            city="Cleveland",
            state="OH",
            zip_code="44113",
            country="USA",
            is_active=True,
        )
        db.add(existing)
        db.commit()
        original_name = existing.name
        run = api.create_run(
            AppFolioMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="resolution-match",
            ),
            db=db,
            current_user=admin,
        )
        content = (
            "Property Id,Property Name,Address 1,City,State,Zip\n"
            "MATCH-RES,Existing Match,10 Match Way,Cleveland,OH,44113\n"
            "NEW-RES,New Property,20 New Way,Cleveland,OH,44113\n"
        ).encode()
        upload = asyncio.run(
            api.stage_appfolio_upload(
                run.id,
                file=_upload_file("resolution.csv", content),
                resource=None,
                sheet_name=None,
                column_mapping_json=None,
                db=db,
                current_user=admin,
            )
        )
        rows = api.list_appfolio_staged_rows(
            run.id, upload.id, response=Response(), offset=0, limit=200,
            db=db, current_user=admin,
        )
        match_row = next(row for row in rows if row.source_id == "MATCH-RES")
        assert match_row.disposition == "POSSIBLE_MATCH"

        with pytest.raises(HTTPException):
            api.dry_run_staged_appfolio_properties(
                run.id, upload.id, db=db, current_user=admin
            )

        resolved = api.resolve_staged_appfolio_property(
            run.id,
            upload.id,
            match_row.id,
            AppFolioStagedRowResolutionIn(
                action="MATCH_EXISTING",
                target_property_id=existing.id,
            ),
            db=db,
            current_user=admin,
        )
        assert resolved.resolution_action == "MATCH_EXISTING"
        assert resolved.resolution_target_id == existing.id

        preview = api.dry_run_staged_appfolio_properties(
            run.id, upload.id, db=db, current_user=admin
        )
        assert preview.total == 2 and preview.importable == 2
        committed = api.commit_staged_appfolio_properties(
            run.id,
            upload.id,
            AppFolioStagedPropertyCommitIn(fingerprint=preview.fingerprint),
            db=db,
            current_user=admin,
        )
        assert committed.committed == 1
        assert committed.matched_existing == 1
        assert committed.replayed is False
        assert db.query(Property).filter(Property.organization_id == org.id).count() == 2
        assert db.get(Property, existing.id).name == original_name
        mappings = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "PROPERTIES",
        ).all()
        assert {item.source_id for item in mappings} == {"MATCH-RES", "NEW-RES"}
        assert next(item for item in mappings if item.source_id == "MATCH-RES").target_id == existing.id

        replay = api.commit_staged_appfolio_properties(
            run.id,
            upload.id,
            AppFolioStagedPropertyCommitIn(fingerprint=preview.fingerprint),
            db=db,
            current_user=admin,
        )
        assert replay.replayed is True
        assert replay.committed == 0
        assert replay.matched_existing == 0
        assert db.query(Property).filter(Property.organization_id == org.id).count() == 2
    finally:
        db.close()
        engine.dispose()


def test_staged_property_create_new_resolution_binds_fingerprint_and_old_preview_goes_stale():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_TECH)
        org = _org(db, name="Resolution Create Org")
        existing = Property(
            organization_id=org.id,
            name="Reviewed Possible",
            property_type="multi_family",
            address_line1="30 Review Rd",
            city="Cleveland",
            state="OH",
            zip_code="44113",
            country="USA",
            is_active=True,
        )
        db.add(existing)
        db.commit()
        run = api.create_run(
            AppFolioMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="resolution-create",
            ),
            db=db,
            current_user=admin,
        )
        content = (
            "Property Id,Property Name,Address 1,City,State,Zip\n"
            "CREATE-RES,Reviewed Possible,30 Review Rd,Cleveland,OH,44113\n"
        ).encode()
        upload = asyncio.run(
            api.stage_appfolio_upload(
                run.id,
                file=_upload_file("create-new.csv", content),
                resource=None,
                sheet_name=None,
                column_mapping_json=None,
                db=db,
                current_user=admin,
            )
        )
        row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.id
        ).one()
        api.resolve_staged_appfolio_property(
            run.id,
            upload.id,
            row.id,
            AppFolioStagedRowResolutionIn(action="CREATE_NEW"),
            db=db,
            current_user=admin,
        )
        preview_create = api.dry_run_staged_appfolio_properties(
            run.id, upload.id, db=db, current_user=admin
        )
        assert any(
            "Possible existing target property match" in warning
            for warning in preview_create.rows[0].warnings
        )

        api.resolve_staged_appfolio_property(
            run.id,
            upload.id,
            row.id,
            AppFolioStagedRowResolutionIn(
                action="MATCH_EXISTING",
                target_property_id=existing.id,
            ),
            db=db,
            current_user=admin,
        )
        assert db.get(PlatformMigrationRun, run.id).last_dry_run_fingerprint is None
        with pytest.raises(HTTPException) as exc:
            api.commit_staged_appfolio_properties(
                run.id,
                upload.id,
                AppFolioStagedPropertyCommitIn(fingerprint=preview_create.fingerprint),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        preview_match = api.dry_run_staged_appfolio_properties(
            run.id, upload.id, db=db, current_user=admin
        )
        assert preview_match.fingerprint != preview_create.fingerprint
        matched = api.commit_staged_appfolio_properties(
            run.id,
            upload.id,
            AppFolioStagedPropertyCommitIn(fingerprint=preview_match.fingerprint),
            db=db,
            current_user=admin,
        )
        assert matched.committed == 0 and matched.matched_existing == 1
        assert db.query(Property).filter(Property.organization_id == org.id).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_staged_property_create_new_and_skip_are_explicit_and_scoped():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        org = _org(db, name="Resolution Scope Org")
        other = _org(db, name="Resolution Scope Other")
        existing = Property(
            organization_id=org.id,
            name="Possible Create",
            property_type="multi_family",
            address_line1="40 Create St",
            city="Cleveland",
            state="OH",
            zip_code="44113",
            country="USA",
            is_active=True,
        )
        foreign = Property(
            organization_id=other.id,
            name="Foreign",
            property_type="multi_family",
            address_line1="99 Foreign St",
            city="Cleveland",
            state="OH",
            zip_code="44113",
            country="USA",
            is_active=True,
        )
        db.add_all([existing, foreign])
        db.commit()
        run = api.create_run(
            AppFolioMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="resolution-scope",
            ),
            db=db,
            current_user=admin,
        )
        content = (
            "Property Id,Property Name,Address 1,City,State,Zip,Hidden At\n"
            "CREATE-NEW,Possible Create,40 Create St,Cleveland,OH,44113,\n"
            "SKIP-HIDDEN,Hidden Source,50 Hidden St,Cleveland,OH,44113,2026-01-01\n"
        ).encode()
        upload = asyncio.run(
            api.stage_appfolio_upload(
                run.id,
                file=_upload_file("scope.csv", content),
                resource=None,
                sheet_name=None,
                column_mapping_json=None,
                db=db,
                current_user=admin,
            )
        )
        rows = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.id
        ).order_by(PlatformMigrationStagedRow.row_number).all()

        with pytest.raises(HTTPException) as exc:
            api.resolve_staged_appfolio_property(
                run.id,
                upload.id,
                rows[0].id,
                AppFolioStagedRowResolutionIn(
                    action="MATCH_EXISTING",
                    target_property_id=foreign.id,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 404

        with pytest.raises(HTTPException) as exc:
            api.resolve_staged_appfolio_property(
                run.id,
                upload.id,
                rows[0].id,
                AppFolioStagedRowResolutionIn(action="CREATE_NEW"),
                db=db,
                current_user=support,
            )
        assert exc.value.status_code == 403

        api.resolve_staged_appfolio_property(
            run.id,
            upload.id,
            rows[0].id,
            AppFolioStagedRowResolutionIn(action="CREATE_NEW"),
            db=db,
            current_user=admin,
        )
        api.resolve_staged_appfolio_property(
            run.id,
            upload.id,
            rows[1].id,
            AppFolioStagedRowResolutionIn(action="SKIP"),
            db=db,
            current_user=admin,
        )
        preview = api.dry_run_staged_appfolio_properties(
            run.id, upload.id, db=db, current_user=admin
        )
        assert preview.total == 1 and preview.rows[0].source_id == "CREATE-NEW"
        committed = api.commit_staged_appfolio_properties(
            run.id,
            upload.id,
            AppFolioStagedPropertyCommitIn(fingerprint=preview.fingerprint),
            db=db,
            current_user=admin,
        )
        assert committed.committed == 1
        assert db.query(Property).filter(Property.organization_id == org.id).count() == 2
        assert db.query(Property).filter(
            Property.organization_id == org.id,
            Property.name == "Hidden Source",
        ).count() == 0

        resolution_audits = db.query(AuditLog).filter(
            AuditLog.entity_type == "platform_migration_staged_row",
            AuditLog.action == "appfolio_property_resolution_changed",
        ).count()
        assert resolution_audits == 2
    finally:
        db.close()
        engine.dispose()


def test_staged_property_resolution_and_commit_routes_are_exposed():
    from app.main import app

    paths = set(app.openapi()["paths"])
    assert (
        "/api/platform/migrations/appfolio/runs/{run_id}/uploads/{upload_id}/rows/{staged_row_id}/resolution"
        in paths
    )
    assert (
        "/api/platform/migrations/appfolio/runs/{run_id}/uploads/{upload_id}/properties/commit"
        in paths
    )


# ---------------------------------------------------------------------------
# Phase 4.13 AppFolio Unit Directory ingestion + staging
# ---------------------------------------------------------------------------

def _mapped_property_for_units(db, *, run, org, admin, source_id="AF-PROP-UNIT"):
    target = Property(
        organization_id=org.id,
        name="Mapped Unit Property",
        property_type="multi_family",
        address_line1="100 Unit Way",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        country="USA",
        is_active=True,
    )
    db.add(target)
    db.flush()
    db.add(
        PlatformMigrationItem(
            run_id=run.id,
            organization_id=org.id,
            provider="APPFOLIO",
            resource="PROPERTIES",
            source_id=source_id,
            target_entity="PROPERTY",
            target_id=target.id,
            source_fingerprint="d" * 64,
            created_by_platform_user_id=admin.id,
        )
    )
    db.commit()
    return target


def test_appfolio_unit_directory_csv_stages_against_durable_property_mapping_and_replays():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Unit Stage Org")
        run = api.create_run(
            AppFolioMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="unit-stage",
            ),
            db=db,
            current_user=admin,
        )
        target = _mapped_property_for_units(
            db, run=run, org=org, admin=admin, source_id="PROP-100"
        )
        content = (
            "Unit ID,Unit Name,Property ID,Property Name,Unit Address,"
            "Unit Street Address 1,Unit Street Address 2,Unit City,Unit State,Unit Zip\n"
            "UNIT-1,101,PROP-100,Mapped Unit Property,100 Unit Way #101,"
            "100 Unit Way,,Cleveland,OH,44113\n"
        ).encode()

        first = asyncio.run(
            api.stage_appfolio_upload(
                run.id,
                file=_upload_file("unit-directory.csv", content),
                resource=None,
                sheet_name=None,
                column_mapping_json=None,
                db=db,
                current_user=admin,
            )
        )
        assert first.detected_resource == "UNITS"
        assert first.status == "STAGED"
        assert first.replayed is False
        assert first.validation_summary["total"] == 1
        assert first.validation_summary["valid"] == 1
        assert first.validation_summary["invalid"] == 0
        assert first.validation_summary["warnings"] == 0
        assert first.validation_summary["unresolved_property_links"] == 0
        assert first.validation_summary["missing_unit_source_ids"] == 0

        row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == first.id
        ).one()
        assert row.resource == "UNITS"
        assert row.source_id == "UNIT-1"
        assert row.disposition == "NEW"
        assert row.normalized_data["source_property_id"] == "PROP-100"
        assert row.normalized_data["unit_name"] == "101"
        assert row.normalized_data["address_line1"] == "100 Unit Way"
        assert db.query(Unit).count() == 0
        assert db.get(Property, target.id).name == "Mapped Unit Property"

        replay = asyncio.run(
            api.stage_appfolio_upload(
                run.id,
                file=_upload_file("same-units-renamed.csv", content),
                resource=None,
                sheet_name=None,
                column_mapping_json=None,
                db=db,
                current_user=admin,
            )
        )
        assert replay.replayed is True
        assert replay.id == first.id
        assert db.query(PlatformMigrationUpload).filter(
            PlatformMigrationUpload.run_id == run.id,
            PlatformMigrationUpload.detected_resource == "UNITS",
        ).count() == 1
        assert db.query(Unit).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_appfolio_unit_directory_missing_or_unresolved_ids_stage_for_review_not_invention():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_TECH)
        org = _org(db, name="Unit Review Org")
        run = api.create_run(
            AppFolioMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="unit-review",
            ),
            db=db,
            current_user=admin,
        )
        _mapped_property_for_units(
            db, run=run, org=org, admin=admin, source_id="PROP-OK"
        )
        content = (
            "Unit ID,Unit Name,Property ID,Property Name,Unit Street Address 1,"
            "Unit City,Unit State,Unit Zip\n"
            ",201,PROP-OK,Mapped Unit Property,100 Unit Way,Cleveland,OH,44113\n"
            "UNIT-UNKNOWN,202,PROP-MISSING,Unknown Property,200 Missing Way,Cleveland,OH,44113\n"
        ).encode()

        upload = asyncio.run(
            api.stage_appfolio_upload(
                run.id,
                file=_upload_file("unit-review.csv", content),
                resource=None,
                sheet_name=None,
                column_mapping_json=None,
                db=db,
                current_user=admin,
            )
        )
        assert upload.detected_resource == "UNITS"
        assert upload.status == "REVIEW_REQUIRED"
        assert upload.validation_summary["valid"] == 2
        assert upload.validation_summary["warnings"] == 2
        assert upload.validation_summary["unresolved_property_links"] == 1
        assert upload.validation_summary["missing_unit_source_ids"] == 1

        rows = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.id
        ).order_by(PlatformMigrationStagedRow.row_number).all()
        assert [row.disposition for row in rows] == ["REVIEW", "REVIEW"]
        assert rows[0].source_id is None
        assert any("Unit ID was not supplied" in warning for warning in rows[0].warnings)
        assert rows[1].source_id == "UNIT-UNKNOWN"
        assert any("has no durable Property mapping" in warning for warning in rows[1].warnings)
        assert db.query(Unit).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_appfolio_unit_directory_duplicate_unit_id_is_invalid_and_xlsx_autodetects():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, name="Unit XLSX Org")
        run = api.create_run(
            AppFolioMigrationRunCreateIn(
                organization_id=org.id,
                source_account_ref="unit-xlsx",
            ),
            db=db,
            current_user=admin,
        )
        _mapped_property_for_units(
            db, run=run, org=org, admin=admin, source_id="PROP-XLSX"
        )

        workbook = Workbook()
        ws = workbook.active
        ws.title = "Unit Directory"
        ws.append([
            "Unit ID", "Unit Name", "Property ID", "Property Name",
            "Unit Street Address 1", "Unit City", "Unit State", "Unit Zip",
        ])
        ws.append([
            "UNIT-X", "A", "PROP-XLSX", "Mapped Unit Property",
            "100 Unit Way", "Cleveland", "OH", "44113",
        ])
        ws.append([
            "UNIT-X", "B", "PROP-XLSX", "Mapped Unit Property",
            "100 Unit Way", "Cleveland", "OH", "44113",
        ])
        notes = workbook.create_sheet("Notes")
        notes.append(["Comment"])
        notes.append(["not a supported migration report"])
        buffer = BytesIO()
        workbook.save(buffer)
        workbook.close()

        upload = asyncio.run(
            api.stage_appfolio_upload(
                run.id,
                file=_upload_file("unit-directory.xlsx", buffer.getvalue()),
                resource=None,
                sheet_name=None,
                column_mapping_json=None,
                db=db,
                current_user=admin,
            )
        )
        assert upload.detected_resource == "UNITS"
        assert upload.sheet_name == "Unit Directory"
        assert upload.status == "STAGED_WITH_ERRORS"
        assert upload.validation_summary["duplicates"] == 1
        assert upload.validation_summary["invalid"] == 1

        rows = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.id
        ).order_by(PlatformMigrationStagedRow.row_number).all()
        assert rows[0].disposition == "NEW"
        assert rows[1].disposition == "INVALID"
        assert any("Duplicate AppFolio Unit ID" in error for error in rows[1].errors)
        assert db.query(Unit).count() == 0
    finally:
        db.close()
        engine.dispose()
