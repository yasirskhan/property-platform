"""Per-lease source identity diagnostics never create customer leases or payments."""
import pytest
from fastapi import HTTPException, Response

from app.models.lease import Lease
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUserRole
from app.models.property import Property, Unit
from app.models.user import User, UserRole
from app.routers.yardi_migrations import list_yardi_lease_relationships
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _org, _platform_user, _session


def test_lease_row_blockers_are_paginated_and_update_when_targets_change():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        org = _org(db, "yardi-lease-row-checks")
        other_org = _org(db, "yardi-lease-row-elsewhere")
        home = Property(
            organization_id=org.id, name="Verified Parent",
            address_line1="1 Main", city="Cleveland", state="OH", zip_code="44113",
        )
        other = Property(
            organization_id=org.id, name="Second Parent",
            address_line1="2 Main", city="Cleveland", state="OH", zip_code="44113",
        )
        tenant = User(
            organization_id=org.id, role=UserRole.TENANT,
            email="lease-row-check@example.test", hashed_password="preserve-hash",
            first_name="Existing", last_name="Tenant", is_active=True,
        )
        outsider = User(
            organization_id=other_org.id, role=UserRole.TENANT,
            email="elsewhere-lease-row@example.test", hashed_password="elsewhere-hash",
            first_name="Other", last_name="Tenant", is_active=True,
        )
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="lease-row-export", status="DRAFT",
        )
        db.add_all([home, other, tenant, outsider, run])
        db.flush()
        unit = Unit(property_id=home.id, unit_number="101")
        db.add(unit)
        db.commit()
        before_leases = db.query(Lease).count()
        upload = stage_yardi_file(
            db, run=run, filename="lease-export.csv",
            content=(
                b"Lease,Resident,Property,Unit\n"
                b"L1,T1,P1,U1\n"
                b"L2,T2,P1,U1\n"
                b"L3,T3,P9,U9\n"
                b"L4,,P1,U1\n"
            ),
            resource_override="LEASE_OCCUPANCY", sheet_name=None,
            explicit_mapping={
                "source_id": "Lease", "source_tenant_id": "Resident",
                "source_property_id": "Property", "source_unit_id": "Unit",
            }, platform_user_id=admin.id,
        )
        db.commit()
        response = Response()
        first = list_yardi_lease_relationships(
            run.id, response, offset=0, limit=2, db=db, current_user=support,
        )
        assert response.headers["cache-control"] == "no-store"
        assert first["total"] == 4
        assert len(first["items"]) == 2
        assert first["items"][0]["blockers"] == [
            "PROPERTY_IDENTITY_UNMAPPED_OR_INACTIVE",
            "UNIT_IDENTITY_UNMAPPED_OR_INACTIVE",
            "TENANT_IDENTITY_UNMAPPED_OR_INACTIVE",
        ]
        assert all(not item["occupancy_or_lease_authorized"] for item in first["items"])
        assert first["read_only"] is True
        assert first["controlled_commit_enabled"] is False
        assert first["customer_business_mutation"] is False
        last = list_yardi_lease_relationships(
            run.id, Response(), offset=2, limit=2, db=db, current_user=admin,
        )
        assert [item["source_id"] for item in last["items"]] == ["L3", "L4"]
        assert last["items"][1]["blockers"] == ["INVALID_OR_SKIPPED"]

        for resource, source, entity, target in (
            ("PROPERTIES", "P1", "PROPERTY", home.id),
            ("UNITS", "U1", "UNIT", unit.id),
            ("TENANTS", "T1", "TENANT_USER", tenant.id),
        ):
            db.add(PlatformMigrationItem(
                run_id=run.id, organization_id=org.id, provider="YARDI",
                resource=resource, source_id=source, target_entity=entity,
                target_id=target, source_fingerprint="reviewed-" + source,
            ))
        db.commit()
        resolved = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=2, db=db, current_user=admin,
        )
        assert resolved["items"][0]["identity_links_complete"] is True
        assert resolved["items"][0]["blockers"] == []
        assert resolved["items"][1]["blockers"] == ["TENANT_IDENTITY_UNMAPPED_OR_INACTIVE"]
        assert "preserve-hash" not in str(resolved)
        assert "lease-row-check@example.test" not in str(resolved)

        unit.property_id = other.id
        db.commit()
        reparented = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=2, db=db, current_user=admin,
        )
        assert reparented["items"][0]["blockers"] == ["UNIT_PROPERTY_MISMATCH"]
        assert reparented["items"][0]["identity_links_complete"] is False
        tenant.is_active = False
        db.commit()
        inactive = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=1, db=db, current_user=admin,
        )
        assert inactive["items"][0]["blockers"] == [
            "TENANT_IDENTITY_UNMAPPED_OR_INACTIVE", "UNIT_PROPERTY_MISMATCH",
        ]
        assert db.query(Lease).count() == before_leases
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
        ).count() == 3
        db.refresh(tenant)
        assert tenant.hashed_password == "preserve-hash"
    finally:
        db.close()
        engine.dispose()


def test_lease_row_review_rejects_unpermitted_roles_and_wrong_provider():
    db, engine = _session()
    try:
        sales = _platform_user(db, PlatformUserRole.PLATFORM_SALES)
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-lease-row-roles")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="read-only-roles", status="DRAFT",
        )
        other = PlatformMigrationRun(
            organization_id=org.id, provider="BUILDIUM",
            source_account_ref="wrong-provider", status="DRAFT",
        )
        db.add_all([run, other])
        db.commit()
        with pytest.raises(HTTPException) as denied:
            list_yardi_lease_relationships(
                run.id, Response(), offset=0, limit=10, db=db, current_user=sales,
            )
        assert denied.value.status_code == 403
        with pytest.raises(HTTPException) as wrong_provider:
            list_yardi_lease_relationships(
                other.id, Response(), offset=0, limit=10, db=db, current_user=admin,
            )
        assert wrong_provider.value.status_code == 404
        empty = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=admin,
        )
        assert empty["total"] == 0 and empty["items"] == []
    finally:
        db.close()
        engine.dispose()
