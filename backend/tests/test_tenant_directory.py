"""Current tenant directory: scoped lease and contact visibility."""
from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.lease import Lease, LeaseStatus
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import Organization, User, UserRole
from app.routers import reporting as router
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes


REPORT_KEY = "tenant.directory"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Directory Org", slug="directory-org")
    other = Organization(name="Other Directory Org", slug="other-directory-org")
    db.add_all([org, other])
    db.flush()
    def user(organization, role, name):
        row = User(
            email=f"{name.lower().replace('=', 'f')}@directory.example",
            hashed_password="x", first_name=name, last_name="Test",
            role=role, organization_id=organization.id, is_active=True,
        )
        db.add(row)
        db.flush()
        return row
    admin = user(org, UserRole.ADMIN, "Admin")
    manager = user(org, UserRole.MANAGER, "Manager")
    local = user(org, UserRole.TENANT, "=Local")
    idle = user(org, UserRole.TENANT, "Idle")
    historical = user(org, UserRole.TENANT, "Historical")
    foreign_tenant = user(other, UserRole.TENANT, "Foreign")
    inactive = user(org, UserRole.TENANT, "Inactive")
    inactive.is_active = False
    def prop(organization, name):
        p = Property(
            organization_id=organization.id, name=name, address_line1="1 Test Ave",
            city="Cleveland", state="OH", zip_code="44113", is_active=True,
        )
        db.add(p)
        db.flush()
        return p
    assigned = prop(org, "Assigned")
    unassigned = prop(org, "Unassigned")
    secret = prop(other, "Secret")
    db.add(PropertyAssignment(
        property_id=assigned.id, user_id=manager.id, role=UserRole.MANAGER,
        is_active=True,
    ))
    db.flush()
    def lease(property_, tenant, status, suffix, *, start=-30, end=30):
        unit = Unit(property_id=property_.id, unit_number=suffix, is_active=True)
        db.add(unit)
        db.flush()
        row = Lease(
            unit_id=unit.id, tenant_id=tenant.id,
            start_date=date.today() + timedelta(days=start),
            end_date=date.today() + timedelta(days=end),
            monthly_rent=1000, security_deposit=500,
            status=status,
        )
        db.add(row)
        db.flush()
        return row
    first = lease(assigned, local, LeaseStatus.ACTIVE, "A")
    second = lease(unassigned, local, LeaseStatus.ACTIVE, "B")
    old = lease(assigned, historical, LeaseStatus.TERMINATED, "C")
    future = lease(assigned, historical, LeaseStatus.ACTIVE, "D", start=30)
    foreign_lease = lease(secret, foreign_tenant, LeaseStatus.ACTIVE, "E")
    inactive_lease = lease(assigned, inactive, LeaseStatus.ACTIVE, "F")
    db.commit()
    return {
        "admin":admin, "manager":manager, "local":local, "idle":idle,
        "historical":historical, "foreign_tenant":foreign_tenant,
        "assigned":assigned, "unassigned":unassigned, "secret":secret,
        "first":first, "second":second, "old":old, "future":future,
        "foreign_lease":foreign_lease, "inactive_lease":inactive_lease,
    }


def _report(db, user, **params):
    return build_report_payload(
        db, organization_id=user.organization_id, report_key=REPORT_KEY,
        parameters=params, current_user=user,
    )


def test_admin_current_leases_unassigned_tenants_and_csv_formula_escape():
    db, engine = _session()
    try:
        s = _seed(db)
        rows = _report(db, s["admin"]).rows
        assert len(rows) == 4
        assert sum(1 for row in rows if row[0] == s["local"].id) == 2
        assert any(row[0] == s["idle"].id and row[9] == "No eligible current lease"
                   for row in rows)
        assert any(row[0] == s["historical"].id and row[9] == "No eligible current lease"
                   for row in rows)
        assert s["foreign_lease"].id not in [r[6] for r in rows]
        assert s["old"].id not in [r[6] for r in rows]
        assert s["future"].id not in [r[6] for r in rows]
        csv_text = report_csv_bytes(_report(db, s["admin"])).decode("utf-8-sig")
        assert "'=Local Test" in csv_text
        assert "Foreign Test" not in csv_text
        assert "Secret" not in csv_text
    finally:
        db.close()
        engine.dispose()


def test_manager_only_assigned_current_leases_no_unassigned_contact_leak():
    db, engine = _session()
    try:
        s = _seed(db)
        rows = _report(db, s["manager"]).rows
        assert len(rows) == 1
        assert rows[0][0] == s["local"].id and rows[0][6] == s["first"].id
        assert all(row[0] != s["idle"].id for row in rows)
        for p in (s["unassigned"], s["secret"]):
            with pytest.raises(ReportDeliveryError, match="Property not found"):
                _report(db, s["manager"], property_id=p.id)
        filtered = _report(db, s["admin"], property_id=s["assigned"].id)
        assert len(filtered.rows) == 1
        assert filtered.rows[0][6] == s["first"].id
        with pytest.raises(ReportDeliveryError, match="Property not found"):
            _report(db, s["admin"], property_id=s["secret"].id)
    finally:
        db.close()
        engine.dispose()


def test_invalid_parameters_tenant_staff_and_inactive_admin_fail_closed():
    db, engine = _session()
    try:
        s = _seed(db)
        for params in (
            {"sql": "select * from users"},
            {"property_id": "-1"}, {"property_id": "invalid"},
        ):
            with pytest.raises(ReportDeliveryError):
                _report(db, s["admin"], **params)
        with pytest.raises(ReportDeliveryError):
            _report(db, s["local"])
        with pytest.raises(ReportDeliveryError):
            build_report_payload(
                db, organization_id=s["admin"].organization_id,
                report_key=REPORT_KEY, parameters={},
            )
        with pytest.raises(ReportDeliveryError):
            build_report_payload(
                db, organization_id=s["secret"].organization_id,
                report_key=REPORT_KEY, parameters={}, current_user=s["admin"],
            )
        s["admin"].is_active = False
        db.commit()
        with pytest.raises(ReportDeliveryError):
            _report(db, s["admin"])
    finally:
        db.close()
        engine.dispose()


def test_preview_email_csv_access_and_feature_revocation(monkeypatch):
    db, engine = _session()
    try:
        s = _seed(db)
        admin = s["admin"]
        definition = next(x for x in REPORT_CATALOG if x.key == REPORT_KEY)
        assert definition.tier == "STANDARD"
        assert definition.href == "/dashboard/reporting/tenants"
        assert router.REPORT_PERMISSIONS[REPORT_KEY] == "LEASING"
        monkeypatch.setattr(router, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(
            router, "resolve_customer_features",
            lambda *a, **kw: [SimpleNamespace(key=router.EXPORT_FEATURE_KEY, allowed=True)],
        )
        request = SimpleNamespace(query_params={})
        response = Response()
        preview = router.preview_tenant_directory(
            request, response, db=db, current_user=admin,
        )
        assert preview["total"] == 4
        assert response.headers["cache-control"] == "no-store"
        exported = router.export_report_csv(REPORT_KEY, request, db=db, current_user=admin)
        assert b"Tenant ID" in exported.body
        sent = {}
        monkeypatch.setattr(router, "send_email", lambda **kw: sent.update(kw))
        result = router.email_report(
            REPORT_KEY,
            router.ReportEmailIn(recipient="recipient@example.com", parameters={}),
            db=db, current_user=admin,
        )
        assert result.sent
        assert sent["organization_id"] == admin.organization_id
        assert b"Tenant ID" in sent["attachments"][0][1]
        monkeypatch.setattr(
            router, "resolve_customer_features",
            lambda *a, **kw: [SimpleNamespace(key=router.EXPORT_FEATURE_KEY, allowed=False)],
        )
        with pytest.raises(HTTPException) as exc:
            router.preview_tenant_directory(
                request, Response(), db=db, current_user=admin,
            )
        assert exc.value.status_code == 404
        monkeypatch.setattr(
            router, "resolve_customer_features",
            lambda *a, **kw: [SimpleNamespace(key=router.EXPORT_FEATURE_KEY, allowed=True)],
        )
        monkeypatch.setattr(
            router, "permission_allows_user",
            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL",
        )
        with pytest.raises(HTTPException) as exc:
            router.export_report_csv(REPORT_KEY, request, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()
