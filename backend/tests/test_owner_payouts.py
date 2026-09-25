from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import init_db  # noqa: F401
from app.core.database import Base
from app.models.bank_account import BankAccount
from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.owner_ach import OwnerACHAccount
from app.models.owner_payout import OwnerPayout
from app.models.user import Organization, User, UserRole
from app.routers.owner_payouts import _require_write
from app.schemas.gl_transaction import PostingLine
from app.schemas.owner_payout import OwnerPayoutDraftIn, OwnerPayoutEntryIn
from app.services.gl_posting import post_transaction
from app.services.owner_ledger import get_owner_subledger
from app.services.owner_payout_confirmation import confirm_external_payout_batch
from app.services.owner_payouts import (
    OwnerPayoutError,
    create_owner_payout_draft,
    preview_owner_payouts,
)


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def seed(db: Session):
    org = Organization(name="Payout Org", slug="payout-org")
    other = Organization(name="Other Payout Org", slug="other-payout-org")
    db.add_all([org, other])
    db.flush()

    admin = User(
        email="payout-admin@example.com",
        hashed_password="x",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    manager = User(
        email="payout-manager@example.com",
        hashed_password="x",
        first_name="Manager",
        last_name="User",
        role=UserRole.MANAGER,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    owner = User(
        email="payout-owner@example.com",
        hashed_password="x",
        first_name="Owner",
        last_name="One",
        role=UserRole.OWNER,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    owner_without_ach = User(
        email="payout-owner-two@example.com",
        hashed_password="x",
        first_name="Owner",
        last_name="Two",
        role=UserRole.OWNER,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    db.add_all([admin, manager, owner, owner_without_ach])
    db.flush()

    cash = GLAccount(
        organization_id=org.id,
        gl_number="1150",
        name="Rental Trust",
        account_type="ASSET",
        subject_to_mgmt_fees=False,
        include_on_cash_flow=True,
        must_clear=False,
        is_active=True,
    )
    owner_funds = GLAccount(
        organization_id=org.id,
        gl_number="2401",
        name="Owner Funds",
        account_type="LIABILITY",
        subject_to_mgmt_fees=False,
        include_on_cash_flow=True,
        must_clear=False,
        is_active=True,
    )
    income = GLAccount(
        organization_id=org.id,
        gl_number="4100",
        name="Rent",
        account_type="INCOME",
        subject_to_mgmt_fees=True,
        include_on_cash_flow=True,
        must_clear=False,
        is_active=True,
    )
    db.add_all([cash, owner_funds, income])
    db.flush()

    bank = BankAccount(
        organization_id=org.id,
        name="Client Trust",
        bank_name="Test Bank",
        routing_number="021000021",
        account_number="123456789",
        gl_account_id=cash.id,
        account_type="OPERATING",
        ach_format="CSV",
        is_active=True,
        created_by_id=admin.id,
    )
    db.add(bank)
    db.flush()

    db.add(
        OwnerACHAccount(
            organization_id=org.id,
            owner_id=owner.id,
            account_holder_name="Owner One",
            bank_name="Owner Bank",
            routing_number="021000021",
            account_number="987654321",
            account_type="CHECKING",
            is_enabled=True,
            created_by_id=admin.id,
            updated_by_id=admin.id,
        )
    )
    db.commit()

    post_transaction(
        db=db,
        organization_id=org.id,
        transaction_date=date(2026, 9, 25),
        transaction_type="JOURNAL_ENTRY",
        memo="Seed owner balance",
        created_by=admin,
        lines=[
            PostingLine(
                gl_account_id=cash.id,
                property_id=None,
                unit_id=None,
                owner_id=None,
                description="Cash",
                debit=Decimal("100.00"),
                credit=Decimal("0.00"),
            ),
            PostingLine(
                gl_account_id=income.id,
                property_id=None,
                unit_id=None,
                owner_id=owner.id,
                description="Owner income",
                debit=Decimal("0.00"),
                credit=Decimal("100.00"),
            ),
        ],
    )
    return org, admin, manager, owner, owner_without_ach, bank


@pytest.mark.accounting
def test_owner_payout_preview_uses_subledger_and_masks_destination(db: Session) -> None:
    org, _admin, _manager, owner, owner_without_ach, bank = seed(db)

    preview = preview_owner_payouts(
        db,
        organization_id=org.id,
        bank_account_id=bank.id,
    )
    by_owner = {row["owner_id"]: row for row in preview["candidates"]}

    assert preview["book_balance"] == Decimal("100.00")
    assert by_owner[owner.id]["available_balance"] == Decimal("100.00")
    assert by_owner[owner.id]["can_pay"] is True
    assert by_owner[owner.id]["account_last4"] == "4321"
    assert by_owner[owner_without_ach.id]["can_pay"] is False
    assert by_owner[owner_without_ach.id]["account_last4"] is None


@pytest.mark.accounting
def test_owner_payout_draft_is_durable_but_does_not_change_financial_state(db: Session) -> None:
    org, admin, _manager, owner, _owner_without_ach, bank = seed(db)
    before_transactions = db.query(GLTransaction).count()
    before_balance = get_owner_subledger(
        db,
        organization_id=org.id,
        owner_id=owner.id,
    )["balance"]

    payload = OwnerPayoutDraftIn(
        bank_account_id=bank.id,
        effective_date=date(2026, 9, 26),
        payouts=[OwnerPayoutEntryIn(owner_id=owner.id, amount=Decimal("60.00"))],
    )
    batch, total, rows = create_owner_payout_draft(
        db,
        organization_id=org.id,
        payload=payload,
        created_by=admin,
    )

    assert batch.startswith("OWN-DRAFT-20260926-")
    assert total == Decimal("60.00")
    assert len(rows) == 1
    payout = db.query(OwnerPayout).one()
    assert payout.status == "DRAFT"
    assert payout.destination_last4 == "4321"
    assert payout.gl_transaction_id is None
    assert db.query(GLTransaction).count() == before_transactions

    after_balance = get_owner_subledger(
        db,
        organization_id=org.id,
        owner_id=owner.id,
    )["balance"]
    assert after_balance == before_balance


@pytest.mark.accounting
def test_external_confirmation_posts_accounting_after_human_attestation(db: Session) -> None:
    org, admin, manager, owner, _owner_without_ach, bank = seed(db)
    payload = OwnerPayoutDraftIn(
        bank_account_id=bank.id,
        effective_date=date(2026, 9, 26),
        payouts=[OwnerPayoutEntryIn(owner_id=owner.id, amount=Decimal("60.00"))],
    )
    batch, _total, _rows = create_owner_payout_draft(
        db,
        organization_id=org.id,
        payload=payload,
        created_by=admin,
    )
    before_transactions = db.query(GLTransaction).count()

    rows = confirm_external_payout_batch(
        db,
        organization_id=org.id,
        batch_reference=batch,
        confirmation_date=date(2026, 9, 26),
        confirmed_by=manager,
    )

    assert len(rows) == 1
    payout = db.query(OwnerPayout).one()
    assert payout.status == "PAID"
    assert payout.confirmed_by_id == manager.id
    assert payout.gl_transaction_id is not None
    assert db.query(GLTransaction).count() == before_transactions + 1

    txn = db.get(GLTransaction, payout.gl_transaction_id)
    assert txn is not None
    assert txn.transaction_type == "OWNER_DRAW"
    assert txn.source_type == "owner_payout"
    assert txn.source_id == payout.id

    ledger = get_owner_subledger(
        db,
        organization_id=org.id,
        owner_id=owner.id,
    )
    assert ledger is not None
    assert ledger["balance"] == Decimal("40.00")

    with pytest.raises(OwnerPayoutError, match="Only a draft"):
        confirm_external_payout_batch(
            db,
            organization_id=org.id,
            batch_reference=batch,
            confirmation_date=date(2026, 9, 26),
            confirmed_by=manager,
        )


@pytest.mark.accounting
def test_owner_payout_draft_rejects_overpayment_without_partial_state(db: Session) -> None:
    org, admin, _manager, owner, _owner_without_ach, bank = seed(db)

    payload = OwnerPayoutDraftIn(
        bank_account_id=bank.id,
        effective_date=date(2026, 9, 26),
        payouts=[OwnerPayoutEntryIn(owner_id=owner.id, amount=Decimal("101.00"))],
    )
    with pytest.raises(OwnerPayoutError, match="exceeds the available balance"):
        create_owner_payout_draft(
            db,
            organization_id=org.id,
            payload=payload,
            created_by=admin,
        )

    assert db.query(OwnerPayout).count() == 0


@pytest.mark.accounting
def test_owner_payout_draft_rejects_missing_ach_before_saving(db: Session) -> None:
    org, admin, _manager, owner, owner_without_ach, bank = seed(db)

    payload = OwnerPayoutDraftIn(
        bank_account_id=bank.id,
        effective_date=date(2026, 9, 26),
        payouts=[
            OwnerPayoutEntryIn(owner_id=owner.id, amount=Decimal("25.00")),
            OwnerPayoutEntryIn(
                owner_id=owner_without_ach.id,
                amount=Decimal("1.00"),
            ),
        ],
    )
    with pytest.raises(OwnerPayoutError, match="not configured and enabled"):
        create_owner_payout_draft(
            db,
            organization_id=org.id,
            payload=payload,
            created_by=admin,
        )

    assert db.query(OwnerPayout).count() == 0


@pytest.mark.accounting
def test_pay_owners_write_scope_is_staff_only() -> None:
    _require_write(SimpleNamespace(role="ADMIN"))
    _require_write(SimpleNamespace(role="MANAGER"))

    for role in ("OWNER", "TENANT", "CREW"):
        with pytest.raises(HTTPException) as exc:
            _require_write(SimpleNamespace(role=role))
        assert exc.value.status_code == 403
