"""Core General Ledger invariants."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.property import Property, Unit
from app.models.user import Organization, User, UserRole
from app.schemas.gl_transaction import PostingLine
from app.services.gl_posting import PostingError, post_transaction, reverse_transaction

TEST_TABLES = [
    Organization.__table__, User.__table__, Property.__table__, Unit.__table__,
    GLAccount.__table__, GLTransaction.__table__, GLEntry.__table__, AuditLog.__table__,
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


def seed_accounting(db: Session) -> tuple[Organization, User, GLAccount, GLAccount]:
    org = Organization(name="Test Org", slug="test-org")
    db.add(org)
    db.flush()
    user = User(
        email="admin@test.local",
        hashed_password="not-used-in-this-test",
        first_name="Test",
        last_name="Admin",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    cash = GLAccount(
        organization_id=org.id, gl_number="1150", name="Client Trust",
        account_type="ASSET", is_active=True,
    )
    income = GLAccount(
        organization_id=org.id, gl_number="4100", name="Rent Income",
        account_type="INCOME", is_active=True,
    )
    db.add_all([user, cash, income])
    db.commit()
    return org, user, cash, income


@pytest.mark.accounting
def test_balanced_transaction_posts_equal_debits_and_credits(db: Session) -> None:
    org, user, cash, income = seed_accounting(db)
    txn = post_transaction(
        db, organization_id=org.id, transaction_date=date(2026, 9, 23),
        transaction_type="RECEIPT", memo="Test receipt", created_by=user,
        lines=[
            PostingLine(gl_account_id=cash.id, debit=Decimal("100.00")),
            PostingLine(gl_account_id=income.id, credit=Decimal("100.00")),
        ],
    )
    assert txn.id is not None
    debit_total = db.query(func.sum(GLEntry.debit)).filter(GLEntry.transaction_id == txn.id).scalar()
    credit_total = db.query(func.sum(GLEntry.credit)).filter(GLEntry.transaction_id == txn.id).scalar()
    assert Decimal(debit_total) == Decimal("100.00")
    assert Decimal(credit_total) == Decimal("100.00")


@pytest.mark.accounting
def test_unbalanced_transaction_is_rejected_without_posting(db: Session) -> None:
    org, user, cash, income = seed_accounting(db)
    with pytest.raises(PostingError, match="does not balance"):
        post_transaction(
            db, organization_id=org.id, transaction_date=date(2026, 9, 23),
            transaction_type="RECEIPT", memo="Bad receipt", created_by=user,
            lines=[
                PostingLine(gl_account_id=cash.id, debit=Decimal("100.00")),
                PostingLine(gl_account_id=income.id, credit=Decimal("90.00")),
            ],
        )
    assert db.query(GLTransaction).count() == 0
    assert db.query(GLEntry).count() == 0


@pytest.mark.accounting
def test_cross_org_gl_account_is_rejected(db: Session) -> None:
    org, user, cash, _income = seed_accounting(db)
    other_org = Organization(name="Other Org", slug="other-org")
    db.add(other_org)
    db.flush()
    foreign_income = GLAccount(
        organization_id=other_org.id, gl_number="4100", name="Other Rent Income",
        account_type="INCOME", is_active=True,
    )
    db.add(foreign_income)
    db.commit()
    with pytest.raises(PostingError, match="not found in your organization"):
        post_transaction(
            db, organization_id=org.id, transaction_date=date(2026, 9, 23),
            transaction_type="RECEIPT", memo="Cross-org attempt", created_by=user,
            lines=[
                PostingLine(gl_account_id=cash.id, debit=Decimal("100.00")),
                PostingLine(gl_account_id=foreign_income.id, credit=Decimal("100.00")),
            ],
        )
    assert db.query(GLTransaction).count() == 0


@pytest.mark.accounting
def test_reversal_nets_original_transaction_to_zero(db: Session) -> None:
    org, user, cash, income = seed_accounting(db)
    original = post_transaction(
        db, organization_id=org.id, transaction_date=date(2026, 9, 23),
        transaction_type="RECEIPT", memo="Original", created_by=user,
        lines=[
            PostingLine(gl_account_id=cash.id, debit=Decimal("125.00")),
            PostingLine(gl_account_id=income.id, credit=Decimal("125.00")),
        ],
    )
    reversal = reverse_transaction(
        db, original=original, reversal_date=date(2026, 9, 23), created_by=user,
    )
    db.refresh(original)
    assert original.is_reversed is True
    assert reversal.reversal_of_id == original.id
    all_entries = db.query(GLEntry).all()
    total_debit = sum((Decimal(e.debit or 0) for e in all_entries), Decimal("0"))
    total_credit = sum((Decimal(e.credit or 0) for e in all_entries), Decimal("0"))
    assert total_debit == total_credit == Decimal("250.00")
    by_account: dict[int, Decimal] = {}
    for entry in all_entries:
        by_account.setdefault(entry.gl_account_id, Decimal("0"))
        by_account[entry.gl_account_id] += Decimal(entry.debit or 0) - Decimal(entry.credit or 0)
    assert all(balance == Decimal("0") for balance in by_account.values())


@pytest.mark.accounting
def test_reversal_commit_failure_rolls_back_reversal_and_original_flag(db: Session) -> None:
    org, user, cash, income = seed_accounting(db)
    original = post_transaction(
        db, organization_id=org.id, transaction_date=date(2026, 9, 23),
        transaction_type="JOURNAL_ENTRY", memo="atomic reversal test", created_by=user,
        lines=[
            PostingLine(gl_account_id=cash.id, debit=Decimal("50.00")),
            PostingLine(gl_account_id=income.id, credit=Decimal("50.00")),
        ],
    )
    original_id = original.id
    real_commit = db.commit

    def fail_commit() -> None:
        raise RuntimeError("simulated commit failure")

    db.commit = fail_commit  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="simulated commit failure"):
        reverse_transaction(
            db, original=original, reversal_date=date(2026, 9, 23), created_by=user,
        )
    db.commit = real_commit  # type: ignore[method-assign]
    db.rollback()
    db.expire_all()
    persisted = db.get(GLTransaction, original_id)
    assert persisted is not None
    assert persisted.is_reversed is False
    reversal_count = db.query(GLTransaction).filter(GLTransaction.reversal_of_id == original_id).count()
    assert reversal_count == 0


@pytest.mark.accounting
def test_locked_period_rejects_post_without_financial_side_effects(db: Session) -> None:
    org, user, cash, income = seed_accounting(db)
    org.locked_through_date = date(2026, 9, 30)
    db.commit()

    with pytest.raises(PostingError, match="locked through 2026-09-30"):
        post_transaction(
            db,
            organization_id=org.id,
            transaction_date=date(2026, 9, 30),
            transaction_type="RECEIPT",
            memo="Blocked by close",
            created_by=user,
            lines=[
                PostingLine(gl_account_id=cash.id, debit=Decimal("75.00")),
                PostingLine(gl_account_id=income.id, credit=Decimal("75.00")),
            ],
        )

    assert db.query(GLTransaction).count() == 0
    assert db.query(GLEntry).count() == 0


@pytest.mark.accounting
def test_first_open_day_after_lock_can_post(db: Session) -> None:
    org, user, cash, income = seed_accounting(db)
    org.locked_through_date = date(2026, 9, 30)
    db.commit()

    txn = post_transaction(
        db,
        organization_id=org.id,
        transaction_date=date(2026, 10, 1),
        transaction_type="RECEIPT",
        memo="Open period",
        created_by=user,
        lines=[
            PostingLine(gl_account_id=cash.id, debit=Decimal("75.00")),
            PostingLine(gl_account_id=income.id, credit=Decimal("75.00")),
        ],
    )

    assert txn.id is not None
