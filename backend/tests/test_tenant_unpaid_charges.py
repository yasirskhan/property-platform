"""Tenant Unpaid Charges: current Charge snapshots, assignment and permission gates."""
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
from app.models.lease import Lease, LeaseStatus, RentInvoice, InvoiceStatus
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import Organization, User, UserRole
from app.routers import reporting as router
from app.services import tenant_unpaid_charges
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes

KEY = "tenant.unpaid_charges"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    one = Organization(name="Unpaid One", slug="unpaid-one")
    two = Organization(name="Unpaid Two", slug="unpaid-two")
    db.add_all((one, two)); db.flush()
    def user(org, role, name):
        x = User(
            organization_id=org.id, role=role, first_name=name, last_name="Person",
            email=f"{name.lower().replace('=', 'f')}@unpaid.example",
            hashed_password="x", is_active=True,
        )
        db.add(x); db.flush()
        return x
    admin = user(one, UserRole.ADMIN, "Admin")
    manager = user(one, UserRole.MANAGER, "Manager")
    tenant = user(one, UserRole.TENANT, "=Danger")
    other = user(two, UserRole.TENANT, "Foreign")
    def prop(org, name):
        x = Property(
            organization_id=org.id, name=name, address_line1="10 Test St",
            city="Cleveland", state="OH", zip_code="44113", is_active=True,
        )
        db.add(x); db.flush()
        return x
    assigned = prop(one, "Assigned")
    unassigned = prop(one, "Unassigned")
    foreign = prop(two, "Foreign property")
    db.add(PropertyAssignment(
        property_id=assigned.id, user_id=manager.id,
        role=UserRole.MANAGER, is_active=True,
    ))
    accounts = [
        GLAccount(organization_id=org.id, gl_number="5001", name="Fees",
                  account_type="INCOME", is_active=True)
        for org in (one, two)
    ]
    db.add_all(accounts); db.flush()
    def charge(org, who, property_, amount, paid, name, *, active=True, deleted=False):
        x = Charge(
            organization_id=org.id, tenant_user_id=who.id,
            property_id=property_.id if property_ else None,
            charge_date=date.today()-timedelta(days=2),
            description=name, amount=Decimal(amount), amount_paid=Decimal(paid),
            gl_account_id=accounts[0].id if org.id == one.id else accounts[1].id,
            is_active=active, deleted_at=datetime.utcnow() if deleted else None,
        )
        db.add(x); db.flush()
        return x
    partial = charge(one, tenant, assigned, "80", "30", "=Damage")
    due = charge(one, tenant, unassigned, "120", "0", "Utilities")
    unallocated = charge(one, tenant, None, "20", "0", "No property")
    charge(one, tenant, assigned, "25", "25", "Paid")
    charge(one, tenant, assigned, "25", "30", "Credit")
    charge(one, tenant, assigned, "99", "0", "Soft deleted", deleted=True)
    charge(two, other, foreign, "9999", "0", "Private")
    charge(one, tenant, assigned, "50", "0", "Inactive", active=False)
    # A separate rent invoice must NEVER inflate the standalone-charge report.
    unit = Unit(property_id=assigned.id, unit_number="A", is_active=True)
    db.add(unit); db.flush()
    lease = Lease(
        unit_id=unit.id, tenant_id=tenant.id, start_date=date.today(),
        end_date=date.today()+timedelta(days=365), status=LeaseStatus.ACTIVE,
        monthly_rent=Decimal("1000"), security_deposit=Decimal("500"),
    )
    db.add(lease); db.flush()
    db.add(RentInvoice(
        lease_id=lease.id, period_start=date.today(), period_end=date.today(),
        due_date=date.today(), amount_due=Decimal("1000"),
        amount_paid=Decimal("0"), late_fee=Decimal("50"),
        status=InvoiceStatus.PENDING,
    ))
    db.commit()
    return admin, manager, tenant, other, assigned, unassigned, foreign, partial, due, unallocated


def _report(db, actor, **filters):
    return build_report_payload(
        db, organization_id=actor.organization_id,
        report_key=KEY, current_user=actor, parameters=filters,
    )


def test_current_unpaid_charge_math_excludes_rent_paid_credits_deletions_and_foreign(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, other, assigned, unassigned, foreign, partial, due, unallocated = _seed(db)
        monkeypatch.setattr(tenant_unpaid_charges, "permission_allows_user", lambda *a, **kw: True)
        result = _report(db, admin)
        assert {row[4] for row in result.rows} == {partial.id, due.id, unallocated.id}
        assert sum((row[8] for row in result.rows), Decimal(0)) == Decimal("190")
        assert next(row[8] for row in result.rows if row[4] == partial.id) == Decimal("50")
        assert next(row[2] for row in result.rows if row[4] == unallocated.id) == "Unallocated organization charge"
        csv = report_csv_bytes(result).decode("utf-8-sig")
        assert "'=Danger Person" in csv and "'=Damage" in csv
        assert "Private" not in csv and "9999" not in csv
        assert "1000" not in csv
    finally:
        db.close(); engine.dispose()


def test_manager_assignment_unallocated_and_foreign_filters(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, other, assigned, unassigned, foreign, partial, due, unallocated = _seed(db)
        monkeypatch.setattr(tenant_unpaid_charges, "permission_allows_user", lambda *a, **kw: True)
        assert [row[4] for row in _report(db, manager).rows] == [partial.id]
        for p in (unassigned, foreign):
            with pytest.raises(ReportDeliveryError, match="Property not found"):
                _report(db, manager, property_id=p.id)
        with pytest.raises(ReportDeliveryError, match="Tenant not found"):
            _report(db, manager, tenant_id=other.id)
        assert {row[4] for row in _report(db, admin, tenant_id=tenant.id, property_id=assigned.id).rows} == {partial.id}
    finally:
        db.close(); engine.dispose()


def test_bad_filters_revoked_roles_permissions_and_missing_actor(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, other, assigned, unassigned, foreign, partial, due, unallocated = _seed(db)
        monkeypatch.setattr(tenant_unpaid_charges, "permission_allows_user", lambda *a, **kw: True)
        for filters in ({"sql": "SELECT *"}, {"property_id": "-1"}, {"tenant_id": "bad"}):
            with pytest.raises(ReportDeliveryError):
                _report(db, admin, **filters)
        with pytest.raises(ReportDeliveryError, match="Property not found"):
            _report(db, admin, property_id=foreign.id)
        with pytest.raises(ReportDeliveryError):
            _report(db, tenant)
        with pytest.raises(ReportDeliveryError):
            build_report_payload(db, organization_id=admin.organization_id, report_key=KEY, parameters={})
        monkeypatch.setattr(
            tenant_unpaid_charges, "permission_allows_user",
            lambda db, *, user, menu_key: menu_key != "LEASING",
        )
        with pytest.raises(ReportDeliveryError, match="permission required"):
            _report(db, admin)
        monkeypatch.setattr(
            tenant_unpaid_charges, "permission_allows_user",
            lambda db, *, user, menu_key: menu_key != "ACCOUNTING.CHARGES",
        )
        with pytest.raises(ReportDeliveryError, match="permission required"):
            _report(db, manager)
        admin.is_active = False; db.commit()
        with pytest.raises(ReportDeliveryError):
            _report(db, admin)
    finally:
        db.close(); engine.dispose()


def test_catalog_preview_export_email_and_export_gate(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(tenant_unpaid_charges, "permission_allows_user", lambda *a, **kw: True)
        item = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert item.tier == "STANDARD" and item.href == "/dashboard/reporting/unpaid-charges"
        assert router.REPORT_PERMISSIONS[KEY] == "ACCOUNTING.CHARGES"
        monkeypatch.setattr(router, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(
            router, "resolve_customer_features",
            lambda *a, **kw: [SimpleNamespace(key=router.EXPORT_FEATURE_KEY, allowed=True)],
        )
        request = SimpleNamespace(query_params={})
        response = Response()
        preview = router.preview_tenant_unpaid_charges(request, response, db=db, current_user=admin)
        assert preview["total"] == 3
        assert response.headers["cache-control"] == "no-store"
        response_csv = router.export_report_csv(KEY, request, db=db, current_user=admin)
        assert b"Outstanding" in response_csv.body
        sent = {}
        monkeypatch.setattr(router, "send_email", lambda **kw: sent.update(kw))
        emailed = router.email_report(
            KEY, router.ReportEmailIn(recipient="recipient@example.com", parameters={}),
            db=db, current_user=admin,
        )
        assert emailed.sent and b"Outstanding" in sent["attachments"][0][1]
        monkeypatch.setattr(
            router, "resolve_customer_features",
            lambda *a, **kw: [SimpleNamespace(key=router.EXPORT_FEATURE_KEY, allowed=False)],
        )
        with pytest.raises(HTTPException) as exc:
            router.preview_tenant_unpaid_charges(request, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            router.export_report_csv(KEY, request, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()
