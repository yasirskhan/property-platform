"""Current invoice metadata aging, never retroactive or combined with standalone charges."""
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
from app.models.lease import InvoiceStatus, Lease, LeaseStatus, RentInvoice
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import Organization, User, UserRole
from app.services import aged_receivables as aging
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes
from app.routers import reporting as router

KEY = "transaction.aged_receivables"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    a = Organization(name="Receivable One", slug="receivable-one")
    b = Organization(name="Receivable Two", slug="receivable-two")
    db.add_all([a, b]); db.flush()

    def user(org, role, name):
        item = User(organization_id=org.id, role=role, first_name=name,
                    last_name="Aging", email=f"{name}@receivable.example",
                    hashed_password="x", is_active=True)
        db.add(item); db.flush(); return item

    admin = user(a, UserRole.ADMIN, "Admin")
    manager = user(a, UserRole.MANAGER, "Manager")
    tenant = user(a, UserRole.TENANT, "=Formula")
    other = user(b, UserRole.TENANT, "Foreign")
    def property_(org, name):
        item = Property(
            organization_id=org.id, name=name,
            address_line1="100 Test Ave", city="Cleveland",
            state="OH", zip_code="44113", is_active=True,
        )
        db.add(item); db.flush(); return item
    first = property_(a, "Assigned")
    second = property_(a, "Unassigned")
    foreign = property_(b, "Secret")
    db.add(PropertyAssignment(property_id=first.id, user_id=manager.id,
                              role=UserRole.MANAGER, is_active=True))
    db.flush()
    saved = {}
    def invoice(name, prop=first, person=tenant, days=1, amount="100",
                paid="0", fee="0", status=InvoiceStatus.DUE):
        unit = Unit(property_id=prop.id, unit_number=name, is_active=True)
        db.add(unit); db.flush()
        lease = Lease(unit_id=unit.id, tenant_id=person.id,
                      start_date=date.today()-timedelta(days=100),
                      end_date=date.today()+timedelta(days=300),
                      monthly_rent=1000, security_deposit=1000,
                      status=LeaseStatus.ACTIVE)
        db.add(lease); db.flush()
        item = RentInvoice(lease_id=lease.id,
                           period_start=date.today()-timedelta(days=45),
                           period_end=date.today(),
                           due_date=date.today()-timedelta(days=days),
                           amount_due=Decimal(amount), amount_paid=Decimal(paid),
                           late_fee=Decimal(fee), status=status)
        db.add(item); db.flush(); saved[name]=item
        return item
    for label, days in (("1-30",30), ("31-60",31), ("60-days",60),
                        ("61-90",61), ("90-days",90), ("91-plus",91),
                        ("today",0), ("future",-3)):
        invoice(label, days=days)
    invoice("partial", days=10, amount="100", fee="25", paid="75",
            status=InvoiceStatus.PARTIAL)
    invoice("paid", days=300, amount="100", paid="100", status=InvoiceStatus.PAID)
    invoice("void", days=10, status=InvoiceStatus.VOID)
    invoice("unassigned", prop=second, days=2, amount="250")
    invoice("foreign", prop=foreign, person=other, days=4, amount="99999")
    db.commit()
    return admin, manager, tenant, foreign, first, second, saved


def _report(db, user, **params):
    return build_report_payload(
        db, organization_id=user.organization_id, current_user=user,
        report_key=KEY, parameters=params,
    )


def test_bucket_boundaries_partial_paid_exclusion_csv_and_no_changes(monkeypatch):
    db, engine = _session()
    try:
        admin, _, _, _, first, _, saved = _seed(db)
        monkeypatch.setattr(aging, "permission_allows_user", lambda *a, **k: True)
        before = db.query(RentInvoice).count()
        report = _report(db, admin)
        detail = {r[3]: r for r in report.rows if isinstance(r[3], int)}
        assert len(detail) == 10
        for key, bucket in (
            ("1-30","1-30 DAYS"), ("31-60","31-60 DAYS"),
            ("60-days","31-60 DAYS"), ("61-90","61-90 DAYS"),
            ("90-days","61-90 DAYS"), ("91-plus","91+ DAYS"),
            ("today","DUE TODAY"), ("future","NOT YET DUE"),
        ):
            assert detail[saved[key].id][11] == bucket
        assert detail[saved["partial"].id][9] == Decimal("50")
        assert saved["paid"].id not in detail and saved["void"].id not in detail
        buckets = {r[1]:r[9] for r in report.rows if r[0] == "BUCKET"}
        assert buckets["1-30 DAYS"] == Decimal("150")
        assert buckets["31-60 DAYS"] == Decimal("200")
        assert buckets["61-90 DAYS"] == Decimal("200")
        assert buckets["91+ DAYS"] == Decimal("100")
        assert buckets["DUE TODAY"] == Decimal("100")
        assert buckets["NOT YET DUE"] == Decimal("100")
        assert report.rows[-1][9] == Decimal("1100")
        csv = report_csv_bytes(report).decode("utf-8-sig")
        assert "'=Formula Aging" in csv
        assert "99999" not in csv and "Secret" not in csv
        assert db.query(RentInvoice).count() == before
        assert "not posted gl" in report.title.lower()
        assert "standalone Charges" in report.title
    finally:
        db.close(); engine.dispose()


def test_visibility_filters_unchanged_roles_and_status_validation(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, other, first, second, saved = _seed(db)
        monkeypatch.setattr(aging, "permission_allows_user", lambda *a, **k: True)
        manager_report = _report(db, manager)
        assert manager_report.rows[-1][9] == Decimal("850")
        assert _report(db, admin, property_id=second.id).rows[-1][9] == Decimal("250")
        for prop in (second.id, second.id+1000):
            with pytest.raises(ReportDeliveryError, match="Property not found"):
                _report(db, manager, property_id=prop)
        with pytest.raises(ReportDeliveryError, match="Property not found"):
            _report(db, admin, property_id=second.id+1000)
        with pytest.raises(ReportDeliveryError, match="permission"):
            _report(db, tenant)
        for params in (
            {"as_of": (date.today()-timedelta(days=1)).isoformat()},
            {"as_of": (date.today()+timedelta(days=1)).isoformat()},
            {"as_of": "not-a-date"}, {"property_id": -1}, {"sql": "select *"},
            {"tenant_id": 100000},
        ):
            if "tenant_id" in params:
                assert _report(db, admin, **params).rows[-1][9] == 0
            else:
                with pytest.raises(ReportDeliveryError):
                    _report(db, admin, **params)
        monkeypatch.setattr(aging, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "LEASING")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _report(db, admin)
        monkeypatch.setattr(aging, "permission_allows_user", lambda *a, **k: True)
        invoice = saved["partial"]
        invoice.amount_paid = Decimal("999")
        db.flush()
        with pytest.raises(ReportDeliveryError, match="Invalid"):
            _report(db, admin)
        invoice.amount_paid = Decimal("75")
        invoice.status = InvoiceStatus.PAID
        db.flush()
        with pytest.raises(ReportDeliveryError, match="Paid invoice"):
            _report(db, admin)
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_catalog_preview_email_csv_permission_and_gate(monkeypatch):
    db, engine = _session()
    try:
        admin, _, _, _, first, _, saved = _seed(db)
        monkeypatch.setattr(aging, "permission_allows_user", lambda *a, **k: True)
        item = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert item.href == "/dashboard/reporting/aged-receivables"
        assert item.tier == "STANDARD" and item.presentation == "BUTTON"
        assert router.REPORT_PERMISSIONS[KEY] == "LEASING"
        monkeypatch.setattr(router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=router.EXPORT_FEATURE_KEY, allowed=True)])
        req = SimpleNamespace(query_params={"property_id":str(first.id)})
        preview = router.preview_aged_receivables(req, Response(),
                                                 db=db, current_user=admin)
        assert preview["total"] == 16
        csv = router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Current Recorded Unpaid" in csv.body
        sent = {}
        monkeypatch.setattr(router, "send_email", lambda **kw: sent.update(kw))
        outcome = router.email_report(
            KEY, router.ReportEmailIn(recipient="finance@example.com",
                                      parameters={"property_id":first.id}),
            db=db, current_user=admin,
        )
        assert outcome.sent
        assert b"99999" not in sent["attachments"][0][1]
        monkeypatch.setattr(router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=router.EXPORT_FEATURE_KEY, allowed=False)])
        with pytest.raises(HTTPException) as exc:
            router.preview_aged_receivables(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()
