"""Commercial reference reports must not invent leases, money or authority."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.commercial_lease_abstract import CommercialLeaseAbstract
from app.models.charge import Charge
from app.models.gl_transaction import GLTransaction
from app.models.lease import Lease, LeaseStatus, RentInvoice
from app.models.property import Property, PropertyAssignment, PropertyType, Unit
from app.models.user import Organization, User, UserRole
from app.routers import affordable_programs, reporting as report_router
from app.services import commercial_lease_report as report
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes

KEY = "commercial.lease_references"


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    own = Organization(name="Commercial Reporting", slug="commercial-reporting")
    foreign = Organization(name="Other Reporting", slug="other-reporting")
    db.add_all((own, foreign)); db.flush()
    users = []
    for org, role, label in (
        (own, UserRole.ADMIN, "admin"), (own, UserRole.MANAGER, "manager"),
        (own, UserRole.OWNER, "owner"), (own, UserRole.TENANT, "tenant"),
        (foreign, UserRole.ADMIN, "foreign"), (foreign, UserRole.TENANT, "outtenant"),
    ):
        u = User(organization_id=org.id, role=role, first_name=label,
                 last_name="Records", email=f"com-report-{label}@example.com",
                 hashed_password="x", is_active=True)
        db.add(u); users.append(u)
    db.flush()
    props = []
    for org, title, kind in (
        (own, "=Retail", PropertyType.COMMERCIAL),
        (own, "Unassigned Commercial", PropertyType.COMMERCIAL),
        (own, "Residential", PropertyType.MULTI_FAMILY),
        (foreign, "Foreign", PropertyType.COMMERCIAL),
    ):
        prop = Property(organization_id=org.id, name=title, property_type=kind,
                        address_line1="1 Main", city="Cleveland", state="OH",
                        zip_code="44113", is_active=True)
        db.add(prop); props.append(prop)
    db.flush()
    db.add(PropertyAssignment(property_id=props[0].id, user_id=users[1].id,
                              role=UserRole.MANAGER, is_active=True))
    abstracts = []
    leases = []
    for prop, tenant, number, commencement in (
        (props[0], users[3], "=Unit", date(2026, 3, 1)),
        (props[1], users[3], "Not assigned", None),
        (props[2], users[3], "Residential", None),
        (props[3], users[5], "Foreign", None),
    ):
        unit = Unit(property_id=prop.id, unit_number=number,
                    monthly_rent=Decimal("1200"), is_active=True)
        db.add(unit); db.flush()
        lease = Lease(unit_id=unit.id, tenant_id=tenant.id,
                      start_date=date(2026, 1, 1), end_date=date(2027, 1, 1),
                      monthly_rent=Decimal("1200"), security_deposit=0,
                      status=LeaseStatus.ACTIVE)
        db.add(lease); db.flush()
        row = CommercialLeaseAbstract(
            organization_id=prop.organization_id, property_id=prop.id,
            lease_id=lease.id, rent_commencement_on=commencement,
        )
        db.add(row); abstracts.append(row); leases.append(lease)
    db.commit()
    return users, props, leases, abstracts


@pytest.fixture(autouse=True)
def feature_and_menu(monkeypatch):
    monkeypatch.setattr(report, "permission_allows_user", lambda *a, **k: True)
    monkeypatch.setattr(report, "resolve_customer_features", lambda *a, **k: [
        SimpleNamespace(key="release.properties.compliance", allowed=True),
    ])
    monkeypatch.setattr(affordable_programs, "permission_allows_user", lambda *a, **k: True)
    monkeypatch.setattr(affordable_programs, "resolve_customer_features", lambda *a, **k: [
        SimpleNamespace(key=affordable_programs.FEATURE_KEY, allowed=True),
    ])


def _payload(db, actor, **params):
    return build_report_payload(
        db, organization_id=actor.organization_id, report_key=KEY,
        current_user=actor, parameters=params,
    )


def test_report_exact_recorded_data_scope_and_no_finance():
    db, engine = _db()
    try:
        users, props, leases, abstracts = _seed(db)
        admin, manager = users[:2]
        before = (db.query(Charge).count(), db.query(RentInvoice).count(),
                  db.query(GLTransaction).count())
        all_rows = _payload(db, admin)
        assert len(all_rows.rows) == 2
        row = next(x for x in all_rows.rows if x[8] == props[0].id)
        assert row[0] == "=Retail" and row[1] == "=Unit"
        assert row[2] == leases[0].id
        assert row[3] == date(2026, 1, 1)
        assert row[6] == "2026-03-01"
        assert row[7] == "STAFF_RECORDED_UNVERIFIED"
        assert next(x for x in all_rows.rows if x[8] == props[1].id)[6] == ""
        csv_data = report_csv_bytes(all_rows).decode("utf-8-sig")
        assert "'=Retail" in csv_data and "'=Unit" in csv_data
        assigned = _payload(db, manager)
        assert len(assigned.rows) == 1 and assigned.rows[0][8] == props[0].id
        assert len(_payload(db, manager, property_id=props[0].id).rows) == 1
        # A foreign-linked lease must disappear, not disclose a foreign tenant.
        leases[0].tenant_id = users[5].id
        db.flush()
        assert _payload(db, admin, property_id=props[0].id).rows == ()
        assert (db.query(Charge).count(), db.query(RentInvoice).count(),
                db.query(GLTransaction).count()) == before
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_foreign_unassigned_role_bad_filter_and_feature_revocation(monkeypatch):
    db, engine = _db()
    try:
        users, props, leases, _ = _seed(db)
        admin, manager, owner, tenant, foreign = users[:5]
        for prop in (props[1], props[2], props[3]):
            with pytest.raises(ReportDeliveryError, match="not found"):
                _payload(db, manager, property_id=prop.id)
        for actor in (owner, tenant, foreign):
            with pytest.raises(ReportDeliveryError):
                _payload(db, actor, property_id=props[0].id)
        for bad in ({"property_id": "-1"}, {"property_id": "3.5"},
                    {"raw_sql": "users"}, {"report_key": "foo"}):
            with pytest.raises(ReportDeliveryError):
                _payload(db, admin, **bad)
        monkeypatch.setattr(report, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "LEASING")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, admin)
        monkeypatch.setattr(report, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(report, "resolve_customer_features", lambda *a, **k: [
            SimpleNamespace(key="release.properties.compliance", allowed=False),
        ])
        with pytest.raises(ReportDeliveryError, match="unavailable"):
            _payload(db, manager)
        assert db.query(GLTransaction).count() == db.query(Charge).count() == 0
    finally:
        db.close(); engine.dispose()


def test_report_catalog_preview_csv_email_and_export_gate(monkeypatch):
    db, engine = _db()
    try:
        users, props, *_ = _seed(db)
        admin = users[0]
        catalog = next(row for row in REPORT_CATALOG if row.key == KEY)
        assert catalog.href == "/dashboard/reporting/commercial-lease-references"
        assert catalog.available and catalog.category == "Commercial"
        assert report_router.REPORT_PERMISSIONS[KEY] == "LEASING"
        monkeypatch.setattr(report_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(report_router, "resolve_customer_features", lambda *a, **k: [
            SimpleNamespace(key=report_router.EXPORT_FEATURE_KEY, allowed=True),
        ])
        req = SimpleNamespace(query_params={"property_id": str(props[0].id)})
        response = Response()
        result = report_router.preview_commercial_lease_references(
            req, response, db=db, current_user=admin,
        )
        assert result["total"] == 1
        assert response.headers["cache-control"] == "no-store"
        exported = report_router.export_report_csv(
            KEY, req, db=db, current_user=admin,
        )
        assert b"STAFF_RECORDED_UNVERIFIED" in exported.body
        assert b"'=Retail" in exported.body
        sent = {}
        monkeypatch.setattr(report_router, "send_email", lambda **kw: sent.update(kw))
        receipt = report_router.email_report(
            KEY, report_router.ReportEmailIn(
                recipient="staff@example.com",
                parameters={"property_id": str(props[0].id)},
            ), db=db, current_user=admin,
        )
        assert receipt.sent
        assert b"Staff-Recorded Rent Commencement" in sent["attachments"][0][1]
        monkeypatch.setattr(report_router, "resolve_customer_features", lambda *a, **k: [
            SimpleNamespace(key=report_router.EXPORT_FEATURE_KEY, allowed=False),
        ])
        with pytest.raises(HTTPException) as exc:
            report_router.preview_commercial_lease_references(
                req, Response(), db=db, current_user=admin,
            )
        assert exc.value.status_code == 404
        monkeypatch.setattr(report_router, "resolve_customer_features", lambda *a, **k: [
            SimpleNamespace(key=report_router.EXPORT_FEATURE_KEY, allowed=True),
        ])
        monkeypatch.setattr(report_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "LEASING")
        with pytest.raises(HTTPException) as exc:
            report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
    finally:
        db.close(); engine.dispose()
