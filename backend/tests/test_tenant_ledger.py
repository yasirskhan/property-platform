from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.charge import Charge
from app.models.gl_account import GLAccount
from app.models.lease import Lease, LeaseStatus, RentInvoice, InvoiceStatus, Payment
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import Organization, User, UserRole
from app.routers import reporting as router
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    one = Organization(name="Ledger One", slug="tenant-ledger-one")
    two = Organization(name="Ledger Two", slug="tenant-ledger-two")
    db.add_all([one, two]); db.flush()
    def user(org, role, name):
        row = User(organization_id=org.id, role=role,
                   first_name=name, last_name="Resident",
                   email=f"{name.lower().replace('=', 'f')}@ledger.example",
                   hashed_password="x", is_active=True)
        db.add(row); db.flush()
        return row
    admin = user(one, UserRole.ADMIN, "Admin")
    manager = user(one, UserRole.MANAGER, "Manager")
    tenant = user(one, UserRole.TENANT, "=Formula")
    outsider = user(two, UserRole.TENANT, "Secret")
    def prop(org, name):
        row = Property(organization_id=org.id, name=name,
                       address_line1="1 Test Street", city="Cleveland",
                       state="OH", zip_code="44113", is_active=True)
        db.add(row); db.flush()
        return row
    first = prop(one, "First")
    second = prop(one, "Second")
    foreign = prop(two, "Foreign")
    db.add(PropertyAssignment(property_id=first.id, user_id=manager.id,
                              role=UserRole.MANAGER, is_active=True))
    db.flush()
    def lease_(p, u, number):
        unit = Unit(property_id=p.id, unit_number=number, is_active=True)
        db.add(unit); db.flush()
        lease = Lease(
            unit_id=unit.id, tenant_id=u.id, status=LeaseStatus.ACTIVE,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=90),
            monthly_rent=1000, security_deposit=500)
        db.add(lease); db.flush()
        return lease, unit
    lease1, unit1 = lease_(first, tenant, "A")
    lease2, unit2 = lease_(second, tenant, "B")
    other_lease, other_unit = lease_(foreign, outsider, "X")
    def invoice(lease, *, amount, paid, fee, status=InvoiceStatus.PARTIAL):
        item = RentInvoice(
            lease_id=lease.id,
            period_start=date.today() - timedelta(days=30),
            period_end=date.today(),
            due_date=date.today() - timedelta(days=1),
            amount_due=Decimal(amount), amount_paid=Decimal(paid),
            late_fee=Decimal(fee), status=status,
        )
        db.add(item); db.flush()
        return item
    inv1 = invoice(lease1, amount="1000", paid="300", fee="50")
    inv2 = invoice(lease2, amount="200", paid="50", fee="0")
    inv3 = invoice(lease1, amount="100", paid="0", fee="0", status=InvoiceStatus.VOID)
    foreign_inv = invoice(other_lease, amount="9999", paid="0", fee="0")
    # Legacy Payment record records the same $300 stored in inv1.amount_paid.
    db.add(Payment(invoice_id=inv1.id, amount=Decimal("300"),
                   paid_at=datetime.utcnow()))
    charge_gl = GLAccount(organization_id=one.id, gl_number="5001",
                          name="Damage income", account_type="INCOME",
                          is_active=True)
    db.add(charge_gl); db.flush()
    def charge(p, u, n, *, amount, paid="0"):
        item = Charge(
            organization_id=one.id, tenant_user_id=u.id,
            unit_id=n, property_id=p, gl_account_id=charge_gl.id,
            charge_date=date.today(), description="=Damage",
            amount=Decimal(amount), amount_paid=Decimal(paid),
            is_paid=False, is_active=True,
        )
        db.add(item); db.flush()
        return item
    charge1 = charge(first.id, tenant, unit1.id, amount="80", paid="30")
    charge2 = charge(None, tenant, None, amount="20")
    charge3 = charge(second.id, tenant, unit2.id, amount="30", paid="10")
    db.commit()
    return admin, manager, tenant, outsider, first, second, foreign, inv1, inv2, inv3, foreign_inv, charge1, charge2, charge3


def _report(db, user, **filters):
    return build_report_payload(
        db, organization_id=user.organization_id,
        report_key="tenant.ledger", parameters=filters, current_user=user,
    )


def test_current_snapshots_do_not_double_count_legacy_payment_and_receipt():
    db, engine = _session()
    try:
        admin, manager, tenant, other, first, second, foreign, inv1, inv2, inv3, foreign_inv, charge1, charge2, charge3 = _seed(db)
        report = _report(db, admin)
        assert len(report.rows) == 5
        balances = {(row[4], row[5]): row[9] for row in report.rows}
        assert balances["Rent invoice", inv1.id] == Decimal("750")
        assert balances["Rent invoice", inv2.id] == Decimal("150")
        assert balances["Standalone charge", charge1.id] == Decimal("50")
        assert balances["Standalone charge", charge2.id] == Decimal("20")
        assert balances["Standalone charge", charge3.id] == Decimal("20")
        assert sum((row[9] for row in report.rows), Decimal(0)) == Decimal("990")
        assert foreign_inv.id not in [r[5] for r in report.rows if r[4] == "Rent invoice"]
        text = report_csv_bytes(report).decode("utf-8-sig")
        assert "'=Formula Resident" in text
        assert "'=Damage" in text
        assert "Secret Resident" not in text
        assert "9999" not in text
    finally:
        db.close(); engine.dispose()


def test_manager_only_assigned_property_invoices_charges_no_unallocated():
    db, engine = _session()
    try:
        admin, manager, tenant, other, first, second, foreign, inv1, inv2, inv3, foreign_inv, charge1, charge2, charge3 = _seed(db)
        result = _report(db, manager)
        assert len(result.rows) == 2
        assert {row[5] for row in result.rows} == {inv1.id, charge1.id}
        assert {row[4] for row in result.rows} == {"Rent invoice", "Standalone charge"}
        for p in (second, foreign):
            with pytest.raises(ReportDeliveryError, match="Property not found"):
                _report(db, manager, property_id=p.id)
        with pytest.raises(ReportDeliveryError, match="Tenant not found"):
            _report(db, manager, tenant_id=other.id)
        assert len(_report(db, admin, tenant_id=tenant.id, property_id=first.id).rows) == 2
    finally:
        db.close(); engine.dispose()


def test_revoked_charge_permission_blocks_ledger_even_with_leasing(monkeypatch):
    from app.services import tenant_ledger
    db, engine = _session()
    try:
        admin, manager, tenant, *_ = _seed(db)
        # Both reporting/LEASING gates might remain granted, but the
        # standalone charge API's own ACCOUNTING.CHARGES access was revoked.
        monkeypatch.setattr(
            tenant_ledger, "permission_allows_user",
            lambda db, *, user, menu_key: menu_key != "ACCOUNTING.CHARGES",
        )
        for actor in (admin, manager):
            with pytest.raises(ReportDeliveryError, match="permission required"):
                _report(db, actor, tenant_id=tenant.id)
    finally:
        db.close()
        engine.dispose()


def test_bad_params_foreign_tenant_and_no_actor_fail_closed():
    db, engine = _session()
    try:
        admin, manager, tenant, other, first, *_ = _seed(db)
        for params in ({"as_of":"2021-01-01"}, {"sql":"SELECT * FROM payments"},
                       {"tenant_id":"-1"}, {"property_id":"abc"}):
            with pytest.raises(ReportDeliveryError):
                _report(db, admin, **params)
        with pytest.raises(ReportDeliveryError, match="Tenant not found"):
            _report(db, admin, tenant_id=other.id)
        with pytest.raises(ReportDeliveryError):
            _report(db, tenant)
        with pytest.raises(ReportDeliveryError):
            build_report_payload(db, organization_id=admin.organization_id,
                                 report_key="tenant.ledger", parameters={})
        manager.is_active = False
        db.commit()
        with pytest.raises(ReportDeliveryError):
            _report(db, manager)
    finally:
        db.close(); engine.dispose()


def test_permission_and_export_revocation_on_preview_csv_email(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        catalog = next(x for x in REPORT_CATALOG if x.key == "tenant.ledger")
        assert catalog.tier == "ENHANCED" and catalog.presentation == "TAB"
        assert catalog.href == "/dashboard/reporting/tenant-ledger"
        assert router.REPORT_PERMISSIONS["tenant.ledger"] == "LEASING"
        monkeypatch.setattr(router, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(router, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(
                                key=router.EXPORT_FEATURE_KEY, allowed=True,
                            )])
        request = SimpleNamespace(query_params={})
        response = Response()
        preview = router.preview_tenant_ledger(request, response, db=db, current_user=admin)
        assert preview["total"] == 5
        assert response.headers["cache-control"] == "no-store"
        exported = router.export_report_csv("tenant.ledger", request, db=db, current_user=admin)
        assert b"Current Balance" in exported.body
        monkeypatch.setattr(router, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(
                                key=router.EXPORT_FEATURE_KEY, allowed=False,
                            )])
        with pytest.raises(HTTPException) as exc:
            router.preview_tenant_ledger(request, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(router, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(
                                key=router.EXPORT_FEATURE_KEY, allowed=True,
                            )])
        monkeypatch.setattr(router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            router.export_report_csv("tenant.ledger", request, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()
