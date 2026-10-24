"""Posted property performance: real GL signs, scopes, basis and delivery."""
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
from app.models.accounting_settings import AccountingSettings
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.services import property_budgets
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes
from app.routers import reporting as report_router

KEY = "property.performance"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    first_org = Organization(name="Performance One", slug="performance-one")
    foreign_org = Organization(name="Performance Other", slug="performance-other")
    db.add_all((first_org, foreign_org)); db.flush()

    def user(org, role, name):
        x = User(
            organization_id=org.id, role=role, first_name=name,
            last_name="Performance", email=f"{name.lower()}@performance.example",
            hashed_password="x", is_active=True,
        )
        db.add(x); db.flush()
        return x

    admin = user(first_org, UserRole.ADMIN, "Admin")
    manager = user(first_org, UserRole.MANAGER, "Manager")
    tenant = user(first_org, UserRole.TENANT, "Tenant")
    foreign_admin = user(foreign_org, UserRole.ADMIN, "Foreign")

    def prop(org, name):
        p = Property(organization_id=org.id, name=name,
                     address_line1="1 Sample St", city="Cleveland",
                     state="OH", zip_code="44113", is_active=True)
        db.add(p); db.flush()
        return p
    visible = prop(first_org, "=Visible")
    hidden = prop(first_org, "Unassigned")
    foreign = prop(foreign_org, "Secret")
    db.add(PropertyAssignment(
        property_id=visible.id, user_id=manager.id,
        role=UserRole.MANAGER, is_active=True,
    ))
    def account(org, number, kind):
        x = GLAccount(
            organization_id=org.id, gl_number=number,
            name="=Income" if kind == "INCOME" else kind,
            account_type=kind, is_active=True,
        )
        db.add(x); db.flush()
        return x
    income = account(first_org, "4001", "INCOME")
    expense = account(first_org, "6001", "EXPENSE")
    bank = account(first_org, "1001", "ASSET")
    outside_income = account(foreign_org, "4001", "INCOME")

    def entry(acct, prop_, amount, debit, day, org=first_org, reversal=False):
        tx = GLTransaction(
            organization_id=org.id, transaction_date=day,
            transaction_type="REVERSAL" if reversal else "JOURNAL_ENTRY",
        )
        db.add(tx); db.flush()
        db.add(GLEntry(
            organization_id=org.id, transaction_id=tx.id,
            gl_account_id=acct.id, property_id=prop_.id if prop_ else None,
            debit=Decimal(amount) if debit else Decimal("0"),
            credit=Decimal("0") if debit else Decimal(amount),
        ))
        return tx
    entry(income, visible, "1200", False, date(2026, 3, 1))
    entry(income, visible, "200", True, date(2026, 3, 2), reversal=True)
    entry(expense, visible, "350", True, date(2026, 3, 3))
    entry(expense, visible, "50", False, date(2026, 3, 4), reversal=True)
    entry(bank, visible, "999", True, date(2026, 3, 5))
    entry(income, hidden, "9999", False, date(2026, 3, 1))
    entry(income, None, "777", False, date(2026, 3, 1))
    entry(income, visible, "888", False, date(2025, 3, 1))
    entry(outside_income, foreign, "9999", False, date(2026, 3, 1), org=foreign_org)
    db.commit()
    return admin, manager, tenant, foreign_admin, visible, hidden, foreign


def _payload(db, actor, prop, **params):
    return build_report_payload(
        db, organization_id=actor.organization_id,
        report_key=KEY, parameters={
            "property_id": prop.id, "calendar_year": 2026, **params,
        }, current_user=actor,
    )


def test_posted_income_expense_reversal_net_and_no_gl_mutation(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, foreign_admin, visible, hidden, foreign = _seed(db)
        monkeypatch.setattr(property_budgets, "permission_allows_user", lambda *a, **k: True)
        before = db.query(GLEntry).count()
        data = _payload(db, admin, visible)
        assert len(data.rows) == 3
        accounts = {row[4]: row for row in data.rows}
        assert accounts["INCOME"][5:8] == (Decimal("1000"), Decimal(0), Decimal("1000"))
        assert accounts["EXPENSE"][5:8] == (Decimal(0), Decimal("300"), Decimal("-300"))
        assert accounts["TOTAL"][5:8] == (Decimal("1000"), Decimal("300"), Decimal("700"))
        assert "INCOME" in data.title.upper()
        assert db.query(GLEntry).count() == before
        csv = report_csv_bytes(data).decode("utf-8-sig")
        assert "'=Visible" in csv and "'=Income" in csv
        assert "Unassigned" not in csv and "Secret" not in csv
        assert _payload(db, admin, hidden).rows[-1][7] == Decimal("9999")
    finally:
        db.close(); engine.dispose()


def test_scope_basis_bad_filters_and_permission_revocation(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, other, visible, hidden, foreign = _seed(db)
        monkeypatch.setattr(property_budgets, "permission_allows_user", lambda *a, **k: True)
        assert _payload(db, manager, visible).rows[-1][7] == Decimal("700")
        for prop in (hidden, foreign):
            with pytest.raises(ReportDeliveryError, match="Property not found"):
                _payload(db, manager, prop)
        for actor in (tenant, other):
            with pytest.raises(ReportDeliveryError):
                _payload(db, actor, visible)
        for params in ({"sql": "select"}, {"calendar_year": 2100},
                       {"calendar_year": 1999}, {"property_id": -1}):
            with pytest.raises(ReportDeliveryError):
                _payload(db, admin, visible, **params)
        monkeypatch.setattr(property_budgets, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "PROPERTIES.ALL")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, admin, visible)
        monkeypatch.setattr(property_budgets, "permission_allows_user", lambda *a, **k: True)
        db.add(AccountingSettings(organization_id=admin.organization_id, accounting_basis="CASH"))
        db.commit()
        with pytest.raises(ReportDeliveryError, match="ACCRUAL"):
            _payload(db, admin, visible)
    finally:
        db.close(); engine.dispose()


def test_catalog_preview_csv_email_export_gate(monkeypatch):
    db, engine = _session()
    try:
        admin, *_ = _seed(db)
        prop = db.query(Property).filter(Property.name == "=Visible").one()
        monkeypatch.setattr(property_budgets, "permission_allows_user", lambda *a, **k: True)
        item = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert item.presentation == "TAB"
        assert item.href == "/dashboard/reporting/property-performance"
        assert report_router.REPORT_PERMISSIONS[KEY] == "ACCOUNTING.GL_ACCOUNTS"
        monkeypatch.setattr(report_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=True,
                            )])
        req = SimpleNamespace(query_params={"property_id": str(prop.id), "calendar_year": "2026"})
        response = Response()
        preview = report_router.preview_property_performance(req, response, db=db, current_user=admin)
        assert preview["total"] == 3
        assert response.headers["cache-control"] == "no-store"
        csv = report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Posted Net" in csv.body
        sent = {}
        monkeypatch.setattr(report_router, "send_email", lambda **kw: sent.update(kw))
        mailed = report_router.email_report(
            KEY, report_router.ReportEmailIn(
                recipient="admin@example.com",
                parameters={"property_id": prop.id, "calendar_year": 2026},
            ), db=db, current_user=admin,
        )
        assert mailed.sent and b"TOTAL PROPERTY-TAGGED GL" in sent["attachments"][0][1]
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=False,
                            )])
        with pytest.raises(HTTPException) as exc:
            report_router.preview_property_performance(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(report_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()
