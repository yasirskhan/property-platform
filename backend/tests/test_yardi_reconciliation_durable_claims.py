"""Cross-run durable source/target drift invalidates Yardi run reconciliation."""
import pytest
from fastapi import Response

from app.models.platform_migration import (
    PlatformMigrationItem, PlatformMigrationRun, PlatformMigrationStagedRow,
)
from app.models.platform_user import PlatformUserRole
from app.models.property import Property, Unit
from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.routers.yardi_migrations import get_yardi_reconciliation
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _org, _platform_user, _session


@pytest.mark.parametrize("resource", [
    "PROPERTIES", "UNITS", "OWNERS", "VENDORS", "TENANTS",
])
def test_reconciliation_revalidates_durable_claims_for_every_identity_resource(resource):
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-reconcile-cross-run-" + resource.lower())
        foreign = _org(db, "yardi-reconcile-cross-run-foreign-" + resource.lower())
        prop1 = Property(
            organization_id=org.id, name="Customer Original",
            address_line1="1 Main", city="Cleveland", state="OH", zip_code="44113",
        )
        prop2 = Property(
            organization_id=org.id, name="Customer Alternate",
            address_line1="2 Main", city="Cleveland", state="OH", zip_code="44113",
        )
        owner1 = User(
            organization_id=org.id, role=UserRole.OWNER,
            email="owner-one-" + resource.lower() + "@example.test",
            hashed_password="preserved-owner-hash",
            first_name="Original", last_name="Owner", is_active=True,
        )
        owner2 = User(
            organization_id=org.id, role=UserRole.OWNER,
            email="owner-two-" + resource.lower() + "@example.test",
            hashed_password="preserved-owner-two-hash",
            first_name="Alternate", last_name="Owner", is_active=True,
        )
        tenant1 = User(
            organization_id=org.id, role=UserRole.TENANT,
            email="tenant-one-" + resource.lower() + "@example.test",
            hashed_password="preserved-tenant-hash",
            first_name="Original", last_name="Tenant", is_active=True,
        )
        tenant2 = User(
            organization_id=org.id, role=UserRole.TENANT,
            email="tenant-two-" + resource.lower() + "@example.test",
            hashed_password="preserved-tenant-two-hash",
            first_name="Alternate", last_name="Tenant", is_active=True,
        )
        vendor1 = Vendor(organization_id=org.id, company_name="Preserved Vendor")
        vendor2 = Vendor(organization_id=org.id, company_name="Alternate Vendor")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI", source_account_ref="current",
            status="DRAFT",
        )
        other = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI", source_account_ref="other",
            status="DRAFT",
        )
        outside = PlatformMigrationRun(
            organization_id=foreign.id, provider="YARDI", source_account_ref="foreign",
            status="DRAFT",
        )
        buildium = PlatformMigrationRun(
            organization_id=org.id, provider="BUILDIUM", source_account_ref="buildium",
            status="DRAFT",
        )
        db.add_all([
            prop1, prop2, owner1, owner2, tenant1, tenant2, vendor1, vendor2,
            run, other, outside, buildium,
        ])
        db.flush()
        unit1 = Unit(property_id=prop1.id, unit_number="101")
        unit2 = Unit(property_id=prop1.id, unit_number="102")
        db.add_all([unit1, unit2])
        db.flush()

        definitions = {
            "PROPERTIES": (
                "P1", "PROPERTY", prop1.id, prop2.id, "resolution_target_id",
                b"ID,Name,Street,City,State,Zip\nP1,Source,1 Main,Cleveland,OH,44113\n",
                {"source_id": "ID", "name": "Name", "address_line1": "Street",
                 "city": "City", "state": "State", "zip_code": "Zip"},
            ),
            "UNITS": (
                "U1", "UNIT", unit1.id, unit2.id, "resolution_target_unit_id",
                b"Unit,Parent,Label\nU1,P1,101\n",
                {"source_id": "Unit", "source_property_id": "Parent",
                 "unit_name": "Label"},
            ),
            "OWNERS": (
                "O1", "OWNER_USER", owner1.id, owner2.id,
                "resolution_target_owner_user_id",
                b"Owner Ref,Owner Label\nO1,Source Owner\n",
                {"source_id": "Owner Ref", "name": "Owner Label"},
            ),
            "VENDORS": (
                "V1", "VENDOR", vendor1.id, vendor2.id,
                "resolution_target_vendor_id",
                b"Vendor Ref,Vendor Label\nV1,Source Vendor\n",
                {"source_id": "Vendor Ref", "name": "Vendor Label"},
            ),
            "TENANTS": (
                "T1", "TENANT_USER", tenant1.id, tenant2.id,
                "resolution_target_tenant_user_id",
                b"Resident Ref,Resident Name\nT1,Source Resident\n",
                {"source_id": "Resident Ref", "name": "Resident Name"},
            ),
        }
        source_id, entity, target_id, alternate_id, target_field, content, mapping = definitions[resource]
        if resource == "UNITS":
            db.add(PlatformMigrationItem(
                run_id=run.id, organization_id=org.id, provider="YARDI",
                resource="PROPERTIES", source_id="P1", target_entity="PROPERTY",
                target_id=prop1.id, source_fingerprint="parent-fingerprint",
            ))
        staged = stage_yardi_file(
            db, run=run, filename=resource.lower() + "-reconcile.csv",
            content=content, resource_override=resource, sheet_name=None,
            explicit_mapping=mapping, platform_user_id=actor.id,
        )
        db.commit()
        row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == staged.upload.id,
        ).one()
        assert row.disposition != "INVALID" and not row.errors
        row.resolution_action = "MATCH_EXISTING"
        setattr(row, target_field, target_id)
        db.add(PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="YARDI",
            resource=resource, source_id=source_id, target_entity=entity,
            target_id=target_id, source_fingerprint=row.row_fingerprint,
        ))
        db.commit()

        def inspect():
            return get_yardi_reconciliation(run.id, Response(), db, actor)

        current = inspect()
        assert current["resource_coverage"][resource]["matched_existing"] == 1
        assert current["customer_business_mutation"] is False

        # Another provider and another organization are independent evidence.
        for ignored_run in (outside, buildium):
            db.add(PlatformMigrationItem(
                run_id=ignored_run.id, organization_id=ignored_run.organization_id,
                provider=ignored_run.provider, resource=resource,
                source_id=resource + "-OTHER", target_entity=entity,
                target_id=target_id, source_fingerprint="external-fingerprint",
            ))
        db.commit()
        isolated = inspect()
        assert isolated["review_fingerprint"] == current["review_fingerprint"]
        assert isolated["resource_coverage"][resource]["matched_existing"] == 1

        conflicting = PlatformMigrationItem(
            run_id=other.id, organization_id=org.id, provider="YARDI",
            resource=resource, source_id=resource + "-OTHER", target_entity=entity,
            target_id=target_id, source_fingerprint="other-fingerprint",
        )
        db.add(conflicting)
        db.commit()
        target_collision = inspect()
        assert target_collision["resource_coverage"][resource]["matched_existing"] == 0
        assert target_collision["resource_coverage"][resource]["needs_review"] == 1
        assert target_collision["review_fingerprint"] != current["review_fingerprint"]

        conflicting.source_id = source_id
        db.commit()
        same_source = inspect()
        assert same_source["resource_coverage"][resource]["matched_existing"] == 1
        assert same_source["review_fingerprint"] == current["review_fingerprint"]

        conflicting.target_id = alternate_id
        db.commit()
        source_collision = inspect()
        assert source_collision["resource_coverage"][resource]["matched_existing"] == 0
        assert source_collision["review_fingerprint"] != current["review_fingerprint"]

        conflicting.target_id = target_id
        db.commit()
        restored = inspect()
        assert restored["review_fingerprint"] == current["review_fingerprint"]
        assert restored["resource_coverage"][resource]["matched_existing"] == 1
        db.refresh(prop1)
        db.refresh(unit1)
        db.refresh(owner1)
        db.refresh(tenant1)
        db.refresh(vendor1)
        assert prop1.name == "Customer Original"
        assert unit1.property_id == prop1.id
        assert owner1.hashed_password == "preserved-owner-hash"
        assert tenant1.hashed_password == "preserved-tenant-hash"
        assert vendor1.company_name == "Preserved Vendor"
        db.refresh(row)
        assert row.resolution_action == "MATCH_EXISTING"
        assert getattr(row, target_field) == target_id
    finally:
        db.close()
        engine.dispose()
