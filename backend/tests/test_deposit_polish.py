from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.deposit import Deposit
from app.models.deposit_line import DepositLine
from app.models.gl_account import GLAccount
from app.models.receipt import Receipt
from app.models.user import Organization, User, UserRole
from app.services.deposit_posting import create_deposit, edit_deposit

TABLES = [
    Organization.__table__,
    User.__table__,
    GLAccount.__table__,
    Receipt.__table__,
    Deposit.__table__,
    DepositLine.__table__,
    AuditLog.__table__,
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
        engine.dispose()


def seed(db: Session):
    org = Organization(name="Deposits", slug="deposits-polish")
    db.add(org)
    db.flush()
    user = User(
        email="deposit-polish@example.com",
        hashed_password="x",
        first_name="Deposit",
        last_name="Admin",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    cash_a = GLAccount(
        organization_id=org.id,
        gl_number="1150",
        name="Operating",
        account_type="ASSET",
        is_active=True,
    )
    cash_b = GLAccount(
        organization_id=org.id,
        gl_number="1160",
        name="Escrow",
        account_type="ASSET",
        is_active=True,
    )
    db.add_all([user, cash_a, cash_b])
    db.flush()

    receipts = []
    for idx, (cash, amount) in enumerate(
        [(cash_a, "10.00"), (cash_a, "20.00"), (cash_b, "30.00"), (cash_a, "40.00")],
        start=1,
    ):
        row = Receipt(
            organization_id=org.id,
            type="OTHER",
            receipt_date=date(2026, 9, idx),
            amount=Decimal(amount),
            cash_gl_account_id=cash.id,
            received_from=f"Payer {idx}",
            is_active=True,
            is_reversed=False,
            created_by_id=user.id,
        )
        db.add(row)
        receipts.append(row)
    db.commit()
    return org, user, cash_a, cash_b, receipts


@pytest.mark.accounting
def test_deposit_auto_number_increments_independently_per_bank(db: Session) -> None:
    org, user, cash_a, cash_b, receipts = seed(db)
    first = create_deposit(
        db,
        organization_id=org.id,
        bank_gl_account_id=cash_a.id,
        deposit_date=date(2026, 9, 10),
        deposit_number=None,
        description=None,
        notes=None,
        receipt_ids=[receipts[0].id],
        created_by=user,
    )
    second = create_deposit(
        db,
        organization_id=org.id,
        bank_gl_account_id=cash_a.id,
        deposit_date=date(2026, 9, 11),
        deposit_number=None,
        description=None,
        notes=None,
        receipt_ids=[receipts[1].id],
        created_by=user,
    )
    escrow = create_deposit(
        db,
        organization_id=org.id,
        bank_gl_account_id=cash_b.id,
        deposit_date=date(2026, 9, 12),
        deposit_number=None,
        description=None,
        notes=None,
        receipt_ids=[receipts[2].id],
        created_by=user,
    )
    assert (first.deposit_number, first.bank_sequence) == ("D-00001", 1)
    assert (second.deposit_number, second.bank_sequence) == ("D-00002", 2)
    assert (escrow.deposit_number, escrow.bank_sequence) == ("D-00001", 1)


@pytest.mark.accounting
def test_edit_deposit_replaces_membership_and_recomputes_total_without_gl(db: Session) -> None:
    org, user, cash_a, _cash_b, receipts = seed(db)
    deposit = create_deposit(
        db,
        organization_id=org.id,
        bank_gl_account_id=cash_a.id,
        deposit_date=date(2026, 9, 10),
        deposit_number=None,
        description="Original",
        notes=None,
        receipt_ids=[receipts[0].id],
        created_by=user,
    )
    edit_deposit(
        db,
        deposit=deposit,
        deposit_date=date(2026, 9, 20),
        description="Edited",
        receipt_ids=[receipts[0].id, receipts[3].id],
        fields_set={"deposit_date", "description", "receipt_ids"},
        edited_by=user,
    )
    db.refresh(deposit)
    assert deposit.deposit_date == date(2026, 9, 20)
    assert deposit.description == "Edited"
    assert Decimal(deposit.total) == Decimal("50.00")
    ids = {
        x.receipt_id
        for x in db.query(DepositLine).filter(DepositLine.deposit_id == deposit.id)
    }
    assert ids == {receipts[0].id, receipts[3].id}
