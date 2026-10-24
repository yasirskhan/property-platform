"""Yardi reconciliation durable identities are resource-keyed and deterministic."""
from fastapi import Response

from app.models.platform_migration import (
    PlatformMigrationItem, PlatformMigrationRun, PlatformMigrationStagedRow,
)
from app.models.platform_user import PlatformUserRole
from app.models.property import Property, Unit
from app.models.vendor import Vendor
from app.routers.yardi_migrations import get_yardi_reconciliation
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _org, _platform_user, _session


def test_reconciliation_same_source_literal_across_resources_and_unit_parent():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-reconciliation-composite-resource")
        prop = Property(
            organization_id=org.id, name="Preserved Customer Property",
            address_line1="1 Main", city="Cleveland", state="OH", zip_code="44113",
        )
        vendor = Vendor(organization_id=org.id, company_name="Preserved Company")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="shared-source-literal", status="DRAFT",
        )
        db.add_all([prop, vendor, run])
        db.flush()
        unit = Unit(property_id=prop.id, unit_number="101")
        db.add(unit)
        db.flush()
        configurations = (
            ("PROPERTIES", b"ID,Name,Street,City,State,Zip\nSHARED,Imported,1 Main,Cleveland,OH,44113\n",
             {"source_id": "ID", "name": "Name", "address_line1": "Street",
              "city": "City", "state": "State", "zip_code": "Zip"},
             "SHARED", "PROPERTY", prop.id),
            ("VENDORS", b"ID,Name\nSHARED,Imported Vendor\n",
             {"source_id": "ID", "name": "Name"},
             "SHARED", "VENDOR", vendor.id),
            ("UNITS", b"Unit,Parent,Label\nU1,SHARED,101\n",
             {"source_id": "Unit", "source_property_id": "Parent",
              "unit_name": "Label"},
             "U1", "UNIT", unit.id),
        )
        mappings = {}
        for resource, content, fields, source, entity, target in configurations:
            uploaded = stage_yardi_file(
                db, run=run, filename=resource.lower() + ".csv",
                content=content, resource_override=resource, sheet_name=None,
                explicit_mapping=fields, platform_user_id=actor.id,
            )
            db.commit()
            staged = db.query(PlatformMigrationStagedRow).filter(
                PlatformMigrationStagedRow.upload_id == uploaded.upload.id,
            ).one()
            assert staged.disposition != "INVALID" and not staged.errors
            binding = PlatformMigrationItem(
                run_id=run.id, organization_id=org.id, provider="YARDI",
                resource=resource, source_id=source, target_entity=entity,
                target_id=target, source_fingerprint=staged.row_fingerprint,
            )
            mappings[resource] = binding
            db.add(binding)
            db.commit()
        def current():
            return get_yardi_reconciliation(run.id, Response(), db, actor)

        ready = current()
        for resource in ("PROPERTIES", "VENDORS", "UNITS"):
            assert ready["resource_coverage"][resource]["mapped"] == 1
            assert ready["resource_coverage"][resource]["needs_review"] == 0

        # A corrupt Vendor entity type must not invalidate the unrelated
        # Property identity with the same literal source ID or its Unit parent.
        mappings["VENDORS"].target_entity = "PROPERTY"
        db.commit()
        wrong_vendor = current()
        assert wrong_vendor["resource_coverage"]["VENDORS"]["mapped"] == 0
        assert wrong_vendor["resource_coverage"]["VENDORS"]["needs_review"] == 1
        assert wrong_vendor["resource_coverage"]["PROPERTIES"]["mapped"] == 1
        assert wrong_vendor["resource_coverage"]["UNITS"]["mapped"] == 1
        assert wrong_vendor["review_fingerprint"] != ready["review_fingerprint"]

        mappings["VENDORS"].target_entity = "VENDOR"
        db.commit()
        recovered = current()
        assert recovered["review_fingerprint"] == ready["review_fingerprint"]
        db.refresh(prop)
        db.refresh(unit)
        db.refresh(vendor)
        assert prop.name == "Preserved Customer Property"
        assert unit.property_id == prop.id and unit.unit_number == "101"
        assert vendor.company_name == "Preserved Company"
        assert recovered["customer_business_mutation"] is False
    finally:
        db.close()
        engine.dispose()
