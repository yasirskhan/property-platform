from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.gl_account import GLAccount
from app.models.user import Organization, User, UserRole
from app.schemas.gl_transaction import PostingLine
from app.services.diagnostics import check_positive_fee_accounts
from app.services.gl_posting import post_transaction


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def _seed(db):
    org = Organization(name="Positive Fee", slug="positive-fee")
    other = Organization(name="Other Positive Fee", slug="other-positive-fee")
    db.add_all([org, other])
    db.flush()

    user = User(
        email="positive-fee@example.com",
        hashed_password="unused",
        first_name="Positive",
        last_name="Fee",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
    )
    cash = GLAccount(
        organization_id=org.id,
        gl_number="1150",
        name="Trust Cash",
        account_type="ASSET",
        is_active=True,
    )
    flagged = GLAccount(
        organization_id=org.id,
        gl_number="4430",
        name="Late Fee Clearing",
        account_type="INCOME",
        must_clear=True,
        is_active=True,
    )
    ignored = GLAccount(
        organization_id=org.id,
        gl_number="4440",
        name="Ordinary Fee Income",
        account_type="INCOME",
        must_clear=False,
        is_active=True,
    )
    inactive = GLAccount(
        organization_id=org.id,
        gl_number="4450",
        name="Inactive Must Clear",
        account_type="INCOME",
        must_clear=True,
        is_active=True,
    )
    other_flagged = GLAccount(
        organization_id=other.id,
        gl_number="4430",
        name="Other Org Must Clear",
        account_type="INCOME",
        must_clear=True,
        is_active=True,
    )
    db.add_all([user, cash, flagged, ignored, inactive, other_flagged])
    db.commit()
    return org, other, user, cash, flagged, ignored, inactive, other_flagged


def _credit_income(db, *, org_id: int, user: User, cash: GLAccount, account: GLAccount, amount: str):
    post_transaction(
        db,
        organization_id=org_id,
        transaction_date=date(2026, 9, 25),
        transaction_type="JOURNAL_ENTRY",
        memo="positive fee diagnostic probe",
        created_by=user,
        lines=[
            PostingLine(gl_account_id=cash.id, debit=Decimal(amount)),
            PostingLine(gl_account_id=account.id, credit=Decimal(amount)),
        ],
    )


def test_positive_fee_diagnostic_flags_only_active_must_clear_income_accounts():
    db, engine = _session()
    try:
        org, _other, user, cash, flagged, ignored, inactive, _other_flagged = _seed(db)
        _credit_income(
            db,
            org_id=org.id,
            user=user,
            cash=cash,
            account=flagged,
            amount="25.00",
        )
        _credit_income(
            db,
            org_id=org.id,
            user=user,
            cash=cash,
            account=ignored,
            amount="40.00",
        )
        _credit_income(
            db,
            org_id=org.id,
            user=user,
            cash=cash,
            account=inactive,
            amount="50.00",
        )
        inactive.is_active = False
        db.commit()

        report = check_positive_fee_accounts(db, org.id)

        assert report["passed"] is False
        assert report["severity"] == "warning"
        assert len(report["details"]) == 1
        assert report["details"][0]["gl_account_id"] == flagged.id
        assert report["details"][0]["balance"] == "25.00"
    finally:
        db.close()
        engine.dispose()


def test_positive_fee_diagnostic_passes_when_must_clear_accounts_are_zero_or_negative():
    db, engine = _session()
    try:
        org, _other, user, cash, flagged, _ignored, _inactive, _other_flagged = _seed(db)

        report = check_positive_fee_accounts(db, org.id)
        assert report["passed"] is True

        post_transaction(
            db,
            organization_id=org.id,
            transaction_date=date(2026, 9, 25),
            transaction_type="JOURNAL_ENTRY",
            memo="negative must-clear probe",
            created_by=user,
            lines=[
                PostingLine(gl_account_id=flagged.id, debit=Decimal("5.00")),
                PostingLine(gl_account_id=cash.id, credit=Decimal("5.00")),
            ],
        )

        report = check_positive_fee_accounts(db, org.id)
        assert report["passed"] is True
        assert report["details"] == []
    finally:
        db.close()
        engine.dispose()
