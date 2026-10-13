"""Committed Yardi identity metadata is inspectable without customer mutation."""
import pytest
from fastapi import HTTPException, Response

from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUserRole
from app.models.property import Property, Unit
from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.routers.yardi_migrations import list_yardi_durable_bindings
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
