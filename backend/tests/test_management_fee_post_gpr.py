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
from app.models.user import Organization, User, UserRole
from app.schemas.journal_entry import GPRPostIn


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def _seed_user(db):
    org = Organization(name="GPR Fee Org", slug="gpr-fee-org")
    db.add(org)
    db.flush()
    user = User(
        email="gpr-fee-admin@example.com",
        hashed_password="unused",
        first_name="GPR",
        last_name="Admin",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return org, user


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
                key=management_fees.MANAGEMENT_FEE_GPR_FEATURE_KEY,
                allowed=True,
            )
        ],
    )


def test_management_fee_gpr_requires_its_independent_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, engine = _session()
    try:
        _org, user = _seed_user(db)
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
            management_fees.get_management_fee_gpr_candidates(
                month=date(2026, 9, 1), db=db, current_user=user
            )
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_management_fee_gpr_preview_uses_shared_candidate_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, engine = _session()
    try:
        org, user = _seed_user(db)
        _enable(monkeypatch)
        seen = {}

        def fake_list(db_arg, *, organization_id, month):
            seen.update(db=db_arg, organization_id=organization_id, month=month)
            return [
                SimpleNamespace(
                    unit_id=11,
                    property_id=22,
                    property_name="Shared Engine Property",
                    unit_number="A",
                    lease_id=None,
                    market_rent=Decimal("1500.00"),
                    scheduled_rent=Decimal("0.00"),
                    loss_gain=Decimal("1500.00"),
                    already_posted=False,
                    transaction_id=None,
                )
            ]

        monkeypatch.setattr(management_fees, "list_gpr_candidates", fake_list)
        result = management_fees.get_management_fee_gpr_candidates(
            month=date(2026, 9, 17), db=db, current_user=user
        )

        assert seen["db"] is db
        assert seen["organization_id"] == org.id
        assert seen["month"] == date(2026, 9, 1)
        assert result.total == 1
        assert result.unposted == 1
        assert result.items[0].unit_id == 11
    finally:
        db.close()
        engine.dispose()


def test_management_fee_gpr_post_delegates_to_shared_posting_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, engine = _session()
    try:
        org, user = _seed_user(db)
        _enable(monkeypatch)
        seen = {}

        def fake_post(db_arg, *, organization_id, month, unit_ids, created_by):
            seen.update(
                db=db_arg,
                organization_id=organization_id,
                month=month,
                unit_ids=unit_ids,
                created_by=created_by,
            )
            return [SimpleNamespace(id=901), SimpleNamespace(id=902)]

        monkeypatch.setattr(management_fees, "post_gpr", fake_post)
        result = management_fees.post_management_fee_gpr(
            GPRPostIn(month=date(2026, 9, 25), unit_ids=[1, 2]),
            db=db,
            current_user=user,
        )

        assert seen["db"] is db
        assert seen["organization_id"] == org.id
        assert seen["month"] == date(2026, 9, 1)
        assert seen["unit_ids"] == [1, 2]
        assert seen["created_by"] is user
        assert result.posted == 2
        assert result.transaction_ids == [901, 902]
    finally:
        db.close()
        engine.dispose()
