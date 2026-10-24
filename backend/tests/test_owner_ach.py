from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import pytest

from app.core.database import Base
from app.models.owner_ach import OwnerACHAccount
from app.models.user import Organization, User, UserRole
from app.schemas.owner_ach import OwnerACHUpsertIn
from app.services.owner_ach import OwnerACHError, get_owner_ach, upsert_owner_ach
from app.routers.owner_ach import _require_scope
from fastapi import HTTPException


TABLES = [
    Organization.__table__,
    User.__table__,
    OwnerACHAccount.__table__,
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
    org = Organization(name="Owner ACH Org", slug="owner-ach-org")
    other = Organization(name="Other Org", slug="other-owner-ach-org")
    db.add_all([org, other])
    db.flush()

    admin = User(
        email="admin-owner-ach@example.com",
        hashed_password="x",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    owner = User(
        email="owner-ach@example.com",
        hashed_password="x",
        first_name="Owner",
        last_name="One",
        role=UserRole.OWNER,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    other_owner = User(
        email="other-owner-ach@example.com",
        hashed_password="x",
        first_name="Other",
        last_name="Owner",
        role=UserRole.OWNER,
        organization_id=other.id,
        is_active=True,
        is_verified=True,
    )
    manager = User(
        email="manager-owner-ach@example.com",
        hashed_password="x",
        first_name="Manager",
        last_name="User",
        role=UserRole.MANAGER,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    db.add_all([admin, owner, other_owner, manager])
    db.commit()
    return org, other, admin, owner, other_owner, manager


@pytest.mark.accounting
def test_owner_ach_setup_is_org_scoped_and_masks_account(db: Session) -> None:
    org, _other, admin, owner, _other_owner, _manager = seed(db)
    payload = OwnerACHUpsertIn(
        account_holder_name="Owner One",
        bank_name="Test Bank",
        routing_number="021000021",
        account_number="123456789012",
        account_type="CHECKING",
        is_enabled=True,
    )

    saved = upsert_owner_ach(
        db,
        organization_id=org.id,
        owner_id=owner.id,
        payload=payload,
        actor=admin,
    )
    assert saved.configured is True
    assert saved.routing_last4 == "0021"
    assert saved.account_last4 == "9012"
    assert "123456789012" not in saved.model_dump_json()

    row = db.query(OwnerACHAccount).one()
    assert row.owner_id == owner.id
    assert row.organization_id == org.id


@pytest.mark.accounting
def test_owner_ach_update_reuses_single_owner_row(db: Session) -> None:
    org, _other, admin, owner, _other_owner, _manager = seed(db)
    first = OwnerACHUpsertIn(
        account_holder_name="Owner One",
        routing_number="021000021",
        account_number="111122223333",
        account_type="CHECKING",
    )
    second = OwnerACHUpsertIn(
        account_holder_name="Owner One Updated",
        routing_number="021000021",
        account_number="999988887777",
        account_type="SAVINGS",
        is_enabled=False,
    )
    upsert_owner_ach(
        db,
        organization_id=org.id,
        owner_id=owner.id,
        payload=first,
        actor=admin,
    )
    updated = upsert_owner_ach(
        db,
        organization_id=org.id,
        owner_id=owner.id,
        payload=second,
        actor=admin,
    )

    assert db.query(OwnerACHAccount).count() == 1
    assert updated.account_holder_name == "Owner One Updated"
    assert updated.account_type == "SAVINGS"
    assert updated.account_last4 == "7777"
    assert updated.is_enabled is False


@pytest.mark.accounting
def test_owner_ach_rejects_invalid_routing_cross_org_and_non_owner(db: Session) -> None:
    org, _other, admin, owner, other_owner, manager = seed(db)
    bad = OwnerACHUpsertIn(
        account_holder_name="Owner One",
        routing_number="123456789",
        account_number="1234",
        account_type="CHECKING",
    )
    with pytest.raises(OwnerACHError, match="valid ABA"):
        upsert_owner_ach(
            db,
            organization_id=org.id,
            owner_id=owner.id,
            payload=bad,
            actor=admin,
        )

    good = OwnerACHUpsertIn(
        account_holder_name="Other Owner",
        routing_number="021000021",
        account_number="1234",
        account_type="CHECKING",
    )
    with pytest.raises(OwnerACHError, match="Owner not found"):
        upsert_owner_ach(
            db,
            organization_id=org.id,
            owner_id=other_owner.id,
            payload=good,
            actor=admin,
        )
    with pytest.raises(OwnerACHError, match="Owner not found"):
        get_owner_ach(
            db,
            organization_id=org.id,
            owner_id=manager.id,
        )


@pytest.mark.accounting
def test_owner_ach_sensitive_route_scope_allows_admin_and_owner_self_only(db: Session) -> None:
    _org, _other, admin, owner, _other_owner, manager = seed(db)

    _require_scope(admin, owner.id)
    _require_scope(owner, owner.id)

    with pytest.raises(HTTPException) as manager_error:
        _require_scope(manager, owner.id)
    assert manager_error.value.status_code == 403

    second_owner = User(
        email="second-owner-ach@example.com",
        hashed_password="x",
        first_name="Second",
        last_name="Owner",
        role=UserRole.OWNER,
        organization_id=owner.organization_id,
        is_active=True,
        is_verified=True,
    )
    db.add(second_owner)
    db.commit()
    with pytest.raises(HTTPException) as owner_error:
        _require_scope(owner, second_owner.id)
    assert owner_error.value.status_code == 403
