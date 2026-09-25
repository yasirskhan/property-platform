from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.bill import Bill
from app.models.bill_line import BillLine
from app.models.gl_account import GLAccount, GLAccountPostingRestriction
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.user import Organization, User, UserRole
from app.schemas.bill import BillCreateIn, BillLineIn, BillPayIn
from app.services.bill_posting import pay_bill, post_bill, reverse_bill


TEST_TABLES = [
    Organization.__table__,
    User.__table__,
    GLAccount.__table__,
    GLAccountPostingRestriction.__table__,
    GLTransaction.__table__,
    GLEntry.__table__,
    Bill.__table__,
    BillLine.__table__,
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


def seed(db: Session):
    org = Organization(name="Bill Polish Org", slug="bill-polish")
    db.add(org)
    db.flush()
    user = User(
        email="bill-polish@example.com",
        hashed_password="unused",
        first_name="Bill",
        last_name="Admin",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    ap = GLAccount(
        organization_id=org.id,
        gl_number="2100",
        name="Accounts Payable",
        account_type="LIABILITY",
        is_active=True,
    )
    expense = GLAccount(
        organization_id=org.id,
        gl_number="6100",
        name="Repairs",
        account_type="EXPENSE",
        is_active=True,
    )
    cash = GLAccount(
        organization_id=org.id,
        gl_number="1150",
        name="Rental Trust",
        account_type="ASSET",
        is_active=True,
    )
    db.add_all([user, ap, expense, cash])
    db.commit()
    return org, user, ap, expense, cash


def create_bill(db: Session, org, user, expense, cash) -> Bill:
    return post_bill(
        db=db,
        organization_id=org.id,
        payload=BillCreateIn(
            payee_name="Plumber",
            bill_date=date(2026, 9, 20),
            cash_gl_account_id=cash.id,
            lines=[
                BillLineIn(
                    gl_account_id=expense.id,
                    description="Repair",
                    amount=Decimal("100.00"),
                )
            ],
        ),
        created_by=user,
    )


@pytest.mark.accounting
def test_bill_default_cash_account_is_used_for_payment(db: Session) -> None:
    org, user, _ap, expense, cash = seed(db)
    bill = create_bill(db, org, user, expense, cash)

    updated = pay_bill(
        db=db,
        organization_id=org.id,
        bill=bill,
        payload=BillPayIn(
            payment_date=date(2026, 9, 21),
            cash_gl_account_id=None,
            amount=Decimal("25.00"),
        ),
        created_by=user,
    )

    assert updated.cash_gl_account_id == cash.id
    assert updated.status == "PARTIAL"
    payment = (
        db.query(GLTransaction)
        .filter(
            GLTransaction.source_type == "bill_payment",
            GLTransaction.source_id == bill.id,
        )
        .one()
    )
    cash_entry = (
        db.query(GLEntry)
        .filter(
            GLEntry.transaction_id == payment.id,
            GLEntry.gl_account_id == cash.id,
        )
        .one()
    )
    assert Decimal(cash_entry.credit) == Decimal("25.00")


@pytest.mark.accounting
def test_partial_bill_reversal_unwinds_payment_and_accrual_atomically(
    db: Session,
) -> None:
    org, user, _ap, expense, cash = seed(db)
    bill = create_bill(db, org, user, expense, cash)
    pay_bill(
        db=db,
        organization_id=org.id,
        bill=bill,
        payload=BillPayIn(
            payment_date=date(2026, 9, 21),
            amount=Decimal("40.00"),
        ),
        created_by=user,
    )

    mirror = reverse_bill(
        db=db,
        original=bill,
        reversal_date=date(2026, 9, 24),
        memo="Correct partially paid bill",
        created_by=user,
    )

    db.refresh(bill)
    assert bill.status == "PARTIAL"
    assert bill.is_reversed is True
    assert mirror.status == "VOID"

    originals = (
        db.query(GLTransaction)
        .filter(
            GLTransaction.organization_id == org.id,
            GLTransaction.source_id == bill.id,
            GLTransaction.transaction_type == "BILL",
        )
        .all()
    )
    assert originals
    assert all(txn.is_reversed for txn in originals)

    balances = {}
    for entry in db.query(GLEntry).filter(GLEntry.organization_id == org.id).all():
        balances.setdefault(entry.gl_account_id, Decimal("0"))
        balances[entry.gl_account_id] += (
            Decimal(entry.debit or 0) - Decimal(entry.credit or 0)
        )
    assert all(value == Decimal("0") for value in balances.values())


@pytest.mark.accounting
def test_delete_mode_only_allows_unpaid_and_hides_bill_history_rows(
    db: Session,
) -> None:
    org, user, _ap, expense, cash = seed(db)
    bill = create_bill(db, org, user, expense, cash)

    mirror = reverse_bill(
        db=db,
        original=bill,
        reversal_date=date(2026, 9, 24),
        memo="Delete unpaid bill",
        created_by=user,
        deactivate=True,
    )

    db.refresh(bill)
    assert bill.is_reversed is True
    assert bill.is_active is False
    assert bill.deleted_at is not None
    assert mirror.status == "VOID"
    assert mirror.is_active is False
