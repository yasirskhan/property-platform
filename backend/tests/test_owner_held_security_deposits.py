from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.accounting_key_account import AccountingKeyAccount
from app.models.bank_account import BankAccount
from app.models.gl_account import GLAccount
from app.models.user import Organization, User, UserRole
from app.routers.leases import _validate_security_deposit_account_choice
from app.services.owner_held_deposits import (
    OwnerHeldDepositError,
    add_deposit_key_account,
    list_deposit_key_accounts,
    list_eligible_deposit_accounts,
    validate_owner_held_deposit_account,
)

TABLES = [
    Organization.__table__,
    User.__table__,
    GLAccount.__table__,
    BankAccount.__table__,
    AccountingKeyAccount.__table__,
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
    org = Organization(name="Owner Held Org", slug="owner-held-org")
    other = Organization(name="Other Org", slug="owner-held-other")
    db.add_all([org, other])
    db.flush()

    admin = User(
        email="owner-held-admin@example.com",
        hashed_password="x",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    db.add(admin)
    db.flush()

    operating = GLAccount(
        organization_id=org.id,
        gl_number="1150",
        name="Operating Cash",
        account_type="ASSET",
        subject_to_mgmt_fees=False,
        include_on_cash_flow=True,
        must_clear=False,
        is_active=True,
    )
    good = GLAccount(
        organization_id=org.id,
        gl_number="2102",
        name="Owner Held Security Deposits",
        account_type="LIABILITY",
        offset_account="1150",
        subject_to_mgmt_fees=False,
        include_on_cash_flow=False,
        must_clear=False,
        is_active=True,
    )
    wrong_offset = GLAccount(
        organization_id=org.id,
        gl_number="2103",
        name="Wrong Deposit",
        account_type="LIABILITY",
        offset_account="1160",
        subject_to_mgmt_fees=False,
        include_on_cash_flow=False,
        must_clear=False,
        is_active=True,
    )
    other_gl = GLAccount(
        organization_id=other.id,
        gl_number="2102",
        name="Other Owner Held",
        account_type="LIABILITY",
        offset_account="1150",
        subject_to_mgmt_fees=False,
        include_on_cash_flow=False,
        must_clear=False,
        is_active=True,
    )
    db.add_all([operating, good, wrong_offset, other_gl])
    db.flush()
    db.add(
        BankAccount(
            organization_id=org.id,
            name="Client Trust",
            gl_account_id=operating.id,
            account_type="OPERATING",
            is_active=True,
            created_by_id=admin.id,
        )
    )
    db.commit()
    return org, other, admin, good, wrong_offset, other_gl


@pytest.mark.accounting
def test_owner_held_key_account_requires_liability_offset_to_operating_cash(db: Session) -> None:
    org, _other, _admin, good, wrong_offset, _other_gl = seed(db)

    assert validate_owner_held_deposit_account(
        db, organization_id=org.id, gl_account_id=good.id
    ).id == good.id

    with pytest.raises(OwnerHeldDepositError, match="offset to Operating Cash"):
        validate_owner_held_deposit_account(
            db, organization_id=org.id, gl_account_id=wrong_offset.id
        )


@pytest.mark.accounting
def test_owner_held_key_account_is_org_scoped_and_idempotent(db: Session) -> None:
    org, _other, admin, good, _wrong_offset, other_gl = seed(db)

    first = add_deposit_key_account(
        db,
        organization_id=org.id,
        gl_account_id=good.id,
        created_by=admin,
    )
    second = add_deposit_key_account(
        db,
        organization_id=org.id,
        gl_account_id=good.id,
        created_by=admin,
    )
    assert first.id == second.id
    assert len(list_deposit_key_accounts(db, organization_id=org.id)) == 1

    with pytest.raises(OwnerHeldDepositError, match="not found"):
        add_deposit_key_account(
            db,
            organization_id=org.id,
            gl_account_id=other_gl.id,
            created_by=admin,
        )


@pytest.mark.accounting
def test_eligible_owner_held_accounts_exclude_invalid_liabilities(db: Session) -> None:
    org, _other, _admin, good, wrong_offset, _other_gl = seed(db)
    ids = {row.id for row in list_eligible_deposit_accounts(db, organization_id=org.id)}
    assert good.id in ids
    assert wrong_offset.id not in ids


@pytest.mark.accounting
def test_lease_deposit_choice_requires_configured_key_account(db: Session, monkeypatch) -> None:
    org, _other, admin, good, _wrong_offset, _other_gl = seed(db)
    monkeypatch.setattr(
        "app.routers.leases.owner_held_feature_allowed",
        lambda _db, *, user: True,
    )

    with pytest.raises(HTTPException) as missing:
        _validate_security_deposit_account_choice(
            db,
            current_user=admin,
            organization_id=org.id,
            gl_account_id=good.id,
        )
    assert missing.value.status_code == 422

    add_deposit_key_account(
        db,
        organization_id=org.id,
        gl_account_id=good.id,
        created_by=admin,
    )
    _validate_security_deposit_account_choice(
        db,
        current_user=admin,
        organization_id=org.id,
        gl_account_id=good.id,
    )


@pytest.mark.accounting
def test_lease_deposit_choice_is_release_gated(db: Session, monkeypatch) -> None:
    org, _other, admin, good, _wrong_offset, _other_gl = seed(db)
    monkeypatch.setattr(
        "app.routers.leases.owner_held_feature_allowed",
        lambda _db, *, user: False,
    )
    with pytest.raises(HTTPException) as denied:
        _validate_security_deposit_account_choice(
            db,
            current_user=admin,
            organization_id=org.id,
            gl_account_id=good.id,
        )
    assert denied.value.status_code == 403
