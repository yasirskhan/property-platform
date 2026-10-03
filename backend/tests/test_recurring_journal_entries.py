from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.gl_entry import GLEntry
from app.models.gl_account import GLAccount, GLAccountPostingRestriction
from app.models.gl_transaction import GLTransaction
from app.models.organization_feature_setting import OrganizationFeatureSetting
from app.models.property import Property, Unit
from app.models.recurring_journal_entry import RecurringJournalEntry, RecurringJournalEntryLine
from app.models.release_gate import ReleaseGate, ReleaseGateOrganization
from app.models.user import Organization, User, UserRole

from app.schemas.journal_entry import JournalEntryLineIn
from app.services.gl_posting import PostingError
import app.services.recurring_journal_entries as recurring


TEST_TABLES = [
    Organization.__table__,
    User.__table__,
    Property.__table__,
    Unit.__table__,
    GLAccount.__table__,
    GLAccountPostingRestriction.__table__,
    ReleaseGate.__table__,
    ReleaseGateOrganization.__table__,
    OrganizationFeatureSetting.__table__,
    GLTransaction.__table__,
    GLEntry.__table__,
    RecurringJournalEntry.__table__,
    RecurringJournalEntryLine.__table__,
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


def seed_recurring_accounts(db: Session, slug: str = "recurring-org"):
    org = Organization(name="Recurring Org", slug=slug)
    db.add(org)
    db.flush()
    user = User(
        email=f"{slug}@example.com",
        hashed_password="not-used",
        first_name="Recurring",
        last_name="Admin",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    cash = GLAccount(
        organization_id=org.id,
        gl_number="1000",
        name="Cash",
        account_type="ASSET",
        is_active=True,
    )
    income = GLAccount(
        organization_id=org.id,
        gl_number="4000",
        name="Recurring Income",
        account_type="INCOME",
        is_active=True,
    )
    db.add_all([user, cash, income])
    db.commit()
    return org, user, cash, income


def balanced_lines(cash_id: int, income_id: int, amount: str = "125.50"):
    return [
        JournalEntryLineIn(
            gl_account_id=cash_id,
            description="Recurring debit",
            debit=Decimal(amount),
            credit=Decimal("0"),
        ),
        JournalEntryLineIn(
            gl_account_id=income_id,
            description="Recurring credit",
            debit=Decimal("0"),
            credit=Decimal(amount),
        ),
    ]


@pytest.mark.accounting
def test_monthly_schedule_clamps_to_last_calendar_day() -> None:
    assert recurring.monthly_date(2026, 2, 31) == date(2026, 2, 28)
    assert recurring.next_monthly_date(date(2028, 1, 31), 31) == date(2028, 2, 29)
    assert recurring.first_monthly_date_on_or_after(
        date(2026, 1, 20), 15
    ) == date(2026, 2, 15)


@pytest.mark.accounting
def test_recurring_journal_entry_posts_due_months_once_and_advances(
    db: Session, monkeypatch
) -> None:
    org, user, cash, income = seed_recurring_accounts(db)
    schedule = recurring.create_recurring_journal_entry(
        db,
        organization_id=org.id,
        created_by=user,
        name="Month end accrual",
        start_date=date(2026, 1, 31),
        end_date=None,
        day_of_month=31,
        reference_number="REC-1",
        memo="Monthly recurring accrual",
        lines=balanced_lines(cash.id, income.id),
    )
    monkeypatch.setattr(
        recurring,
        "recurring_journal_entries_enabled_for_org",
        lambda _db, *, organization_id: organization_id == org.id,
    )

    result = recurring.post_due_recurring_journal_entries(
        db,
        as_of=date(2026, 2, 28),
        organization_id=org.id,
    )

    assert result == {"posted": 2, "skipped_disabled": 0, "failed": 0}
    db.refresh(schedule)
    assert schedule.last_posted_date == date(2026, 2, 28)
    assert schedule.next_post_date == date(2026, 3, 31)
    assert schedule.is_active is True

    rows = (
        db.query(GLTransaction)
        .filter(
            GLTransaction.organization_id == org.id,
            GLTransaction.source_type == "recurring_je",
            GLTransaction.source_id == schedule.id,
        )
        .order_by(GLTransaction.transaction_date.asc())
        .all()
    )
    assert [row.transaction_date for row in rows] == [
        date(2026, 1, 31),
        date(2026, 2, 28),
    ]
    assert all(row.reference_number == "REC-1" for row in rows)

    second = recurring.post_due_recurring_journal_entries(
        db,
        as_of=date(2026, 2, 28),
        organization_id=org.id,
    )
    assert second == {"posted": 0, "skipped_disabled": 0, "failed": 0}
    assert (
        db.query(GLTransaction)
        .filter(
            GLTransaction.organization_id == org.id,
            GLTransaction.source_type == "recurring_je",
            GLTransaction.source_id == schedule.id,
        )
        .count()
        == 2
    )


@pytest.mark.accounting
def test_recurring_journal_entry_respects_feature_gate_and_org_scope(
    db: Session, monkeypatch
) -> None:
    org, user, cash, income = seed_recurring_accounts(db, "recurring-primary")
    other_org, other_user, other_cash, other_income = seed_recurring_accounts(
        db, "recurring-other"
    )
    first = recurring.create_recurring_journal_entry(
        db,
        organization_id=org.id,
        created_by=user,
        name="Primary recurring",
        start_date=date(2026, 3, 1),
        end_date=None,
        day_of_month=1,
        reference_number=None,
        memo=None,
        lines=balanced_lines(cash.id, income.id),
    )
    recurring.create_recurring_journal_entry(
        db,
        organization_id=other_org.id,
        created_by=other_user,
        name="Other recurring",
        start_date=date(2026, 3, 1),
        end_date=None,
        day_of_month=1,
        reference_number=None,
        memo=None,
        lines=balanced_lines(other_cash.id, other_income.id, "50.00"),
    )

    monkeypatch.setattr(
        recurring,
        "recurring_journal_entries_enabled_for_org",
        lambda _db, *, organization_id: False,
    )
    disabled = recurring.post_due_recurring_journal_entries(
        db,
        as_of=date(2026, 3, 1),
        organization_id=org.id,
    )
    assert disabled == {"posted": 0, "skipped_disabled": 1, "failed": 0}

    monkeypatch.setattr(
        recurring,
        "recurring_journal_entries_enabled_for_org",
        lambda _db, *, organization_id: organization_id == org.id,
    )
    enabled = recurring.post_due_recurring_journal_entries(
        db,
        as_of=date(2026, 3, 1),
        organization_id=org.id,
    )
    assert enabled == {"posted": 1, "skipped_disabled": 0, "failed": 0}
    assert (
        db.query(GLTransaction)
        .filter(
            GLTransaction.organization_id == other_org.id,
            GLTransaction.source_type == "recurring_je",
        )
        .count()
        == 0
    )
    db.refresh(first)
    assert first.next_post_date == date(2026, 4, 1)


@pytest.mark.accounting
def test_recurring_template_rejects_cross_org_gl_account(db: Session) -> None:
    org, user, cash, _income = seed_recurring_accounts(db, "recurring-scope")
    other_org, _other_user, _other_cash, other_income = seed_recurring_accounts(
        db, "recurring-scope-other"
    )
    assert other_org.id != org.id

    with pytest.raises(PostingError, match="outside this organization"):
        recurring.create_recurring_journal_entry(
            db,
            organization_id=org.id,
            created_by=user,
            name="Bad template",
            start_date=date(2026, 4, 1),
            end_date=None,
            day_of_month=1,
            reference_number=None,
            memo=None,
            lines=balanced_lines(cash.id, other_income.id),
        )
