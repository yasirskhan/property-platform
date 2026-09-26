from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
import app.routers.reporting as reporting_router
import app.services.label_report as label_report
from app.core.database import Base
from app.models.lease import Lease, LeaseStatus
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import Organization, User, UserRole
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org1 = Organization(name="Labels One", slug="labels-one")
    org2 = Organization(name="Labels Two", slug="labels-two")
    db.add_all([org1, org2])
    db.flush()

    def user(org, role, email, first):
        item = User(
            email=email, hashed_password="x", first_name=first, last_name="Recipient",
            organization_id=org.id, role=role, is_active=True,
        )
        db.add(item)
        db.flush()
        return item

    admin = user(org1, UserRole.ADMIN, "labels-admin@example.com", "Admin")
    manager = user(org1, UserRole.MANAGER, "labels-manager@example.com", "Manager")
    tenant = user(org1, UserRole.TENANT, "labels-tenant@example.com", "=Formula")
    other_tenant = user(org2, UserRole.TENANT, "labels-other@example.com", "Secret")
    other_admin = user(org2, UserRole.ADMIN, "labels-other-admin@example.com", "Other")
    def property_(org, name, address):
        prop = Property(
            organization_id=org.id, name=name, address_line1=address,
            city="Cleveland", state="OH", zip_code="44113",
            country="USA", is_active=True,
        )
        db.add(prop)
        db.flush()
        return prop
    first = property_(org1, "First", "100 First Street")
    second = property_(org1, "Unassigned", "200 Second Street")
    other = property_(org2, "Other Secret Property", "999 Private Street")
    db.add(PropertyAssignment(property_id=first.id, user_id=manager.id,
                              role=UserRole.MANAGER, is_active=True))
    db.flush()
    def lease_(prop, person, number, status):
        unit = Unit(property_id=prop.id, unit_number=number, is_active=True)
        db.add(unit)
        db.flush()
        db.add(Lease(
            unit_id=unit.id, tenant_id=person.id,
            start_date=__import__("datetime").date(2026, 1, 1),
            end_date=__import__("datetime").date(2027, 1, 1),
            monthly_rent=1000, security_deposit=1000, status=status,
        ))
    lease_(first, tenant, "2B", LeaseStatus.ACTIVE)
    lease_(second, tenant, "1A", LeaseStatus.ACTIVE)
    lease_(other, other_tenant, "9Z", LeaseStatus.ACTIVE)
    lease_(first, tenant, "3C", LeaseStatus.TERMINATED)
    db.commit()
    return admin, manager, tenant, other_admin, first, second, other


def _payload(db, user, **params):
    return build_report_payload(
        db, organization_id=user.organization_id, report_key="mailing.labels",
        parameters=params, current_user=user,
    )


def test_labels_catalog_and_permission_mapping():
    label = next(item for item in REPORT_CATALOG if item.key == "mailing.labels")
    assert label.available and label.tier == "STANDARD"
    assert label.href == "/dashboard/reporting/labels"
    assert reporting_router.REPORT_PERMISSIONS["mailing.labels"] == "PROPERTIES.ALL"


def test_mail_merge_csv_escapes_formulas_and_never_leaks_other_organization():
    db, engine = _session()
    try:
        admin, _, _, _, first, _, other = _seed(db)
        labels = _payload(db, admin, recipient_type="TENANT")
        csv_text = report_csv_bytes(labels).decode("utf-8-sig")
        assert labels.headers[:3] == ("RecipientName", "AddressLine1", "AddressLine2")
        assert len(labels.rows) == 2
        assert "'=Formula Recipient" in csv_text
        assert "Unit 2B" in csv_text
        assert "999 Private Street" not in csv_text
        assert "Secret Recipient" not in csv_text
        assert other.id not in [row[-1] for row in labels.rows]
        single = _payload(db, admin, recipient_type="PROPERTY", property_id=first.id)
        assert len(single.rows) == 1 and single.rows[0][1] == "100 First Street"
    finally:
        db.close()
        engine.dispose()


def test_manager_scope_excludes_unassigned_records_and_property_id_probing():
    db, engine = _session()
    try:
        _, manager, _, _, first, second, other = _seed(db)
        assert [row[-1] for row in _payload(db, manager).rows] == [first.id]
        assert len(_payload(db, manager, recipient_type="TENANT").rows) == 1
        for prop in (second, other):
            with pytest.raises(ReportDeliveryError, match="Property not found"):
                _payload(db, manager, property_id=prop.id)
    finally:
        db.close()
        engine.dispose()


def test_invalid_filters_missing_user_and_nonstaff_fail_closed():
    db, engine = _session()
    try:
        admin, _, tenant, other_admin, first, _, other = _seed(db)
        for params in (
            {"recipient_type": "VENDOR"}, {"sql": "SELECT * FROM users"},
            {"property_id": "-1"}, {"property_id": "abc"},
        ):
            with pytest.raises(ReportDeliveryError):
                _payload(db, admin, **params)
        with pytest.raises(ReportDeliveryError):
            _payload(db, admin, property_id=other.id)
        with pytest.raises(ReportDeliveryError):
            _payload(db, tenant)
        with pytest.raises(ReportDeliveryError):
            build_report_payload(db, organization_id=admin.organization_id,
                                 report_key="mailing.labels", parameters={})
        with pytest.raises(ReportDeliveryError):
            build_report_payload(db, organization_id=other_admin.organization_id,
                                 report_key="mailing.labels", parameters={},
                                 current_user=admin)
    finally:
        db.close()
        engine.dispose()


def test_tenant_labels_require_lease_permission(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(label_report, "permission_allows_user",
                            lambda db, *, user, menu_key: False)
        assert len(_payload(db, admin).rows) == 2
        with pytest.raises(ReportDeliveryError, match="Lease permission"):
            _payload(db, admin, recipient_type="TENANT")
    finally:
        db.close()
        engine.dispose()


def test_preview_export_and_email_recheck_permissions_and_release_gate(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(reporting_router, "permission_allows_user",
                            lambda *args, **kwargs: True)
        monkeypatch.setattr(label_report, "permission_allows_user",
                            lambda *args, **kwargs: True)
        monkeypatch.setattr(
            reporting_router, "resolve_customer_features",
            lambda *args, **kwargs: [
                SimpleNamespace(key=reporting_router.EXPORT_FEATURE_KEY, allowed=True)
            ],
        )
        req = SimpleNamespace(query_params={"recipient_type": "PROPERTY"})
        preview = reporting_router.preview_labels(req, db=db, current_user=admin)
        assert preview["total"] == 2
        exported = reporting_router.export_report_csv("mailing.labels", req, db=db, current_user=admin)
        assert b"RecipientName" in exported.body
        assert b"100 First Street" in exported.body
        sent = {}
        monkeypatch.setattr(reporting_router, "send_email", lambda **kwargs: sent.update(kwargs))
        result = reporting_router.email_report(
            "mailing.labels",
            reporting_router.ReportEmailIn(recipient="recipient@example.com",
                                           parameters={"recipient_type": "PROPERTY"}),
            db=db, current_user=admin,
        )
        assert result.sent is True
        assert sent["organization_id"] == admin.organization_id
        assert sent["attachments"][0][0] == "property-mail-merge.csv"
        assert b"999 Private Street" not in sent["attachments"][0][1]

        monkeypatch.setattr(
            reporting_router, "resolve_customer_features",
            lambda *args, **kwargs: [
                SimpleNamespace(key=reporting_router.EXPORT_FEATURE_KEY, allowed=False)
            ],
        )
        for action in (
            lambda: reporting_router.preview_labels(req, db=db, current_user=admin),
            lambda: reporting_router.export_report_csv("mailing.labels", req, db=db, current_user=admin),
        ):
            with pytest.raises(HTTPException) as exc:
                action()
            assert exc.value.status_code == 404
        monkeypatch.setattr(reporting_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            reporting_router.preview_labels(req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()
