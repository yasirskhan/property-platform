"""Yardi lease relationship coverage is descriptive, scoped, and nonmutating."""
from fastapi import Response
from app.models.lease import Lease
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUserRole
from app.models.property import Property, Unit
from app.models.user import User, UserRole
from app.routers.yardi_migrations import get_yardi_reconciliation
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _org, _platform_user, _session


def test_lease_dependency_coverage_detects_missing_mismatched_and_deactivated_targets():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-lease-coverage")
        prop = Property(
            organization_id=org.id, name="Mapped Property",
            address_line1="1 Main", city="Cleveland", state="OH", zip_code="44113",
        )
        alternative = Property(
            organization_id=org.id, name="Other Property",
            address_line1="2 Main", city="Cleveland", state="OH", zip_code="44113",
        )
        tenant = User(
            organization_id=org.id, role=UserRole.TENANT,
            email="yardi-lease-coverage@example.test", hashed_password="unchanged-hash",
            first_name="Resident", last_name="Existing", is_active=True,
        )
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="lease-coverage-export", status="DRAFT",
        )
        db.add_all([prop, alternative, tenant, run])
        db.flush()
        unit = Unit(property_id=prop.id, unit_number="101")
        db.add(unit)
        db.commit()
        before_leases = db.query(Lease).count()
        stage_yardi_file(
            db, run=run, filename="leases.csv",
            content=b"Lease,Resident,Property,Unit\nL1,T1,P1,U1\n",
            resource_override="LEASE_OCCUPANCY", sheet_name=None,
            explicit_mapping={
                "source_id": "Lease", "source_tenant_id": "Resident",
                "source_property_id": "Property", "source_unit_id": "Unit",
            }, platform_user_id=actor.id,
        )
        db.commit()
        initial = get_yardi_reconciliation(run.id, Response(), db, actor)
        coverage = initial["lease_relationship_readiness"]
        assert coverage["staged"] == 1
        assert coverage["complete_identity_links"] == 0
        assert coverage["missing_property"] == 1
        assert coverage["missing_unit"] == 1
        assert coverage["missing_tenant"] == 1
        for resource, source_id, entity, target_id in (
            ("PROPERTIES", "P1", "PROPERTY", prop.id),
            ("UNITS", "U1", "UNIT", unit.id),
            ("TENANTS", "T1", "TENANT_USER", tenant.id),
        ):
            db.add(PlatformMigrationItem(
                run_id=run.id, organization_id=org.id, provider="YARDI",
                resource=resource, source_id=source_id,
                target_entity=entity, target_id=target_id,
                source_fingerprint="reviewed-source-" + resource,
            ))
        db.commit()
        matched = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert matched["lease_relationship_readiness"]["complete_identity_links"] == 1
        assert matched["lease_relationship_readiness"]["controlled_commit_enabled"] is False
        assert matched["review_fingerprint"] != initial["review_fingerprint"]

        unit.property_id = alternative.id
        db.commit()
        mismatched = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert mismatched["lease_relationship_readiness"]["complete_identity_links"] == 0
        assert mismatched["lease_relationship_readiness"]["unit_property_mismatch"] == 1
        assert mismatched["review_fingerprint"] != matched["review_fingerprint"]

        tenant.is_active = False
        db.commit()
        unavailable = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert unavailable["lease_relationship_readiness"]["missing_tenant"] == 1
        assert unavailable["lease_relationship_readiness"]["customer_business_mutation"] is False
        assert db.query(Lease).count() == before_leases
        db.refresh(tenant)
        assert tenant.hashed_password == "unchanged-hash"
    finally:
        db.close()
        engine.dispose()
