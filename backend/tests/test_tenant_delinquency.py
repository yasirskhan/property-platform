from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.lease import Lease, LeaseStatus, RentInvoice, InvoiceStatus
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
    first = Organization(name="Delinquency One", slug="delinquency-one")
    other = Organization(name="Delinquency Two", slug="delinquency-two")
    db.add_all([first, other])
    db.flush()
    def person(org, role, first_name):
        value = User(
            email=f"{first_name.lower().replace('=', 'f')}@delinquency.example",
            hashed_password="x", first_name=first_name, last_name="Test",
            role=role, organization_id=org.id, is_active=True,
        )
        db.add(value)
        db.flush()
        return value
    admin = person(first, UserRole.ADMIN, "Admin")
    manager = person(first, UserRole.MANAGER, "Manager")
    tenant = person(first, UserRole.TENANT, "=Formula")
    outsider = person(other, UserRole.TENANT, "Secret")
    def property_(org, name):
        value = Property(
            organization_id=org.id, name=name,
            address_line1="100 Test Ave", city="Cleveland", state="OH",
            zip_code="44113", is_active=True,
        )
        db.add(value)
        db.flush()
        return value
    assigned = property_(first, "Assigned")
    unassigned = property_(first, "Unassigned")
    private = property_(other, "Private")
    db.add(PropertyAssignment(
        property_id=assigned.id, user_id=manager.id,
        role=UserRole.MANAGER, is_active=True,
    ))
    db.flush()
    def invoice(prop, person_, balance, *, days=10, paid=0, fee=0, status=InvoiceStatus.DUE):
        unit = Unit(property_id=prop.id, unit_number="A", is_active=True)
        db.add(unit)
        db.flush()
        lease = Lease(
            unit_id=unit.id, tenant_id=person_.id,
            start_date=date.today() - timedelta(days=90),
            end_date=date.today() + timedelta(days=365),
            monthly_rent=1000, security_deposit=1000, status=LeaseStatus.ACTIVE,
        )
        db.add(lease)
        db.flush()
        inv = RentInvoice(
            lease_id=lease.id, period_start=date.today() - timedelta(days=40),
            period_end=date.today(), due_date=date.today() - timedelta(days=days),
            amount_due=Decimal(balance), amount_paid=Decimal(paid),
            late_fee=Decimal(fee), status=status,
        )
        db.add(inv)
        db.flush()
        return inv
    expected = invoice(assigned, tenant, "1000", paid="300", fee="50",
                       status=InvoiceStatus.PARTIAL)
    invoice(assigned, tenant, "1000", paid="1000", days=20, status=InvoiceStatus.PAID)
    invoice(assigned, tenant, "1000", days=-2, status=InvoiceStatus.PENDING)
    invoice(assigned, tenant, "1000", days=40, status=InvoiceStatus.VOID)
    local = invoice(unassigned, tenant, "200", paid="0", days=3)
    foreign = invoice(private, outsider, "8888", paid="0", days=15)
    db.commit()
    return admin, manager, tenant, assigned, unassigned, private, expected, local, foreign


def _report(db, user, **params):
    return build_report_payload(
        db, organization_id=user.organization_id,
        report_key="tenant.delinquency", parameters=params, current_user=user,
    )


def test_current_overdue_math_org_scope_and_formula_escape():
    db, engine = _session()
    try:
        admin, _, _, assigned, unassigned, private, expected, local, foreign = _seed(db)
        payload = _report(db, admin)
        assert len(payload.rows) == 2
        assert payload.rows[0][3] == expected.id
        assert payload.rows[0][5] == 10
        assert payload.rows[0][9] == Decimal("750")
        assert payload.rows[1][9] == Decimal("200")
        text = report_csv_bytes(payload).decode("utf-8-sig")
        assert "'=Formula Test" in text
        assert "8888" not in text
        assert "Private" not in text
        assert foreign.id not in [row[3] for row in payload.rows]
        assert [row[-1] for row in payload.rows] == [assigned.id, unassigned.id]
    finally:
        db.close()
        engine.dispose()


def test_manager_property_assignments_and_unknown_id_are_indistinguishable():
    db, engine = _session()
    try:
        admin, manager, tenant, assigned, unassigned, private, *_ = _seed(db)
        assert len(_report(db, manager).rows) == 1
        assert len(_report(db, manager, property_id=assigned.id).rows) == 1
        for prop in (unassigned, private):
            with pytest.raises(ReportDeliveryError, match="Property not found"):
                _report(db, manager, property_id=prop.id)
        with pytest.raises(ReportDeliveryError, match="Property not found"):
            _report(db, admin, property_id=private.id)
    finally:
        db.close()
        engine.dispose()


def test_untrusted_parameters_and_nonstaff_fail_closed():
    db, engine = _session()
    try:
        admin, manager, tenant, assigned, *_ = _seed(db)
        for parameters in ({"as_of": "2020-01-01"}, {"sql": "SELECT * FROM users"},
                           {"property_id": "-1"}, {"property_id": "abc"}):
            with pytest.raises(ReportDeliveryError):
                _report(db, admin, **parameters)
        with pytest.raises(ReportDeliveryError):
            _report(db, tenant)
        with pytest.raises(ReportDeliveryError):
            build_report_payload(
                db, organization_id=admin.organization_id,
                report_key="tenant.delinquency", parameters={},
            )
        with pytest.raises(ReportDeliveryError):
            build_report_payload(
                db, organization_id=admin.organization_id + 500,
                report_key="tenant.delinquency", parameters={},
                current_user=admin,
            )
        admin.is_active = False
        db.commit()
        with pytest.raises(ReportDeliveryError):
            _report(db, admin)
    finally:
        db.close()
        engine.dispose()


def test_delinquency_catalog_and_preview_no_store():
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        definition = next(row for row in REPORT_CATALOG if row.key == "tenant.delinquency")
        assert definition.tier == "ENHANCED" and definition.presentation == "TAB"
        assert definition.href == "/dashboard/reporting/delinquency"
        assert router.REPORT_PERMISSIONS["tenant.delinquency"] == "LEASING"
        # The controller must not bypass either entitlement or menu checks.
        from app.services import customer_features
        original = router.permission_allows_user
        original_features = router.resolve_customer_features
        try:
            router.permission_allows_user = lambda *a, **kw: True
            router.resolve_customer_features = lambda *a, **kw: [
                SimpleNamespace(key=router.EXPORT_FEATURE_KEY, allowed=True),
            ]
            result = Response()
            preview = router.preview_delinquency(
                SimpleNamespace(query_params={}), result, db=db, current_user=admin,
            )
            assert preview["total"] == 2
            assert result.headers["cache-control"] == "no-store"
            export = router.export_report_csv(
                "tenant.delinquency", SimpleNamespace(query_params={}),
                db=db, current_user=admin,
            )
            assert b"Tenant" in export.body and b"750" in export.body
            router.resolve_customer_features = lambda *a, **kw: [
                SimpleNamespace(key=router.EXPORT_FEATURE_KEY, allowed=False),
            ]
            with pytest.raises(HTTPException) as exc:
                router.preview_delinquency(
                    SimpleNamespace(query_params={}), Response(),
                    db=db, current_user=admin,
                )
            assert exc.value.status_code == 404
            router.permission_allows_user = lambda db, *, user, menu_key: menu_key == "REPORTING.ALL"
            with pytest.raises(HTTPException) as exc:
                router.export_report_csv(
                    "tenant.delinquency", SimpleNamespace(query_params={}),
                    db=db, current_user=admin,
                )
            assert exc.value.status_code == 403
        finally:
            router.permission_allows_user = original
            router.resolve_customer_features = original_features
    finally:
        db.close()
        engine.dispose()
