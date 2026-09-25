from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.bank_account import BankAccount
from app.models.gl_account import GLAccount, GLAccountPostingRestriction
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.receipt import Receipt
from app.models.receipt_line import ReceiptLine
from app.models.release_gate import ReleaseGate, ReleaseGateOrganization
from app.models.user import Organization, User, UserRole
from app.schemas.receipt import ReceiptCreateIn
from app.services.receipt_posting import (
    post_receipt,
    process_nsf_receipt,
    resolve_cash_gl_account_id,
)


TEST_TABLES = [
    Organization.__table__,
    User.__table__,
    GLAccount.__table__,
    BankAccount.__table__,
    GLAccountPostingRestriction.__table__,
    ReleaseGate.__table__,
    ReleaseGateOrganization.__table__,
    GLTransaction.__table__,
    GLEntry.__table__,
    Receipt.__table__,
    ReceiptLine.__table__,
    AuditLog.__table__,
]


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=TEST_TABLES)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=list(reversed(TEST_TABLES)))
        engine.dispose()


def seed_receipt_accounts(db: Session):
    org = Organization(name="Receipt Polish Org", slug="receipt-polish")
    db.add(org)
    db.flush()
    user = User(
        email="receipt-polish@example.com",
        hashed_password="unused",
        first_name="Receipt",
        last_name="Admin",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    cash = GLAccount(
        organization_id=org.id,
        gl_number="1150",
        name="Rental Trust",
        account_type="ASSET",
        is_active=True,
    )
    application_fee = GLAccount(
        organization_id=org.id,
        gl_number="4420",
        name="Application Fee Income",
        account_type="INCOME",
        is_active=True,
    )
    db.add_all([user, cash, application_fee])
    db.flush()
    bank = BankAccount(
        organization_id=org.id,
        name="Client Trust",
        gl_account_id=cash.id,
        account_type="OPERATING",
        is_active=True,
    )
    db.add(bank)
    db.commit()
    return org, user, cash, application_fee, bank


@pytest.mark.accounting
def test_automatic_cash_account_prefers_active_operating_bank_mapping(
    db: Session,
) -> None:
    org, _user, cash, _fee, _bank = seed_receipt_accounts(db)

    resolved = resolve_cash_gl_account_id(
        db,
        organization_id=org.id,
        requested_id=None,
    )

    assert resolved == cash.id


@pytest.mark.accounting
def test_application_fee_receipt_uses_standard_income_and_automatic_cash(
    db: Session,
) -> None:
    org, user, cash, application_fee, _bank = seed_receipt_accounts(db)

    receipt = post_receipt(
        db=db,
        organization_id=org.id,
        payload=ReceiptCreateIn(
            type="APPLICATION_FEE",
            receipt_date=date(2026, 9, 24),
            amount=Decimal("75.00"),
            cash_gl_account_id=None,
            received_from="Applicant Example",
            remarks="Application screening fee",
        ),
        created_by=user,
    )

    assert receipt.type == "APPLICATION_FEE"
    assert receipt.cash_gl_account_id == cash.id
    assert receipt.income_gl_account_id == application_fee.id
    assert receipt.received_from == "Applicant Example"

    txn = db.get(GLTransaction, receipt.gl_transaction_id)
    assert txn is not None
    entries = db.query(GLEntry).filter(GLEntry.transaction_id == txn.id).all()
    by_account = {row.gl_account_id: row for row in entries}
    assert Decimal(by_account[cash.id].debit) == Decimal("75.00")
    assert Decimal(by_account[cash.id].credit) == Decimal("0.00")
    assert Decimal(by_account[application_fee.id].debit) == Decimal("0.00")
    assert Decimal(by_account[application_fee.id].credit) == Decimal("75.00")


@pytest.mark.accounting
def test_process_nsf_uses_reversal_spine_and_preserves_original(
    db: Session,
) -> None:
    org, user, _cash, _fee, _bank = seed_receipt_accounts(db)
    original = post_receipt(
        db=db,
        organization_id=org.id,
        payload=ReceiptCreateIn(
            type="APPLICATION_FEE",
            receipt_date=date(2026, 9, 20),
            amount=Decimal("50.00"),
            cash_gl_account_id=None,
            received_from="Returned Applicant",
        ),
        created_by=user,
    )
    original_id = original.id
    original_txn_id = original.gl_transaction_id

    mirror = process_nsf_receipt(
        db=db,
        original=original,
        process_date=date(2026, 9, 24),
        memo="Bank returned payment",
        created_by=user,
    )

    db.refresh(original)
    original_txn = db.get(GLTransaction, original_txn_id)
    assert original.id == original_id
    assert original.is_reversed is True
    assert original_txn is not None and original_txn.is_reversed is True
    assert mirror.reversal_of_id == original.id
    assert mirror.receipt_date == date(2026, 9, 24)
    assert "NSF" in (mirror.remarks or "")
