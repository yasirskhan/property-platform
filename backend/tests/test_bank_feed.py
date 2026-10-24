from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.bank_account import BankAccount
from app.models.bank_feed import BankFeedTransaction
from app.models.check import Check
from app.models.deposit import Deposit
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.user import Organization, User, UserRole
from app.services.bank_feed import BankFeedError, import_bank_feed_csv, parse_bank_feed_csv

TABLES = [
    Organization.__table__,
    User.__table__,
    GLAccount.__table__,
    BankAccount.__table__,
    GLTransaction.__table__,
    GLEntry.__table__,
    Deposit.__table__,
    Check.__table__,
    BankFeedTransaction.__table__,
]


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=TABLES)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=list(reversed(TABLES)))
        engine.dispose()


def seed(db: Session):
    org = Organization(name="Feed Org", slug="feed-org")
    other = Organization(name="Other Feed Org", slug="other-feed-org")
    db.add_all([org, other])
    db.flush()

    user = User(
        email="feed@example.com",
        hashed_password="x",
        first_name="Feed",
        last_name="Admin",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    cash = GLAccount(
        organization_id=org.id,
        gl_number="1150",
        name="Client Trust",
        account_type="ASSET",
        is_active=True,
    )
    offset = GLAccount(
        organization_id=org.id,
        gl_number="6100",
        name="Bank Fees",
        account_type="EXPENSE",
        is_active=True,
    )
    other_cash = GLAccount(
        organization_id=other.id,
        gl_number="1150",
        name="Other Trust",
        account_type="ASSET",
        is_active=True,
    )
    db.add_all([user, cash, offset, other_cash])
    db.flush()

    bank = BankAccount(
        organization_id=org.id,
        name="Client Trust",
        gl_account_id=cash.id,
        account_type="OPERATING",
        is_active=True,
        created_by_id=user.id,
    )
    other_bank = BankAccount(
        organization_id=other.id,
        name="Other Trust",
        gl_account_id=other_cash.id,
        account_type="OPERATING",
        is_active=True,
    )
    db.add_all([bank, other_bank])
    db.flush()

    deposit = Deposit(
        organization_id=org.id,
        bank_gl_account_id=cash.id,
        deposit_date=date(2026, 9, 2),
        deposit_number="D-1",
        total=Decimal("100.00"),
        is_active=True,
        created_by_id=user.id,
    )
    check = Check(
        organization_id=org.id,
        bank_account_id=bank.id,
        check_number="1001",
        check_date=date(2026, 9, 3),
        payee_name="Vendor",
        amount=Decimal("40.00"),
        status="ISSUED",
        created_by_id=user.id,
    )
    db.add_all([deposit, check])
    db.flush()

    txn = GLTransaction(
        organization_id=org.id,
        transaction_date=date(2026, 9, 4),
        transaction_type="BANK_ADJUSTMENT",
        source_type="bank_adjustment",
        source_id=bank.id,
        memo="Bank fee",
        created_by_id=user.id,
        is_reversed=False,
    )
    db.add(txn)
    db.flush()
    db.add_all([
        GLEntry(
            organization_id=org.id,
            transaction_id=txn.id,
            gl_account_id=offset.id,
            debit=Decimal("5.00"),
            credit=Decimal("0.00"),
        ),
        GLEntry(
            organization_id=org.id,
            transaction_id=txn.id,
            gl_account_id=cash.id,
            debit=Decimal("0.00"),
            credit=Decimal("5.00"),
        ),
    ])
    db.commit()
    return org, other, user, bank, other_bank


@pytest.mark.accounting
def test_csv_import_matches_activity_dedupes_and_does_not_mutate_gl(db: Session) -> None:
    org, _other, user, bank, _other_bank = seed(db)
    before_txns = db.query(GLTransaction).count()
    before_entries = db.query(GLEntry).count()
    content = """date,amount,payee,memo,reference,external_id
2026-09-02,100.00,Deposit,,,dep-100
2026-09-03,-40.00,Vendor,,,check-1001
2026-09-04,-5.00,Bank,Fee,,fee-5
2026-09-05,-9.00,Unknown,,,unknown-9
"""
    imported, duplicates, matched, total = import_bank_feed_csv(
        db,
        organization_id=org.id,
        bank_account=bank,
        content=content,
        created_by=user,
    )
    assert (imported, duplicates, matched, total) == (4, 0, 3, 4)
    assert db.query(GLTransaction).count() == before_txns
    assert db.query(GLEntry).count() == before_entries
    assert (
        db.query(BankFeedTransaction)
        .filter(BankFeedTransaction.status == "MATCHED")
        .count()
        == 3
    )

    imported, duplicates, matched, total = import_bank_feed_csv(
        db,
        organization_id=org.id,
        bank_account=bank,
        content=content,
        created_by=user,
    )
    assert (imported, duplicates, matched, total) == (0, 4, 0, 4)


@pytest.mark.accounting
def test_matching_is_organization_and_bank_scoped(db: Session) -> None:
    org, _other, user, bank, other_bank = seed(db)
    # A same-value deposit exists only for the first org/bank. Importing into
    # the other bank must not see or match it.
    content = "date,amount,external_id\n2026-09-02,100.00,other-1\n"
    imported, duplicates, matched, total = import_bank_feed_csv(
        db,
        organization_id=other_bank.organization_id,
        bank_account=other_bank,
        content=content,
        created_by=user,
    )
    assert (imported, duplicates, matched, total) == (1, 0, 0, 1)


@pytest.mark.accounting
def test_parser_preserves_identical_rows_and_rejects_bad_headers() -> None:
    rows = parse_bank_feed_csv(
        "date,amount,payee\n09/10/2026,(12.50),Bank\n09/10/2026,(12.50),Bank\n"
    )
    assert len(rows) == 2
    assert rows[0].amount == Decimal("-12.50")
    assert rows[0].import_key != rows[1].import_key

    with pytest.raises(BankFeedError, match="amount column"):
        parse_bank_feed_csv("date,payee\n2026-09-10,Bank\n")
