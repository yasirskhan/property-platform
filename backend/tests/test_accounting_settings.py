from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
import app.routers.accounting_settings as accounting_settings_router
from app.core.database import Base
from app.models.accounting_settings import AccountingSettings
from app.models.gl_account import GLAccount
from app.models.user import Organization, User, UserRole
from app.schemas.accounting_settings import AccountingSettingsUpdate
from app.services.gpr_posting import GPR_GL, LOSS_GAIN_GL, RENT_GL, _required_accounts
from app.services.receipt_posting import resolve_cash_gl_account_id
from app.services.reporting_basis import get_accounting_basis


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Accounting Settings Org", slug="accounting-settings-org")
    db.add(org)
    db.flush()
    admin = User(
        email="acct-settings-admin@example.com",
        hashed_password="x",
        first_name="Accounting",
        last_name="Admin",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
    )
    db.add(admin)
    accounts = [
        GLAccount(
            organization_id=org.id,
            gl_number="4100",
            name="Rent Income",
            account_type="INCOME",
            is_active=True,
        ),
        GLAccount(
            organization_id=org.id,
            gl_number="4115",
            name="Gross Potential Rent",
            account_type="INCOME",
            is_active=True,
        ),
        GLAccount(
            organization_id=org.id,
            gl_number="4120",
            name="Loss to Lease",
            account_type="INCOME",
            is_active=True,
        ),
        GLAccount(
            organization_id=org.id,
            gl_number="4199",
            name="Custom GPR Income",
            account_type="INCOME",
            is_active=True,
        ),
        GLAccount(
            organization_id=org.id,
            gl_number="1150",
            name="Rental Trust",
            account_type="ASSET",
            is_active=True,
        ),
        GLAccount(
            organization_id=org.id,
            gl_number="1160",
            name="Custom Receipt Cash",
            account_type="ASSET",
            is_active=True,
        ),
    ]
    db.add_all(accounts)
    db.commit()
    return org, admin, {account.gl_number: account for account in accounts}


def _allow(monkeypatch):
    monkeypatch.setattr(
        accounting_settings_router,
        "permission_allows_user",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        accounting_settings_router,
        "resolve_customer_features",
        lambda *args, **kwargs: [
            SimpleNamespace(key=accounting_settings_router.FEATURE_KEY, allowed=True)
        ],
    )


def test_accounting_settings_defaults_and_update(monkeypatch):
    db, engine = _session()
    try:
        org, admin, accounts = _seed(db)
        _allow(monkeypatch)

        initial = accounting_settings_router.get_accounting_settings(
            db=db, current_user=admin
        )
        assert initial.organization_id == org.id
        assert initial.gpr_rent_gl_account_id is None
        assert initial.receipt_cash_gl_account_id is None
        assert initial.report_export_format == "CSV"
        assert initial.fiscal_year_start_month == 1
        assert initial.accounting_basis == "ACCRUAL"
        assert get_accounting_basis(db, organization_id=org.id) == "ACCRUAL"
        assert db.get(AccountingSettings, org.id) is None

        updated = accounting_settings_router.update_accounting_settings(
            AccountingSettingsUpdate(
                gpr_rent_gl_account_id=accounts["4199"].id,
                gpr_market_gl_account_id=accounts["4115"].id,
                gpr_loss_gain_gl_account_id=accounts["4120"].id,
                receipt_cash_gl_account_id=accounts["1160"].id,
                report_export_format="EXCEL",
                fiscal_year_start_month=7,
                accounting_basis="CASH",
            ),
            db=db,
            current_user=admin,
        )
        assert updated.gpr_rent_gl_account_id == accounts["4199"].id
        assert updated.receipt_cash_gl_account_id == accounts["1160"].id
        assert updated.report_export_format == "EXCEL"
        assert updated.fiscal_year_start_month == 7
        assert updated.accounting_basis == "CASH"
        assert get_accounting_basis(db, organization_id=org.id) == "CASH"
    finally:
        db.close()
        engine.dispose()


def test_gpr_defaults_remain_standard_until_overridden():
    db, engine = _session()
    try:
        org, _, accounts = _seed(db)
        defaults = _required_accounts(db, organization_id=org.id)
        assert defaults[RENT_GL].id == accounts["4100"].id
        assert defaults[GPR_GL].id == accounts["4115"].id
        assert defaults[LOSS_GAIN_GL].id == accounts["4120"].id

        db.add(
            AccountingSettings(
                organization_id=org.id,
                gpr_rent_gl_account_id=accounts["4199"].id,
            )
        )
        db.commit()
        configured = _required_accounts(db, organization_id=org.id)
        assert configured[RENT_GL].id == accounts["4199"].id
        assert configured[GPR_GL].id == accounts["4115"].id
    finally:
        db.close()
        engine.dispose()


def test_receipt_cash_default_only_overrides_automatic_when_configured():
    db, engine = _session()
    try:
        org, _, accounts = _seed(db)
        assert (
            resolve_cash_gl_account_id(
                db, organization_id=org.id, requested_id=None
            )
            == accounts["1150"].id
        )
        db.add(
            AccountingSettings(
                organization_id=org.id,
                receipt_cash_gl_account_id=accounts["1160"].id,
            )
        )
        db.commit()
        assert (
            resolve_cash_gl_account_id(
                db, organization_id=org.id, requested_id=None
            )
            == accounts["1160"].id
        )
        assert (
            resolve_cash_gl_account_id(
                db,
                organization_id=org.id,
                requested_id=accounts["1150"].id,
            )
            == accounts["1150"].id
        )
    finally:
        db.close()
        engine.dispose()


def test_accounting_settings_rejects_wrong_account_types(monkeypatch):
    db, engine = _session()
    try:
        _, admin, accounts = _seed(db)
        _allow(monkeypatch)
        with pytest.raises(HTTPException) as exc:
            accounting_settings_router.update_accounting_settings(
                AccountingSettingsUpdate(
                    gpr_rent_gl_account_id=accounts["1160"].id,
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 422
    finally:
        db.close()
        engine.dispose()


def test_accounting_settings_write_is_admin_owner_only():
    with pytest.raises(HTTPException) as exc:
        accounting_settings_router._require_write(
            SimpleNamespace(role=UserRole.MANAGER)
        )
    assert exc.value.status_code == 403
