from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
import app.routers.management_fees as management_fees
from app.core.database import Base
from app.models.gl_account import GLAccount
from app.models.property import Property
from app.models.receipt import Receipt
from app.models.user import Organization, User, UserRole


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def _seed_org(db, slug: str):
    org = Organization(name=f"{slug} org", slug=slug)
    db.add(org)
    db.flush()
    user = User(
        email=f"{slug}@example.com",
        hashed_password="unused",
        first_name="Fee",
        last_name="Admin",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
    )
    account = GLAccount(
        organization_id=org.id,
        gl_number="1150",
        name="Rental Trust",
        account_type="ASSET",
        is_active=True,
    )
    prop = Property(
        organization_id=org.id,
        name=f"{slug} Property",
        property_type="MULTI_FAMILY",
        address_line1="1 Main St",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        country="USA",
        is_active=True,
    )
    db.add_all([user, account, prop])
    db.flush()
    return org, user, account, prop


def _receipt(
    db,
    *,
    org_id: int,
    account_id: int,
    property_id: int,
    amount: str,
    excluded: bool,
    reversed: bool = False,
    reversal_of_id: int | None = None,
):
    row = Receipt(
        organization_id=org_id,
        type="OTHER",
        receipt_date=date(2026, 9, 15),
        amount=Decimal(amount),
        cash_gl_account_id=account_id,
        income_gl_account_id=account_id,
        received_from="Exclusion payer",
        exclude_from_mgmt_fee=excluded,
        property_id=property_id,
        reference_number=f"REF-{amount}",
        is_reversed=reversed,
        reversal_of_id=reversal_of_id,
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row


def _enable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        management_fees,
        "permission_allows_user",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        management_fees,
        "resolve_customer_features",
        lambda *args, **kwargs: [
            SimpleNamespace(
                key=management_fees.EXCLUSIONS_FEATURE_KEY,
                allowed=True,
            )
        ],
    )


def test_management_fee_exclusions_require_independent_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, engine = _session()
    try:
        _org, user, _account, _prop = _seed_org(db, "gate-exclusions")
        db.commit()
        monkeypatch.setattr(
            management_fees,
            "permission_allows_user",
            lambda *args, **kwargs: True,
        )
        monkeypatch.setattr(
            management_fees,
            "resolve_customer_features",
            lambda *args, **kwargs: [],
        )

        with pytest.raises(HTTPException) as exc:
            management_fees.list_management_fee_exclusions(
                date_from=None,
                date_to=None,
                property_id=None,
                include_reversed=True,
                limit=200,
                db=db,
                current_user=user,
            )
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_management_fee_exclusions_are_org_scoped_and_only_explicit_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, engine = _session()
    try:
        org, user, account, prop = _seed_org(db, "main-exclusions")
        other_org, _other_user, other_account, other_prop = _seed_org(
            db, "other-exclusions"
        )
        included = _receipt(
            db,
            org_id=org.id,
            account_id=account.id,
            property_id=prop.id,
            amount="10.00",
            excluded=False,
        )
        excluded = _receipt(
            db,
            org_id=org.id,
            account_id=account.id,
            property_id=prop.id,
            amount="25.00",
            excluded=True,
        )
        reversed_source = _receipt(
            db,
            org_id=org.id,
            account_id=account.id,
            property_id=prop.id,
            amount="30.00",
            excluded=True,
            reversed=True,
        )
        reversal_mirror = _receipt(
            db,
            org_id=org.id,
            account_id=account.id,
            property_id=prop.id,
            amount="30.00",
            excluded=True,
            reversal_of_id=reversed_source.id,
        )
        other = _receipt(
            db,
            org_id=other_org.id,
            account_id=other_account.id,
            property_id=other_prop.id,
            amount="99.00",
            excluded=True,
        )
        db.commit()
        _enable(monkeypatch)

        result = management_fees.list_management_fee_exclusions(
            date_from=None,
            date_to=None,
            property_id=None,
            include_reversed=True,
            limit=200,
            db=db,
            current_user=user,
        )

        ids = {row.receipt_id for row in result.items}
        assert ids == {excluded.id, reversed_source.id}
        assert included.id not in ids
        assert reversal_mirror.id not in ids
        assert other.id not in ids
        assert result.total == 2
        assert {row.property_name for row in result.items} == {prop.name}

        active_only = management_fees.list_management_fee_exclusions(
            date_from=None,
            date_to=None,
            property_id=None,
            include_reversed=False,
            limit=200,
            db=db,
            current_user=user,
        )
        assert [row.receipt_id for row in active_only.items] == [excluded.id]
    finally:
        db.close()
        engine.dispose()
