from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
import app.routers.diagnostics as diagnostics_router
from app.core.database import Base
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.user import Organization, User, UserRole
from app.schemas.gl_transaction import PostingLine
from app.services.diagnostics import (
    check_negative_fee_accounts,
    refund_negative_fee_account,
)
from app.services.gl_posting import PostingError, post_transaction


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def _seed(db):
    org = Organization(name="Diag Org", slug="diag-org")
    db.add(org)
    db.flush()
    user = User(
        email="diag@example.com",
        hashed_password="unused",
        first_name="Diag",
        last_name="Admin",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
    )
    cash = GLAccount(
        organization_id=org.id,
        gl_number="1150",
        name="Trust",
        account_type="ASSET",
        is_active=True,
    )
    fee = GLAccount(
        organization_id=org.id,
        gl_number="4430",
        name="Late Fee",
        account_type="INCOME",
        offset_account="6025",
        is_active=True,
    )
    offset = GLAccount(
        organization_id=org.id,
        gl_number="6025",
        name="Diagnostic Offset",
        account_type="EXPENSE",
        is_active=True,
    )
    db.add_all([user, cash, fee, offset])
    db.commit()
    return org, user, cash, fee, offset


def _make_negative(db, org, user, cash, fee, amount="25.00"):
    post_transaction(
        db,
        organization_id=org.id,
        transaction_date=date(2026, 9, 25),
        transaction_type="JOURNAL_ENTRY",
        memo="negative fee probe",
        created_by=user,
        lines=[
            PostingLine(gl_account_id=fee.id, debit=Decimal(amount)),
            PostingLine(gl_account_id=cash.id, credit=Decimal(amount)),
        ],
    )


def test_refund_negative_diagnostic_uses_central_posting_and_zeros_fee():
    db, engine = _session()
    try:
        org, user, cash, fee, offset = _seed(db)
        _make_negative(db, org, user, cash, fee)
        before = check_negative_fee_accounts(db, org.id)
        assert before["passed"] is False
        assert before["details"][0]["gl_account_id"] == fee.id
        assert before["details"][0]["offset_account"] == "6025"

        result = refund_negative_fee_account(
            db,
            organization_id=org.id,
            gl_account_id=fee.id,
            transaction_date=date(2026, 9, 25),
            created_by=user,
        )
        assert result["amount"] == Decimal("25.00")
        txn = db.get(GLTransaction, result["transaction_id"])
        assert txn is not None
        assert txn.transaction_type == "REFUND_NEGATIVE_DIAGNOSTIC"
        assert txn.source_type == "financial_diagnostic"
        entries = (
            db.query(GLEntry)
            .filter(GLEntry.transaction_id == txn.id)
            .all()
        )
        by_account = {row.gl_account_id: row for row in entries}
        assert Decimal(by_account[offset.id].debit) == Decimal("25.00")
        assert Decimal(by_account[fee.id].credit) == Decimal("25.00")
        assert check_negative_fee_accounts(db, org.id)["passed"] is True

        with pytest.raises(PostingError, match="no longer has a negative balance"):
            refund_negative_fee_account(
                db,
                organization_id=org.id,
                gl_account_id=fee.id,
                transaction_date=date(2026, 9, 25),
                created_by=user,
            )
    finally:
        db.close()
        engine.dispose()


def test_refund_negative_requires_explicit_offset():
    db, engine = _session()
    try:
        org, user, cash, fee, _offset = _seed(db)
        _make_negative(db, org, user, cash, fee)
        fee.offset_account = None
        db.commit()
        with pytest.raises(PostingError, match="no offset account configured"):
            refund_negative_fee_account(
                db,
                organization_id=org.id,
                gl_account_id=fee.id,
                transaction_date=date(2026, 9, 25),
                created_by=user,
            )
        assert (
            db.query(GLTransaction)
            .filter(
                GLTransaction.transaction_type
                == "REFUND_NEGATIVE_DIAGNOSTIC"
            )
            .count()
            == 0
        )
    finally:
        db.close()
        engine.dispose()


def test_refund_negative_respects_locked_period_without_side_effects():
    db, engine = _session()
    try:
        org, user, cash, fee, _offset = _seed(db)
        _make_negative(db, org, user, cash, fee)
        org.locked_through_date = date(2026, 9, 25)
        db.commit()
        with pytest.raises(PostingError, match="locked through 2026-09-25"):
            refund_negative_fee_account(
                db,
                organization_id=org.id,
                gl_account_id=fee.id,
                transaction_date=date(2026, 9, 25),
                created_by=user,
            )
        assert (
            db.query(GLTransaction)
            .filter(
                GLTransaction.transaction_type
                == "REFUND_NEGATIVE_DIAGNOSTIC"
            )
            .count()
            == 0
        )
    finally:
        db.close()
        engine.dispose()


def test_refund_negative_endpoint_requires_independent_gate(monkeypatch):
    db, engine = _session()
    try:
        _org, user, _cash, _fee, _offset = _seed(db)
        monkeypatch.setattr(
            diagnostics_router,
            "permission_allows_user",
            lambda *args, **kwargs: True,
        )
        monkeypatch.setattr(
            diagnostics_router,
            "resolve_customer_features",
            lambda *args, **kwargs: [],
        )
        with pytest.raises(HTTPException) as exc:
            diagnostics_router._require_refund_negative_feature(db, user)
        assert exc.value.status_code == 404

        monkeypatch.setattr(
            diagnostics_router,
            "resolve_customer_features",
            lambda *args, **kwargs: [
                SimpleNamespace(
                    key=diagnostics_router.REFUND_NEGATIVE_FEATURE,
                    allowed=True,
                )
            ],
        )
        assert (
            diagnostics_router._require_refund_negative_feature(db, user)
            == user.organization_id
        )
    finally:
        db.close()
        engine.dispose()
