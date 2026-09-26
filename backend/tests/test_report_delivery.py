from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
import app.routers.reporting as reporting_router
from app.core.database import Base
from app.models.gl_account import GLAccount
from app.models.user import Organization, User, UserRole
from app.services.report_delivery import (
    ReportDeliveryError,
    build_report_payload,
    report_csv_bytes,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Report Delivery Org", slug="report-delivery-org")
    other = Organization(name="Other Report Org", slug="other-report-org")
    db.add_all([org, other])
    db.flush()
    admin = User(
        email="report-delivery@example.com",
        hashed_password="x",
        first_name="Report",
        last_name="Admin",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
    )
    db.add(admin)
    db.add_all(
        [
            GLAccount(
                organization_id=org.id,
                gl_number="1000",
                name="=Potential Formula",
                account_type="ASSET",
                is_active=True,
            ),
            GLAccount(
                organization_id=other.id,
                gl_number="9999",
                name="Other Org Secret",
                account_type="ASSET",
                is_active=True,
            ),
        ]
    )
    db.commit()
    return org, admin


def test_chart_of_accounts_delivery_is_org_scoped_and_csv_safe():
    db, engine = _session()
    try:
        org, _ = _seed(db)
        payload = build_report_payload(
            db,
            organization_id=org.id,
            report_key="accounting.chart_of_accounts",
            parameters={},
        )
        csv_text = report_csv_bytes(payload).decode("utf-8-sig")
        assert "1000" in csv_text
        assert "'=Potential Formula" in csv_text
        assert "Other Org Secret" not in csv_text
    finally:
        db.close()
        engine.dispose()


def test_unknown_report_cannot_be_delivered():
    db, engine = _session()
    try:
        org, _ = _seed(db)
        with pytest.raises(ReportDeliveryError):
            build_report_payload(
                db,
                organization_id=org.id,
                report_key="accounting.future_report",
                parameters={},
            )
    finally:
        db.close()
        engine.dispose()


def test_delivery_requires_framework_and_report_permissions(monkeypatch):
    user = SimpleNamespace(organization_id=42)

    def permissions(_db, *, user, menu_key):
        return menu_key == "REPORTING.ALL"

    monkeypatch.setattr(reporting_router, "permission_allows_user", permissions)
    with pytest.raises(HTTPException) as exc:
        reporting_router._require_report_access(
            object(),
            current_user=user,
            report_key="accounting.trial_balance",
        )
    assert exc.value.status_code == 403


def test_email_delivery_generates_server_side_csv(monkeypatch):
    db, engine = _session()
    try:
        org, admin = _seed(db)
        monkeypatch.setattr(reporting_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(
            reporting_router,
            "resolve_customer_features",
            lambda *a, **k: [
                SimpleNamespace(key=reporting_router.EXPORT_FEATURE_KEY, allowed=True)
            ],
        )
        sent = {}
        monkeypatch.setattr(reporting_router, "send_email", lambda **kwargs: sent.update(kwargs))
        result = reporting_router.email_report(
            "accounting.chart_of_accounts",
            reporting_router.ReportEmailIn(
                recipient="recipient@example.com",
                parameters={},
            ),
            db=db,
            current_user=admin,
        )
        assert result.sent is True
        assert sent["organization_id"] == org.id
        assert sent["attachments"][0][0] == "chart-of-accounts.csv"
        assert b"Potential Formula" in sent["attachments"][0][1]
    finally:
        db.close()
        engine.dispose()
