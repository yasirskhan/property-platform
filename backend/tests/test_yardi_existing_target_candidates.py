"""Staff-only Yardi target candidate picker is bounded, isolated and read-only."""
import pytest
from fastapi import HTTPException, Response
from app.models.platform_migration import PlatformMigrationRun
from app.models.platform_user import PlatformUserRole
from app.models.property import Property, Unit
from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.routers.yardi_migrations import list_yardi_existing_targets
from test_yardi_migrations import _org, _platform_user, _session


def _seed(db):
    admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
    support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
    org = _org(db, "yardi-target-candidates")
    other_org = _org(db, "yardi-target-other-org")
    home = Property(
        organization_id=org.id, name="Alpha Court",
        address_line1="1 Main", city="Cleveland", state="OH", zip_code="44113",
    )
    outside = Property(
        organization_id=other_org.id, name="Alpha Other",
        address_line1="2 Main", city="Cleveland", state="OH", zip_code="44113",
    )
    run = PlatformMigrationRun(
        organization_id=org.id, provider="YARDI",
        source_account_ref="target-picker", status="DRAFT",
    )
    vendor = Vendor(organization_id=org.id, company_name="Atlas Plumbing")
    owner = User(
        organization_id=org.id, role=UserRole.OWNER,
        first_name="Jordan", last_name="Owner", email="picker-owner@example.test",
        hashed_password="secret-hash", is_active=True,
    )
    tenant = User(
        organization_id=org.id, role=UserRole.TENANT,
        first_name="Jordan", last_name="Resident", email="picker-tenant@example.test",
        hashed_password="secret-hash", is_active=True,
    )
    db.add_all([home, outside, run, vendor, owner, tenant])
    db.flush()
    unit = Unit(property_id=home.id, unit_number="A-101")
    db.add(unit)
    db.commit()
    return admin, support, org, run, home, outside, unit, vendor, owner, tenant


def _search(db, actor, run, resource, q):
    return list_yardi_existing_targets(
        run.id, Response(), resource=resource, q=q, limit=20,
        db=db, current_user=actor,
    )


def test_yardi_candidate_search_is_org_scoped_bounded_and_redacted():
    db, engine = _session()
    try:
        admin, support, org, run, home, outside, unit, vendor, owner, tenant = _seed(db)
        property_results = _search(db, admin, run, "PROPERTIES", "Alpha")
        assert property_results["candidates"] == [{"id": home.id, "label": "Alpha Court"}]
        assert property_results["auto_match_enabled"] is False
        assert property_results["customer_business_mutation"] is False
        assert _search(db, admin, run, "UNITS", "A-101")["candidates"] == [
            {"id": unit.id, "label": "A-101 — Alpha Court"},
        ]
        assert _search(db, admin, run, "VENDORS", "Atlas")["candidates"] == [
            {"id": vendor.id, "label": "Atlas Plumbing"},
        ]
        assert _search(db, admin, run, "OWNERS", "Jordan")["candidates"] == [
            {"id": owner.id, "label": "Jordan Owner"},
        ]
        assert _search(db, admin, run, "TENANTS", "Jordan")["candidates"] == [
            {"id": tenant.id, "label": "Jordan Resident"},
        ]
        assert "secret-hash" not in str(property_results)
        assert "example.test" not in str(_search(db, admin, run, "OWNERS", "Jordan"))
        assert outside.id not in [x["id"] for x in property_results["candidates"]]
        with pytest.raises(HTTPException) as readonly:
            _search(db, support, run, "VENDORS", "Atlas")
        assert readonly.value.status_code == 403
        with pytest.raises(HTTPException) as short:
            _search(db, admin, run, "VENDORS", " ")
        assert short.value.status_code == 422
        assert db.query(Unit).count() == 1
        assert db.query(Vendor).count() == 1
        assert db.query(User).count() == 2
    finally:
        db.close()
        engine.dispose()


def test_yardi_candidates_exclude_inactive_targets_and_escape_sql_wildcards():
    db, engine = _session()
    try:
        admin, _, org, run, home, outside, unit, vendor, owner, tenant = _seed(db)
        extra = Property(
            organization_id=org.id, name="A% literal",
            address_line1="3 Main", city="Cleveland", state="OH", zip_code="44113",
        )
        db.add(extra)
        db.commit()
        assert _search(db, admin, run, "PROPERTIES", "A%")["candidates"] == [
            {"id": extra.id, "label": "A% literal"}
        ]
        owner.is_active = False
        vendor.deleted_at = __import__("datetime").datetime.utcnow()
        db.commit()
        assert _search(db, admin, run, "OWNERS", "Jordan")["candidates"] == []
        assert _search(db, admin, run, "VENDORS", "Atlas")["candidates"] == []
    finally:
        db.close()
        engine.dispose()
