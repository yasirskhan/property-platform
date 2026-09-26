"""Property budget target isolation, posted GL comparison, review and delivery."""
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
from app.models.audit_log import AuditLog
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.property import Property, PropertyAssignment
from app.models.property_budget import PropertyBudgetLine
from app.models.user import Organization, User, UserRole
from app.routers import reporting as report_router
from app.schemas.property_budget import PropertyBudgetUpsertIn
from app.services import property_budgets
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes

KEY = "property.budget_comparison"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    a = Organization(name="Budgets One", slug="budgets-one")
    b = Organization(name="Budgets Two", slug="budgets-two")
    db.add_all((a, b)); db.flush()
    def user(org, role, name):
        u = User(
            email=f"{name.lower()}@budget.example",
            organization_id=org.id, role=role,
            first_name=name, last_name="Staff", hashed_password="x",
            is_active=True,
        )
        db.add(u); db.flush()
        return u
    admin = user(a, UserRole.ADMIN, "Admin")
    manager = user(a, UserRole.MANAGER, "Manager")
    tenant = user(a, UserRole.TENANT, "Tenant")
    other_admin = user(b, UserRole.ADMIN, "Foreign")
    def prop(org, name):
        x = Property(organization_id=org.id, name=name,
                     address_line1="1 Budget St", city="Cleveland", state="OH",
                     zip_code="44113", is_active=True)
        db.add(x); db.flush()
        return x
    first = prop(a, "=First")
    second = prop(a, "Second")
    foreign = prop(b, "Foreign")
    db.add(PropertyAssignment(
        property_id=first.id, user_id=manager.id,
        role=UserRole.MANAGER, is_active=True,
    ))
    def account(org, number, category):
        row = GLAccount(organization_id=org.id, gl_number=number,
                        name="=Rent" if category=="INCOME" else "Repairs",
                        account_type=category, is_active=True)
        db.add(row); db.flush()
        return row
    income = account(a, "4001", "INCOME")
    expense = account(a, "6001", "EXPENSE")
    bank = account(a, "1001", "ASSET")
    foreign_income = account(b, "4001", "INCOME")
    def entry(account_, amount, is_debit, month, *, reversal=False, property_=first, org=a):
        tx = GLTransaction(
            organization_id=org.id, transaction_date=date(2026, month, 12),
            transaction_type="REVERSAL" if reversal else "JOURNAL_ENTRY",
            is_reversed=False,
        )
        db.add(tx); db.flush()
        db.add(GLEntry(
            organization_id=org.id, transaction_id=tx.id,
            gl_account_id=account_.id, property_id=property_.id,
            debit=Decimal(amount) if is_debit else Decimal(0),
            credit=Decimal(amount) if not is_debit else Decimal(0),
        ))
        db.add(GLEntry(
            organization_id=org.id, transaction_id=tx.id,
            gl_account_id=bank.id if org.id == a.id else foreign_income.id,
            property_id=property_.id,
            debit=Decimal(0) if is_debit else Decimal(amount),
            credit=Decimal(amount) if is_debit else Decimal(0),
        ))
        return tx
    entry(income, "900", False, 1)
    entry(expense, "350", True, 1)
    entry(income, "1200", False, 2)
    entry(income, "9999", False, 1, property_=second)
    db.commit()
    return admin, manager, tenant, other_admin, first, second, foreign, income, expense, bank


def _payload(db, actor, property_id, year=2026):
    return build_report_payload(
        db, organization_id=actor.organization_id, report_key=KEY,
        parameters={"property_id": property_id, "calendar_year": year},
        current_user=actor,
    )


def test_budget_target_actual_favorable_variance_and_immutable_gl(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, other, first, second, foreign, income, expense, bank = _seed(db)
        monkeypatch.setattr(property_budgets, "permission_allows_user", lambda *a, **kw: True)
        def save(account, month, amount):
            return property_budgets.upsert_property_budget(
                db, current_user=admin,
                payload=PropertyBudgetUpsertIn(
                    property_id=first.id, gl_account_id=account.id,
                    calendar_year=2026, month=month, amount=Decimal(amount),
                ),
            )
        posted_before = db.query(GLEntry).count()
        save(income, 1, "1000"); save(expense, 1, "400"); save(income, 2, "1000")
        assert db.query(GLEntry).count() == posted_before
        report = _payload(db, admin, first.id)
        assert len(report.rows) == 3
        amounts = {(row[2], row[3]): row[6:9] for row in report.rows}
        assert amounts[(1, "4001")] == (Decimal("1000"), Decimal("900"), Decimal("-100"))
        assert amounts[(1, "6001")] == (Decimal("400"), Decimal("350"), Decimal("50"))
        assert amounts[(2, "4001")] == (Decimal("1000"), Decimal("1200"), Decimal("200"))
        assert "=First" not in report_csv_bytes(report).decode("utf-8-sig").splitlines()[1].split(",")[0]
        assert "'=First" in report_csv_bytes(report).decode("utf-8-sig")
        assert "'=Rent" in report_csv_bytes(report).decode("utf-8-sig")
        old = save(income, 1, "1100")
        assert db.query(PropertyBudgetLine).count() == 3
        assert old.id == next(row.id for row in db.query(PropertyBudgetLine).filter_by(gl_account_id=income.id, month=1))
        assert db.query(AuditLog).filter_by(entity_type="property_budget").count() == 4
        assert _payload(db, admin, second.id).rows == ()
    finally:
        db.close(); engine.dispose()


def test_budget_scope_admin_manager_and_invalid_account(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, other, first, second, foreign, income, expense, bank = _seed(db)
        monkeypatch.setattr(property_budgets, "permission_allows_user", lambda *a, **kw: True)
        add = lambda actor, prop, account: property_budgets.upsert_property_budget(
            db, current_user=actor,
            payload=PropertyBudgetUpsertIn(
                property_id=prop.id, gl_account_id=account.id,
                calendar_year=2026, month=1, amount=Decimal("50"),
            ),
        )
        add(admin, first, income)
        assert len(property_budgets.list_property_budget(
            db, current_user=manager, property_id=first.id, calendar_year=2026,
        )) == 1
        for prop in (second, foreign):
            with pytest.raises(ReportDeliveryError, match="Property not found"):
                property_budgets.list_property_budget(
                    db, current_user=manager, property_id=prop.id, calendar_year=2026,
                )
        for prop in (second, foreign):
            with pytest.raises(ReportDeliveryError, match="Property not found"):
                _payload(db, manager, prop.id)
        with pytest.raises(ReportDeliveryError, match="administrators"):
            add(manager, first, income)
        for actor in (tenant, other):
            with pytest.raises(ReportDeliveryError):
                _payload(db, actor, first.id)
        with pytest.raises(ReportDeliveryError, match="account not found"):
            add(admin, first, bank)
        with pytest.raises(ReportDeliveryError):
            add(admin, first, GLAccount(id=9999, organization_id=other.organization_id))
        assert db.query(PropertyBudgetLine).count() == 1
    finally:
        db.close(); engine.dispose()


def test_cash_basis_and_missing_budget_do_not_misrepresent_actuals(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, *_ = _seed(db)
        first = db.query(Property).filter(Property.name == "=First").one()
        monkeypatch.setattr(property_budgets, "permission_allows_user", lambda *a, **kw: True)
        assert _payload(db, admin, first.id).rows == ()
        db.add(AccountingSettings(organization_id=admin.organization_id, accounting_basis="CASH"))
        db.commit()
        with pytest.raises(ReportDeliveryError, match="ACCRUAL"):
            _payload(db, admin, first.id)
        with pytest.raises(ReportDeliveryError):
            build_report_payload(db, organization_id=admin.organization_id,
                                 report_key=KEY, parameters={"property_id": first.id, "calendar_year": 2026})
        for params in ({"property_id": first.id, "calendar_year": 2026, "sql": "select"},
                       {"property_id": first.id, "calendar_year": 2026, "as_of": "2026-01-01"},
                       {"property_id": first.id, "calendar_year": 2101}):
            with pytest.raises(ReportDeliveryError):
                build_report_payload(db, organization_id=admin.organization_id,
                                     report_key=KEY, parameters=params, current_user=admin)
    finally:
        db.close(); engine.dispose()


def test_catalog_report_preview_export_email_and_permission_revocations(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, other, first, second, foreign, income, expense, bank = _seed(db)
        monkeypatch.setattr(property_budgets, "permission_allows_user", lambda *a, **kw: True)
        property_budgets.upsert_property_budget(
            db, current_user=admin, payload=PropertyBudgetUpsertIn(
                property_id=first.id, gl_account_id=income.id,
                calendar_year=2026, month=1, amount=Decimal("1000"),
            ),
        )
        item = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert item.presentation == "TAB" and item.href == "/dashboard/reporting/budget-comparison"
        assert report_router.REPORT_PERMISSIONS[KEY] == "ACCOUNTING.GL_ACCOUNTS"
        monkeypatch.setattr(report_router, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=True,
                            )])
        req = SimpleNamespace(query_params={"property_id": str(first.id), "calendar_year": "2026"})
        response = Response()
        result = report_router.preview_property_budget_comparison(
            req, response, db=db, current_user=admin,
        )
        assert result["total"] == 1
        assert response.headers["cache-control"] == "no-store"
        exported = report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Posted GL Actual" in exported.body
        sent = {}
        monkeypatch.setattr(report_router, "send_email", lambda **kw: sent.update(kw))
        result = report_router.email_report(
            KEY, report_router.ReportEmailIn(
                recipient="admin@example.com",
                parameters={"property_id": first.id, "calendar_year": 2026},
            ), db=db, current_user=admin,
        )
        assert result.sent and b"Favorable Variance" in sent["attachments"][0][1]
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=False,
                            )])
        with pytest.raises(HTTPException) as exc:
            report_router.preview_property_budget_comparison(
                req, Response(), db=db, current_user=admin,
            )
        assert exc.value.status_code == 404
        monkeypatch.setattr(report_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
        monkeypatch.setattr(property_budgets, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "PROPERTIES.ALL")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, admin, first.id)
    finally:
        db.close(); engine.dispose()
