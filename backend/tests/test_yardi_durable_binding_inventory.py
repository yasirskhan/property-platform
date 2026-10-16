"""Committed Yardi identity metadata is inspectable without customer mutation."""
import pytest
from sqlalchemy import event
from fastapi import HTTPException, Response

from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUserRole
from app.models.property import Property, Unit
from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.routers.yardi_migrations import list_yardi_durable_bindings, skip_yardi_staged_row, YardiRowSkipIn
from test_yardi_migrations import _org, _platform_user, _session


def _binding(db, run, resource, source_id, entity, target_id):
    row = PlatformMigrationItem(
        run_id=run.id, organization_id=run.organization_id, provider=run.provider,
        resource=resource, source_id=source_id, target_entity=entity,
        target_id=target_id, source_fingerprint="reviewed-" + source_id,
    )
    db.add(row)
    db.flush()
    return row


def test_yardi_durable_inventory_is_paginated_org_scoped_and_metadata_only():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        org = _org(db, "yardi-binding-inventory")
        foreign = _org(db, "yardi-binding-foreign")
        prop = Property(
            organization_id=org.id, name="Existing Home",
            address_line1="1 Main", city="Cleveland", state="OH", zip_code="44113",
        )
        foreign_property = Property(
            organization_id=foreign.id, name="Outside Property",
            address_line1="2 Main", city="Cleveland", state="OH", zip_code="44113",
        )
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="inventory", status="DRAFT",
        )
        other_run = PlatformMigrationRun(
            organization_id=foreign.id, provider="YARDI",
            source_account_ref="another-run", status="DRAFT",
        )
        different_provider = PlatformMigrationRun(
            organization_id=org.id, provider="BUILDIUM",
            source_account_ref="buildium-run", status="DRAFT",
        )
        vendor = Vendor(organization_id=org.id, company_name="Unchanged Vendor")
        tenant = User(
            organization_id=org.id, role=UserRole.TENANT,
            first_name="Unchanged", last_name="Tenant",
            email="yardi-inventory-tenant@example.test",
            hashed_password="not-returned-hash", is_active=True,
        )
        db.add_all([prop, foreign_property, run, other_run, different_provider, vendor, tenant])
        db.flush()
        unit = Unit(property_id=prop.id, unit_number="201")
        db.add(unit)
        db.flush()
        property_map = _binding(db, run, "PROPERTIES", "P-1", "PROPERTY", prop.id)
        unit_map = _binding(db, run, "UNITS", "U-1", "UNIT", unit.id)
        _binding(db, run, "VENDORS", "V-1", "VENDOR", vendor.id)
        _binding(db, run, "TENANTS", "T-1", "TENANT_USER", tenant.id)
        _binding(db, other_run, "PROPERTIES", "P-foreign", "PROPERTY", foreign_property.id)
        _binding(db, different_provider, "PROPERTIES", "P-buildium", "PROPERTY", prop.id)
        db.commit()

        response = Response()
        first = list_yardi_durable_bindings(
            run.id, response, resource=None, offset=0, limit=2,
            db=db, current_user=support,
        )
        assert response.headers["cache-control"] == "no-store"
        assert first["provider"] == "YARDI" and first["total"] == 4
        assert first["read_only"] is True
        assert first["customer_business_mutation"] is False
        assert [x["id"] for x in first["items"]] == [property_map.id, unit_map.id]
        assert all(x["target_current"] for x in first["items"])
        second = list_yardi_durable_bindings(
            run.id, Response(), resource=None, offset=2, limit=2,
            db=db, current_user=admin,
        )
        assert second["total"] == 4 and len(second["items"]) == 2
        assert set(x["resource"] for x in second["items"]) == {"VENDORS", "TENANTS"}
        scoped = list_yardi_durable_bindings(
            run.id, Response(), resource="VENDORS", offset=0, limit=10,
            db=db, current_user=support,
        )
        assert scoped["total"] == 1 and scoped["items"][0]["source_id"] == "V-1"
        assert "Unchanged Vendor" not in str(scoped)
        assert "not-returned-hash" not in str(first) + str(second)
        assert "yardi-inventory-tenant@example.test" not in str(second)

        tenant.is_active = False
        prop.deleted_at = __import__("datetime").datetime.utcnow()
        db.commit()
        inactive = list_yardi_durable_bindings(
            run.id, Response(), resource="TENANTS", offset=0, limit=10,
            db=db, current_user=admin,
        )
        assert inactive["items"][0]["target_current"] is False
        changed_property = list_yardi_durable_bindings(
            run.id, Response(), resource="UNITS", offset=0, limit=10,
            db=db, current_user=admin,
        )
        assert changed_property["items"][0]["target_current"] is False
        db.refresh(vendor)
        assert vendor.company_name == "Unchanged Vendor"
        with pytest.raises(HTTPException) as wrong_provider:
            list_yardi_durable_bindings(
                different_provider.id, Response(), resource=None, offset=0, limit=10,
                db=db, current_user=admin,
            )
        assert wrong_provider.value.status_code == 404
    finally:
        db.close()
        engine.dispose()



def test_yardi_binding_source_collision_is_resource_and_run_scoped():
    """A Property source collision cannot mark a distinct Vendor identity stale."""
    from app.services.yardi_file_ingestion import stage_yardi_file

    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-binding-resource-isolation")
        target = Property(
            organization_id=org.id, name="Existing Home", address_line1="1 Main",
            city="Cleveland", state="OH", zip_code="44113",
        )
        vendor = Vendor(organization_id=org.id, company_name="Existing Vendor")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="scoped-collision", status="DRAFT",
        )
        other_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="other-run", status="DRAFT",
        )
        db.add_all([target, vendor, run, other_run])
        db.flush()
        _binding(db, run, "PROPERTIES", "SHARED", "PROPERTY", target.id)
        _binding(db, run, "VENDORS", "SHARED", "VENDOR", vendor.id)
        db.commit()

        def stage(resource, current_run, name):
            stage_yardi_file(
                db, run=current_run, filename=resource.lower() + ".csv",
                content=("ID,Name\nSHARED," + name + "\n").encode(),
                resource_override=resource, sheet_name=None,
                explicit_mapping={"source_id": "ID", "name": "Name"},
                platform_user_id=actor.id,
            )
            db.commit()

        stage("PROPERTIES", run, "Original")
        stage("VENDORS", run, "Unrelated Vendor")
        stage("PROPERTIES", other_run, "Outside This Run")
        first = list_yardi_durable_bindings(
            run.id, Response(), resource=None, offset=0, limit=10,
            db=db, current_user=actor,
        )
        assert all(not item["source_identity_collision"] for item in first["items"])
        stage("PROPERTIES", run, "Second Version")
        affected = list_yardi_durable_bindings(
            run.id, Response(), resource=None, offset=0, limit=10,
            db=db, current_user=actor,
        )
        by_resource = {item["resource"]: item for item in affected["items"]}
        assert by_resource["PROPERTIES"]["source_identity_collision"] is True
        assert by_resource["PROPERTIES"]["target_current"] is True
        assert by_resource["VENDORS"]["source_identity_collision"] is False
        assert by_resource["VENDORS"]["target_current"] is True
        db.refresh(target)
        db.refresh(vendor)
        assert target.name == "Existing Home"
        assert vendor.company_name == "Existing Vendor"
    finally:
        db.close()
        engine.dispose()


def test_yardi_durable_inventory_requires_platform_migration_role():
    db, engine = _session()
    try:
        unauthorized = _platform_user(db, PlatformUserRole.PLATFORM_SALES)
        org = _org(db, "yardi-binding-role")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI", source_account_ref="inventory",
            status="DRAFT",
        )
        db.add(run)
        db.commit()
        with pytest.raises(HTTPException) as denied:
            list_yardi_durable_bindings(
                run.id, Response(), resource=None, offset=0, limit=10,
                db=db, current_user=unauthorized,
            )
        assert denied.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_yardi_unit_inventory_marks_moved_parent_without_changing_customer_unit():
    from app.models.platform_migration import PlatformMigrationStagedRow
    from app.services.yardi_file_ingestion import stage_yardi_file

    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-inventory-parent-revalidation")
        prop = Property(
            organization_id=org.id, name="Mapped Parent",
            address_line1="101 Main", city="Cleveland", state="OH", zip_code="44113",
        )
        other = Property(
            organization_id=org.id, name="Other Active Parent",
            address_line1="102 Main", city="Cleveland", state="OH", zip_code="44113",
        )
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="unit-parent-evidence", status="DRAFT",
        )
        db.add_all([prop, other, run])
        db.flush()
        unit = Unit(property_id=prop.id, unit_number="101")
        db.add(unit)
        db.flush()
        _binding(db, run, "PROPERTIES", "P-1", "PROPERTY", prop.id)
        durable_unit = _binding(db, run, "UNITS", "U-1", "UNIT", unit.id)
        db.commit()

        unknown = list_yardi_durable_bindings(
            run.id, Response(), resource="UNITS", offset=0, limit=10,
            db=db, current_user=actor,
        )
        assert unknown["items"][0]["target_current"] is True
        assert unknown["items"][0]["unit_parent_relationship_current"] is None

        uploaded = stage_yardi_file(
            db, run=run, filename="unit-parent.csv",
            content=b"Unit Ref,Parent Ref,Number\nU-1,P-1,101\n",
            resource_override="UNITS", sheet_name=None,
            explicit_mapping={
                "source_id": "Unit Ref", "source_property_id": "Parent Ref",
                "unit_name": "Number",
            }, platform_user_id=actor.id,
        )
        db.commit()
        staged = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == uploaded.upload.id,
        ).one()
        staged.resolution_action = "MATCH_EXISTING"
        staged.resolution_target_unit_id = unit.id
        durable_unit.source_fingerprint = staged.row_fingerprint
        db.commit()
        linked = list_yardi_durable_bindings(
            run.id, Response(), resource="UNITS", offset=0, limit=10,
            db=db, current_user=actor,
        )
        assert linked["items"][0]["target_current"] is True
        assert linked["items"][0]["unit_parent_relationship_current"] is True
        assert linked["items"][0]["source_identity_collision"] is False

        unit.property_id = other.id
        db.commit()
        stale = list_yardi_durable_bindings(
            run.id, Response(), resource="UNITS", offset=0, limit=10,
            db=db, current_user=actor,
        )
        assert stale["items"][0]["target_current"] is True
        assert stale["items"][0]["unit_parent_relationship_current"] is False
        assert stale["items"][0]["target_id"] == unit.id
        db.refresh(unit)
        assert unit.property_id == other.id
        assert unit.unit_number == "101"

        unit.property_id = prop.id
        db.commit()
        restored = list_yardi_durable_bindings(
            run.id, Response(), resource="UNITS", offset=0, limit=10,
            db=db, current_user=actor,
        )
        assert restored["items"][0]["unit_parent_relationship_current"] is True

        # Deliberately model inconsistent exact-fingerprint review evidence.
        # A later matching review must NOT conceal an earlier conflict.
        changed = stage_yardi_file(
            db, run=run, filename="unit-contradictory-parent.csv",
            content=b"Unit Ref,Parent Ref,Number\nU-1,P-UNMAPPED,102\n",
            resource_override="UNITS", sheet_name=None,
            explicit_mapping={
                "source_id": "Unit Ref", "source_property_id": "Parent Ref",
                "unit_name": "Number",
            }, platform_user_id=actor.id,
        )
        db.commit()
        conflicting = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == changed.upload.id,
        ).one()
        conflicting.row_fingerprint = staged.row_fingerprint
        conflicting.resolution_action = "MATCH_EXISTING"
        conflicting.resolution_target_unit_id = unit.id
        db.commit()
        match_again = stage_yardi_file(
            db, run=run, filename="unit-second-matching-parent.csv",
            content=b"Unit Ref,Parent Ref,Number\nU-1,P-1,103\n",
            resource_override="UNITS", sheet_name=None,
            explicit_mapping={
                "source_id": "Unit Ref", "source_property_id": "Parent Ref",
                "unit_name": "Number",
            }, platform_user_id=actor.id,
        )
        db.commit()
        latest_matching = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == match_again.upload.id,
        ).one()
        latest_matching.row_fingerprint = staged.row_fingerprint
        latest_matching.resolution_action = "MATCH_EXISTING"
        latest_matching.resolution_target_unit_id = unit.id
        db.commit()
        contradictory = list_yardi_durable_bindings(
            run.id, Response(), resource="UNITS", offset=0, limit=10,
            db=db, current_user=actor,
        )
        assert contradictory["items"][0]["unit_parent_relationship_current"] is False
        assert contradictory["items"][0]["source_identity_collision"] is True
        # Even an invalid reviewed exact version must not be ignored.
        conflicting.disposition = "INVALID"
        db.commit()
        invalid_evidence = list_yardi_durable_bindings(
            run.id, Response(), resource="UNITS", offset=0, limit=10,
            db=db, current_user=actor,
        )
        assert invalid_evidence["items"][0]["unit_parent_relationship_current"] is False

        # Explicitly disposition the duplicate, retaining the two unaltered
        # exact reviewed sources and the originally bound customer Unit.
        conflicting.resolution_action = None
        db.commit()
        explicit_skip = skip_yardi_staged_row(
            run.id, conflicting.id, YardiRowSkipIn(reason_code="DUPLICATE_SOURCE"),
            db, actor,
        )
        assert explicit_skip["replayed"] is False
        # A second unskipped version still makes the durable source
        # ambiguous, even though its exact reviewed parent agrees.
        still_ambiguous = list_yardi_durable_bindings(
            run.id, Response(), resource="UNITS", offset=0, limit=10,
            db=db, current_user=actor,
        )
        assert still_ambiguous["items"][0]["source_identity_collision"] is True
        assert still_ambiguous["items"][0]["unit_parent_relationship_current"] is False
        latest_matching.resolution_action = None
        db.commit()
        assert skip_yardi_staged_row(
            run.id, latest_matching.id, YardiRowSkipIn(reason_code="DUPLICATE_SOURCE"),
            db, actor,
        )["action"] == "SKIP"
        reconciled = list_yardi_durable_bindings(
            run.id, Response(), resource="UNITS", offset=0, limit=10,
            db=db, current_user=actor,
        )
        assert reconciled["items"][0]["source_identity_collision"] is False
        assert reconciled["items"][0]["unit_parent_relationship_current"] is True
        db.refresh(durable_unit)
        db.refresh(unit)
        assert durable_unit.target_id == unit.id
        assert unit.property_id == prop.id
    finally:
        db.close()
        engine.dispose()


def test_durable_inventory_surfaces_competing_staged_target_review_without_target_mutation():
    from app.models.platform_migration import PlatformMigrationStagedRow
    from app.services.yardi_file_ingestion import stage_yardi_file

    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-binding-competing-target-claim")
        vendor = Vendor(organization_id=org.id, company_name="Preserved Company")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="original-vendor", status="DRAFT",
        )
        other_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="other-vendor", status="DRAFT",
        )
        db.add_all([vendor, run, other_run])
        db.flush()
        _binding(db, run, "VENDORS", "V-1", "VENDOR", vendor.id)
        db.commit()
        original = list_yardi_durable_bindings(
            run.id, Response(), resource="VENDORS", offset=0, limit=10,
            db=db, current_user=actor,
        )["items"][0]
        assert original["target_current"] is True
        assert original["target_review_collision"] is False

        upload = stage_yardi_file(
            db, run=other_run, filename="vendors.csv",
            content=b"Vendor Ref,Company Name\nV-other,Other Vendor\n",
            resource_override="VENDORS", sheet_name=None,
            explicit_mapping={"source_id": "Vendor Ref", "name": "Company Name"},
            platform_user_id=actor.id,
        )
        db.commit()
        competing = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id
        ).one()
        competing.resolution_action = "MATCH_EXISTING"
        competing.resolution_target_vendor_id = vendor.id
        db.commit()
        contested = list_yardi_durable_bindings(
            run.id, Response(), resource="VENDORS", offset=0, limit=10,
            db=db, current_user=actor,
        )["items"][0]
        assert contested["target_current"] is True
        assert contested["target_review_collision"] is True
        assert contested["source_identity_collision"] is False

        competing.resolution_action = None
        competing.resolution_target_vendor_id = None
        db.commit()
        restored = list_yardi_durable_bindings(
            run.id, Response(), resource="VENDORS", offset=0, limit=10,
            db=db, current_user=actor,
        )["items"][0]
        assert restored["target_review_collision"] is False

        # A second run with the SAME provider source identity does not
        # create a different reviewed target claim.
        competing.source_id = "V-1"
        competing.resolution_action = "MATCH_EXISTING"
        competing.resolution_target_vendor_id = vendor.id
        db.commit()
        same_source = list_yardi_durable_bindings(
            run.id, Response(), resource="VENDORS", offset=0, limit=10,
            db=db, current_user=actor,
        )["items"][0]
        assert same_source["target_current"] is True
        assert same_source["target_review_collision"] is False

        # Missing source identity in retained reviewed evidence still contests
        # an otherwise current customer target.
        competing.source_id = None
        db.commit()
        unknown = list_yardi_durable_bindings(
            run.id, Response(), resource="VENDORS", offset=0, limit=10,
            db=db, current_user=actor,
        )["items"][0]
        assert unknown["target_current"] is True
        assert unknown["target_review_collision"] is True
        competing.source_id = "V-1"
        db.commit()

        # A different organization cannot contest this run's identities,
        # even if old review evidence carries the same numeric target ID.
        outside_org = _org(db, "yardi-binding-foreign-review")
        outside_run = PlatformMigrationRun(
            organization_id=outside_org.id, provider="YARDI",
            source_account_ref="outside-vendor", status="DRAFT",
        )
        db.add(outside_run)
        db.commit()
        outside_upload = stage_yardi_file(
            db, run=outside_run, filename="outside-vendors.csv",
            content=b"Vendor Ref,Company Name\nOUTSIDE,Outside Vendor\n",
            resource_override="VENDORS", sheet_name=None,
            explicit_mapping={"source_id": "Vendor Ref", "name": "Company Name"},
            platform_user_id=actor.id,
        )
        db.commit()
        foreign_review = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == outside_upload.upload.id
        ).one()
        foreign_review.resolution_action = "MATCH_EXISTING"
        foreign_review.resolution_target_vendor_id = vendor.id
        db.commit()
        isolated = list_yardi_durable_bindings(
            run.id, Response(), resource="VENDORS", offset=0, limit=10,
            db=db, current_user=actor,
        )["items"][0]
        assert isolated["target_review_collision"] is False

        # The read-only inventory must not run another reviewed-claim SELECT
        # for each additional durable identity. Other live target checks can
        # still be separate, so count only staged reviewed-target SQL.
        def reviewed_claim_select_count():
            statements = []
            def observe(connection, cursor, statement, parameters, context, executemany):
                if (statement.lstrip().upper().startswith("SELECT")
                        and "resolution_action" in statement
                        and "resolution_target_vendor_id" in statement):
                    statements.append(statement)
            event.listen(engine, "before_cursor_execute", observe)
            try:
                list_yardi_durable_bindings(
                    run.id, Response(), resource="VENDORS", offset=0, limit=10,
                    db=db, current_user=actor,
                )
            finally:
                event.remove(engine, "before_cursor_execute", observe)
            return len(statements)

        count_one = reviewed_claim_select_count()
        vendor2 = Vendor(organization_id=org.id, company_name="Preserved Second Company")
        db.add(vendor2)
        db.flush()
        _binding(db, run, "VENDORS", "V-2", "VENDOR", vendor2.id)
        db.commit()
        list_yardi_durable_bindings(
            run.id, Response(), resource="VENDORS", offset=0, limit=10,
            db=db, current_user=actor,
        )
        assert reviewed_claim_select_count() == count_one
        db.refresh(vendor2)
        assert vendor2.company_name == "Preserved Second Company"
        db.refresh(vendor)
        assert vendor.company_name == "Preserved Company"
    finally:
        db.close()
        engine.dispose()


def test_yardi_unit_inventory_batches_exact_parent_review_evidence_per_page():
    """Adding a Unit to the preview must not add another staged-review SELECT."""
    from sqlalchemy import event
    from app.models.platform_migration import PlatformMigrationStagedRow
    from app.services.yardi_file_ingestion import stage_yardi_file

    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-inventory-batched-unit-parent")
        prop = Property(
            organization_id=org.id, name="Stable Parent",
            address_line1="301 Main", city="Cleveland", state="OH", zip_code="44113",
        )
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="batched-unit-review", status="DRAFT",
        )
        db.add_all([prop, run])
        db.flush()
        units = [Unit(property_id=prop.id, unit_number=n) for n in ("301", "302")]
        db.add_all(units)
        db.flush()
        _binding(db, run, "PROPERTIES", "P-1", "PROPERTY", prop.id)
        identities = {
            source: _binding(db, run, "UNITS", source, "UNIT", target.id)
            for source, target in zip(("U-1", "U-2"), units)
        }
        db.commit()
        uploaded = stage_yardi_file(
            db, run=run, filename="two-reviewed-units.csv",
            content=b"Unit Ref,Parent Ref,Number\nU-1,P-1,301\nU-2,P-1,302\n",
            resource_override="UNITS", sheet_name=None,
            explicit_mapping={
                "source_id": "Unit Ref", "source_property_id": "Parent Ref",
                "unit_name": "Number",
            }, platform_user_id=actor.id,
        )
        db.commit()
        for row in db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == uploaded.upload.id,
        ).all():
            row.resolution_action = "MATCH_EXISTING"
            identities[row.source_id].source_fingerprint = row.row_fingerprint
            row.resolution_target_unit_id = (
                units[0].id if row.source_id == "U-1" else units[1].id
            )
        db.commit()

        def inspect(limit):
            statements = []
            def observe(connection, cursor, statement, parameters, context, executemany):
                sql = statement.lower()
                if (sql.lstrip().startswith("select")
                        and "platform_migration_staged_rows" in sql
                        and "row_fingerprint" in sql
                        and "resolution_target_unit_id" in sql
                        and "resolution_action" in sql):
                    statements.append(statement)
            event.listen(engine, "before_cursor_execute", observe)
            try:
                result = list_yardi_durable_bindings(
                    run.id, Response(), resource="UNITS", offset=0, limit=limit,
                    db=db, current_user=actor,
                )
            finally:
                event.remove(engine, "before_cursor_execute", observe)
            return result, len(statements)

        result_one, count_one = inspect(1)
        result_two, count_two = inspect(2)
        assert count_one >= 1 and count_two == count_one
        assert len(result_one["items"]) == 1 and len(result_two["items"]) == 2
        assert all(row["target_current"] is True for row in result_two["items"])
        assert all(
            row["unit_parent_relationship_current"] is True
            for row in result_two["items"]
        )
        db.refresh(prop)
        for unit in units:
            db.refresh(unit)
            assert unit.property_id == prop.id
        assert prop.name == "Stable Parent"
    finally:
        db.close()
        engine.dispose()


def test_yardi_unit_parent_inventory_rejects_ambiguous_mapped_property_source():
    """A duplicate parent Property source invalidates Unit source-parent certainty."""
    from app.models.platform_migration import PlatformMigrationStagedRow
    from app.services.yardi_file_ingestion import stage_yardi_file

    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-inventory-property-parent-collision")
        prop = Property(
            organization_id=org.id, name="Preserved Parent",
            address_line1="1 Main", city="Cleveland", state="OH", zip_code="44113",
        )
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="property-source-parent-collision", status="DRAFT",
        )
        db.add_all([prop, run])
        db.flush()
        unit = Unit(property_id=prop.id, unit_number="301")
        db.add(unit)
        db.flush()
        property_binding = _binding(db, run, "PROPERTIES", "P-1", "PROPERTY", prop.id)
        unit_binding = _binding(db, run, "UNITS", "U-1", "UNIT", unit.id)
        db.commit()

        def stage_property(name):
            upload = stage_yardi_file(
                db, run=run, filename="property-parent.csv",
                content=("ID,Name,Street,City,State,Zip\n"
                         "P-1," + name + ",1 Main,Cleveland,OH,44113\n").encode(),
                resource_override="PROPERTIES", sheet_name=None,
                explicit_mapping={
                    "source_id": "ID", "name": "Name", "address_line1": "Street",
                    "city": "City", "state": "State", "zip_code": "Zip",
                }, platform_user_id=actor.id,
            )
            db.commit()
            return db.query(PlatformMigrationStagedRow).filter(
                PlatformMigrationStagedRow.upload_id == upload.upload.id,
            ).one()

        reviewed_property = stage_property("Original Source Parent")
        reviewed_property.resolution_action = "MATCH_EXISTING"
        reviewed_property.resolution_target_id = prop.id
        property_binding.source_fingerprint = reviewed_property.row_fingerprint
        unit_upload = stage_yardi_file(
            db, run=run, filename="unit-parent.csv",
            content=b"Unit Ref,Parent Ref,Number\nU-1,P-1,301\n",
            resource_override="UNITS", sheet_name=None,
            explicit_mapping={
                "source_id": "Unit Ref", "source_property_id": "Parent Ref",
                "unit_name": "Number",
            }, platform_user_id=actor.id,
        )
        db.commit()
        unit_row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == unit_upload.upload.id,
        ).one()
        unit_row.resolution_action = "MATCH_EXISTING"
        unit_row.resolution_target_unit_id = unit.id
        unit_binding.source_fingerprint = unit_row.row_fingerprint
        db.commit()

        def current():
            return list_yardi_durable_bindings(
                run.id, Response(), resource="UNITS", offset=0, limit=10,
                db=db, current_user=actor,
            )["items"][0]

        first = current()
        assert first["target_current"] is True
        assert first["source_identity_collision"] is False
        assert first["unit_parent_relationship_current"] is True
        assert first["parent_source_identity_collision"] is False
        assert first["parent_source_fingerprint_drift"] is False

        competing = stage_property("Different Staged Version")
        ambiguous = current()
        assert ambiguous["target_current"] is True
        assert ambiguous["source_identity_collision"] is False
        assert ambiguous["unit_parent_relationship_current"] is False
        assert ambiguous["parent_source_identity_collision"] is True
        assert ambiguous["parent_source_fingerprint_drift"] is True

        skipped = skip_yardi_staged_row(
            run.id, competing.id, YardiRowSkipIn(reason_code="DUPLICATE_SOURCE"),
            db, actor,
        )
        assert skipped["action"] == "SKIP"
        restored = current()
        assert restored["target_current"] is True
        assert restored["unit_parent_relationship_current"] is True
        assert restored["parent_source_identity_collision"] is False
        assert restored["parent_source_fingerprint_drift"] is False

        # Only one unskipped Property source version remains here, so ordinary
        # duplicate counts are clear. A stale durable parent fingerprint must
        # nevertheless invalidate Unit source-parent readiness.
        original_fingerprint = property_binding.source_fingerprint
        property_binding.source_fingerprint = "stale-property-parent-fingerprint"
        db.commit()
        stale = current()
        assert stale["source_identity_collision"] is False
        assert stale["parent_source_identity_collision"] is False
        assert stale["parent_source_fingerprint_drift"] is True
        assert stale["target_current"] is True
        assert stale["unit_parent_relationship_current"] is False
        property_binding.source_fingerprint = original_fingerprint
        db.commit()
        recovered = current()
        assert recovered["unit_parent_relationship_current"] is True
        assert recovered["parent_source_fingerprint_drift"] is False

        db.refresh(prop)
        db.refresh(unit)
        assert prop.name == "Preserved Parent"
        assert unit.property_id == prop.id
        assert unit.unit_number == "301"
    finally:
        db.close()
        engine.dispose()
