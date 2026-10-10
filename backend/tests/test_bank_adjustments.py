from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.routers.bank_adjustments as bank_adjustments_router
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.bank_account import BankAccount
from app.models.gl_account import GLAccount, GLAccountPostingRestriction
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.organization_feature_setting import OrganizationFeatureSetting
from app.models.release_gate import ReleaseGate, ReleaseGateOrganization
from app.models.user import Organization, User, UserRole
from app.services.bank_adjustments import (
    create_bank_adjustment,
    reverse_bank_adjustment,
)
from app.services.gl_posting import PostingError

TEST_TABLES = [
    Organization.__table__,
    User.__table__,
    GLAccount.__table__,
    GLAccountPostingRestriction.__table__,
    ReleaseGate.__table__,
    ReleaseGateOrganization.__table__,
    OrganizationFeatureSetting.__table__,
    BankAccount.__table__,
    GLTransaction.__table__,
    GLEntry.__table__,
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
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=list(reversed(TEST_TABLES)))
        engine.dispose()


def seed(db: Session):
    org = Organization(name="Adjustments", slug="adjustments")
    other_org = Organization(name="Other", slug="adjustments-other")
    db.add_all([org, other_org])
    db.flush()
    user = User(
        email="adjustments@example.com",
        hashed_password="x",
        first_name="A",
        last_name="D",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    bank_gl = GLAccount(
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
    foreign_offset = GLAccount(
        organization_id=other_org.id,
        gl_number="6100",
        name="Other Fees",
        account_type="EXPENSE",
        is_active=True,
    )
    db.add_all([user, bank_gl, offset, foreign_offset])
    db.flush()
    bank = BankAccount(
        organization_id=org.id,
        name="Client Trust",
        gl_account_id=bank_gl.id,
        account_type="OPERATING",
        is_active=True,
        created_by_id=user.id,
    )
    db.add(bank)
    db.commit()
    return org, user, bank, bank_gl, offset, foreign_offset


@pytest.mark.accounting
def test_increase_and_decrease_post_expected_bank_sides(db: Session) -> None:
    org, user, bank, bank_gl, offset, _foreign = seed(db)
    increase = create_bank_adjustment(
        db,
        organization_id=org.id,
        bank_account=bank,
        adjustment_date=date(2026, 10, 1),
        direction="INCREASE",
        amount=Decimal("25.50"),
        offset_gl_account_id=offset.id,
        created_by=user,
        reference_number="ADJ-1",
        memo="Interest credit",
    )
    decrease = create_bank_adjustment(
        db,
        organization_id=org.id,
        bank_account=bank,
        adjustment_date=date(2026, 10, 2),
        direction="DECREASE",
        amount=Decimal("7.25"),
        offset_gl_account_id=offset.id,
        created_by=user,
        reference_number="ADJ-2",
        memo="Bank fee",
    )

    inc_bank = next(x for x in increase.entries if x.gl_account_id == bank_gl.id)
    inc_offset = next(x for x in increase.entries if x.gl_account_id == offset.id)
    dec_bank = next(x for x in decrease.entries if x.gl_account_id == bank_gl.id)
    dec_offset = next(x for x in decrease.entries if x.gl_account_id == offset.id)

    assert increase.transaction_type == "BANK_ADJUSTMENT"
    assert increase.source_type == "bank_adjustment"
    assert increase.source_id == bank.id
    assert inc_bank.debit == Decimal("25.50")
    assert inc_bank.credit == Decimal("0.00")
    assert inc_offset.credit == Decimal("25.50")
    assert dec_bank.credit == Decimal("7.25")
    assert dec_offset.debit == Decimal("7.25")


@pytest.mark.accounting
def test_offset_account_must_belong_to_same_organization(db: Session) -> None:
    org, user, bank, _bank_gl, _offset, foreign_offset = seed(db)
    with pytest.raises(PostingError, match="not found in your organization"):
        create_bank_adjustment(
            db,
            organization_id=org.id,
            bank_account=bank,
            adjustment_date=date(2026, 10, 1),
            direction="DECREASE",
            amount=Decimal("10.00"),
            offset_gl_account_id=foreign_offset.id,
            created_by=user,
        )
    assert db.query(GLTransaction).count() == 0


@pytest.mark.accounting
def test_locked_period_rejects_adjustment(db: Session) -> None:
    org, user, bank, _bank_gl, offset, _foreign = seed(db)
    org.locked_through_date = date(2026, 10, 1)
    db.commit()
    with pytest.raises(PostingError, match="locked through"):
        create_bank_adjustment(
            db,
            organization_id=org.id,
            bank_account=bank,
            adjustment_date=date(2026, 10, 1),
            direction="INCREASE",
            amount=Decimal("10.00"),
            offset_gl_account_id=offset.id,
            created_by=user,
        )
    assert db.query(GLTransaction).count() == 0


@pytest.mark.accounting
def test_reversal_is_immutable_and_cannot_repeat(db: Session) -> None:
    org, user, bank, bank_gl, offset, _foreign = seed(db)
    original = create_bank_adjustment(
        db,
        organization_id=org.id,
        bank_account=bank,
        adjustment_date=date(2026, 10, 2),
        direction="DECREASE",
        amount=Decimal("18.00"),
        offset_gl_account_id=offset.id,
        created_by=user,
    )
    original_id = original.id

    reversed_original = reverse_bank_adjustment(
        db,
        organization_id=org.id,
        bank_account=bank,
        transaction_id=original_id,
        reversal_date=date(2026, 10, 3),
        created_by=user,
        memo="Correct bank fee",
    )
    assert reversed_original.is_reversed is True

    reversal = (
        db.query(GLTransaction)
        .filter(GLTransaction.reversal_of_id == original_id)
        .one()
    )
    assert reversal.transaction_type == "REVERSAL"
    reversal_bank = next(x for x in reversal.entries if x.gl_account_id == bank_gl.id)
    assert reversal_bank.debit == Decimal("18.00")
    assert reversal_bank.credit == Decimal("0.00")

    with pytest.raises(PostingError, match="already been reversed"):
        reverse_bank_adjustment(
            db,
            organization_id=org.id,
            bank_account=bank,
            transaction_id=original_id,
            reversal_date=date(2026, 10, 4),
            created_by=user,
        )
    assert db.query(GLTransaction).count() == 2


def test_route_capability_rejects_disabled_feature(monkeypatch) -> None:
    user = SimpleNamespace(organization_id=42)
    monkeypatch.setattr(
        bank_adjustments_router,
        "resolve_customer_features",
        lambda _db, *, user: [
            SimpleNamespace(
                key="release.accounting.bank_adjustments",
                allowed=False,
            )
        ],
    )
    with pytest.raises(HTTPException) as exc:
        bank_adjustments_router._require_adjustments_capability(object(), user)
    assert exc.value.status_code == 403
