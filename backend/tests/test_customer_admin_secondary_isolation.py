from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.lease import Lease, LeaseStatus
from app.models.property import Property, PropertyType, Unit
from app.models.tax import PropertyTax, PropertyTaxPayment, TaxType
from app.models.user import Organization, User, UserRole
from app.models.utility import PropertyUtility, UtilityType
from app.routers import password_reset as password_reset_router
from app.routers.org_email import _check_org_access as check_email_org_access
from app.routers.screening_settings import _check_org_access as check_screening_org_access
from app.routers.taxes import list_tax_payments
from app.routers.tenant_insurance import _check_lease_access, compliance_view
from app.routers.utilities import _get_utility


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org_a = Organization(name="Org A", slug="secondary-a")
    org_b = Organization(name="Org B", slug="secondary-b")
    db.add_all([org_a, org_b])
    db.flush()
    admin_a = User(
        email="secondary-admin-a@example.com",
        hashed_password="unused",
        first_name="Admin",
        last_name="A",
        role=UserRole.ADMIN,
        organization_id=org_a.id,
        is_active=True,
    )
    tenant_a = User(
        email="secondary-tenant-a@example.com",
        hashed_password="unused",
        first_name="Tenant",
        last_name="A",
        role=UserRole.TENANT,
        organization_id=org_a.id,
        is_active=True,
    )
    tenant_b = User(
        email="secondary-tenant-b@example.com",
        hashed_password="unused",
        first_name="Tenant",
        last_name="B",
        role=UserRole.TENANT,
        organization_id=org_b.id,
        is_active=True,
    )
    db.add_all([admin_a, tenant_a, tenant_b])
    db.flush()
    prop_a = Property(
        organization_id=org_a.id,
        name="A",
        property_type=PropertyType.MULTI_FAMILY,
        address_line1="1 A St",
        city="Cleveland",
        state="OH",
        zip_code="44113",
    )
    prop_b = Property(
        organization_id=org_b.id,
        name="B",
        property_type=PropertyType.MULTI_FAMILY,
        address_line1="2 B St",
        city="Cleveland",
        state="OH",
        zip_code="44113",
    )
    db.add_all([prop_a, prop_b])
    db.flush()
    unit_a = Unit(property_id=prop_a.id, unit_number="A1", bedrooms=1, bathrooms=1, monthly_rent=1000)
    unit_b = Unit(property_id=prop_b.id, unit_number="B1", bedrooms=1, bathrooms=1, monthly_rent=1000)
    db.add_all([unit_a, unit_b])
    db.flush()
    lease_a = Lease(
        unit_id=unit_a.id,
        tenant_id=tenant_a.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        monthly_rent=1000,
        security_deposit=0,
        status=LeaseStatus.ACTIVE,
    )
    lease_b = Lease(
        unit_id=unit_b.id,
        tenant_id=tenant_b.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        monthly_rent=1000,
        security_deposit=0,
        status=LeaseStatus.ACTIVE,
    )
    db.add_all([lease_a, lease_b])
    db.flush()
    utility_a = PropertyUtility(
        property_id=prop_a.id,
        utility_type=UtilityType.WATER,
        company_name="A Water",
    )
    utility_b = PropertyUtility(
        property_id=prop_b.id,
        utility_type=UtilityType.WATER,
        company_name="B Water",
    )
    tax_b = PropertyTax(
        property_id=prop_b.id,
        tax_authority="County B",
        tax_type=TaxType.COUNTY,
    )
    db.add_all([utility_a, utility_b, tax_b])
    db.flush()
    payment_b = PropertyTaxPayment(
        tax_id=tax_b.id,
        amount=100,
        paid_at=date(2026, 9, 1),
    )
    db.add(payment_b)
    db.commit()
    return locals()


def test_customer_admin_org_settings_are_same_org_only() -> None:
    db, engine = _session()
    try:
        x = _seed(db)
        check_email_org_access(x["admin_a"], x["org_a"].id)
        check_screening_org_access(x["admin_a"], x["org_a"].id)
        with pytest.raises(HTTPException) as exc:
            check_email_org_access(x["admin_a"], x["org_b"].id)
        assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc:
            check_screening_org_access(x["admin_a"], x["org_b"].id)
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_customer_admin_cannot_force_reset_foreign_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, engine = _session()
    try:
        x = _seed(db)
        monkeypatch.setattr(
            password_reset_router.auth_logic,
            "get_user_by_id",
            lambda _db, _id: x["tenant_b"],
        )
        with pytest.raises(HTTPException) as exc:
            password_reset_router.force_reset(
                x["tenant_b"].id,
                db,
                x["admin_a"],
            )
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_tenant_insurance_admin_scope_and_compliance_are_same_org_only() -> None:
    db, engine = _session()
    try:
        x = _seed(db)
        with pytest.raises(HTTPException) as exc:
            _check_lease_access(db, x["admin_a"], x["lease_b"])
        assert exc.value.status_code == 403
        rows = compliance_view(db, x["admin_a"])
        assert {row["lease_id"] for row in rows} == {x["lease_a"].id}
    finally:
        db.close()
        engine.dispose()


def test_nested_utility_and_tax_ids_cannot_cross_property_boundary() -> None:
    db, engine = _session()
    try:
        x = _seed(db)
        assert (
            _get_utility(db, x["prop_a"].id, x["utility_a"].id).id
            == x["utility_a"].id
        )
        with pytest.raises(HTTPException) as exc:
            _get_utility(db, x["prop_a"].id, x["utility_b"].id)
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            list_tax_payments(
                x["prop_a"].id,
                x["tax_b"].id,
                db,
                x["admin_a"],
            )
        assert exc.value.status_code == 404
    finally:
        db.close()
        engine.dispose()
