from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.lease import Lease, LeaseStatus, RentInvoice
from app.models.property import Property, PropertyAssignment, PropertyType, Unit
from app.models.user import Organization, User, UserRole
from app.models.work_order import WorkOrder, WorkOrderCategory, WorkOrderPriority, WorkOrderUpdate
from app.routers.leases import _check_lease_access, list_leases
from app.routers.payments import _check_invoice_access
from app.routers.users import _scoped_org_id, assign_user_to_property, get_user, list_users
from app.routers.work_orders import _user_can_access_work_order, _visible_work_orders

TEST_TABLES = [
    Organization.__table__,
    User.__table__,
    Property.__table__,
    Unit.__table__,
    PropertyAssignment.__table__,
    Lease.__table__,
    RentInvoice.__table__,
    WorkOrder.__table__,
    WorkOrderUpdate.__table__,
]


def _session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=TEST_TABLES)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org_a = Organization(name="Org A", slug="org-a")
    org_b = Organization(name="Org B", slug="org-b")
    db.add_all([org_a, org_b])
    db.flush()

    admin_a = User(email="admin-a@example.com", hashed_password="x", first_name="A", last_name="Admin", role=UserRole.ADMIN, organization_id=org_a.id, is_active=True)
    admin_b = User(email="admin-b@example.com", hashed_password="x", first_name="B", last_name="Admin", role=UserRole.ADMIN, organization_id=org_b.id, is_active=True)
    tenant_a = User(email="tenant-a@example.com", hashed_password="x", first_name="A", last_name="Tenant", role=UserRole.TENANT, organization_id=org_a.id, is_active=True)
    tenant_b = User(email="tenant-b@example.com", hashed_password="x", first_name="B", last_name="Tenant", role=UserRole.TENANT, organization_id=org_b.id, is_active=True)
    crew_b = User(email="crew-b@example.com", hashed_password="x", first_name="B", last_name="Crew", role=UserRole.CREW, organization_id=org_b.id, is_active=True)
    db.add_all([admin_a, admin_b, tenant_a, tenant_b, crew_b])
    db.flush()

    prop_a = Property(organization_id=org_a.id, name="A", property_type=PropertyType.MULTI_FAMILY, address_line1="1 A", city="Cleveland", state="OH", zip_code="44113")
    prop_b = Property(organization_id=org_b.id, name="B", property_type=PropertyType.MULTI_FAMILY, address_line1="2 B", city="Cleveland", state="OH", zip_code="44113")
    db.add_all([prop_a, prop_b])
    db.flush()

    unit_a = Unit(property_id=prop_a.id, unit_number="A1", bedrooms=1, bathrooms=1, monthly_rent=1000)
    unit_b = Unit(property_id=prop_b.id, unit_number="B1", bedrooms=1, bathrooms=1, monthly_rent=1000)
    db.add_all([unit_a, unit_b])
    db.flush()

    lease_a = Lease(unit_id=unit_a.id, tenant_id=tenant_a.id, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), monthly_rent=1000, security_deposit=0, status=LeaseStatus.ACTIVE)
    lease_b = Lease(unit_id=unit_b.id, tenant_id=tenant_b.id, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), monthly_rent=1000, security_deposit=0, status=LeaseStatus.ACTIVE)
    db.add_all([lease_a, lease_b])
    db.flush()

    invoice_b = RentInvoice(lease_id=lease_b.id, period_start=date(2026, 9, 1), period_end=date(2026, 9, 30), due_date=date(2026, 9, 1), amount_due=1000, amount_paid=0)
    wo_b = WorkOrder(unit_id=unit_b.id, property_id=prop_b.id, tenant_id=tenant_b.id, title="B work", description="x", category=WorkOrderCategory.GENERAL, priority=WorkOrderPriority.MEDIUM)
    db.add_all([invoice_b, wo_b])
    db.commit()
    return {
        "org_a": org_a,
        "org_b": org_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "crew_b": crew_b,
        "prop_a": prop_a,
        "prop_b": prop_b,
        "lease_a": lease_a,
        "lease_b": lease_b,
        "invoice_b": invoice_b,
        "wo_b": wo_b,
    }


def test_customer_admin_user_scope_is_own_org_only():
    db, engine = _session()
    try:
        x = _seed(db)
        assert _scoped_org_id(x["admin_a"], None) == x["org_a"].id
        with pytest.raises(HTTPException) as exc:
            _scoped_org_id(x["admin_a"], x["org_b"].id)
        assert exc.value.status_code == 403

        listed = list_users(None, db, x["admin_a"])
        assert listed
        assert all(u.organization_id == x["org_a"].id for u in listed)

        with pytest.raises(HTTPException) as exc:
            get_user(x["admin_b"].id, db, x["admin_a"])
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_customer_admin_cannot_assign_foreign_user_to_own_property():
    db, engine = _session()
    try:
        x = _seed(db)
        with pytest.raises(HTTPException) as exc:
            assign_user_to_property(x["prop_a"].id, x["crew_b"].id, db, x["admin_a"])
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_customer_admin_lease_and_invoice_scope_is_own_org_only():
    db, engine = _session()
    try:
        x = _seed(db)
        with pytest.raises(HTTPException) as exc:
            _check_lease_access(db, x["admin_a"], x["lease_b"])
        assert exc.value.status_code == 403

        with pytest.raises(HTTPException) as exc:
            _check_invoice_access(db, x["admin_a"], x["invoice_b"])
        assert exc.value.status_code == 403

        listed = list_leases(db, x["admin_a"])
        assert listed
        for lease in listed:
            unit = db.get(Unit, lease.unit_id)
            prop = db.get(Property, unit.property_id)
            assert prop.organization_id == x["org_a"].id
    finally:
        db.close()
        engine.dispose()


def test_customer_admin_work_order_scope_is_own_org_only():
    db, engine = _session()
    try:
        x = _seed(db)
        assert _user_can_access_work_order(db, x["admin_a"], x["wo_b"]) is False
        rows = _visible_work_orders(db, x["admin_a"]).all()
        for wo in rows:
            prop = db.get(Property, wo.property_id)
            assert prop.organization_id == x["org_a"].id
    finally:
        db.close()
        engine.dispose()
