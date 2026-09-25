from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
import app.routers.management_fees as management_fees
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.user import Organization, User, UserRole
from app.schemas.management_fee import OvercollectionStrategyUpdate


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def _user(db, org: Organization, role: UserRole = UserRole.ADMIN) -> User:
    user = User(
        email=f"{role.value.lower()}-{org.id}@example.com",
        hashed_password="not-used",
        first_name="Fee",
        last_name="Admin",
        role=role,
        organization_id=org.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


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
                key=management_fees.OVERCOLLECTION_FEATURE_KEY,
                allowed=True,
            )
        ],
    )


def test_overcollection_strategy_defaults_to_credits_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, engine = _session()
    try:
        org = Organization(name="Fee Org", slug="fee-org")
        db.add(org)
        db.commit()
        admin = _user(db, org)
        _enable(monkeypatch)

        result = management_fees.get_overcollection_strategy(db, admin)

        assert result.strategy == "CREDITS_THEN_RECEIPTS"
        assert result.recommended is True
    finally:
        db.close()
        engine.dispose()


def test_overcollection_strategy_updates_and_audits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, engine = _session()
    try:
        org = Organization(name="Fee Org", slug="fee-org-update")
        db.add(org)
        db.commit()
        admin = _user(db, org)
        _enable(monkeypatch)

        result = management_fees.update_overcollection_strategy(
            OvercollectionStrategyUpdate(strategy="RECEIPTS_THEN_CREDITS"),
            db,
            admin,
        )

        assert result.strategy == "RECEIPTS_THEN_CREDITS"
        assert result.recommended is False
        db.refresh(org)
        assert org.management_fee_overcollection_strategy == "RECEIPTS_THEN_CREDITS"
        audit = (
            db.query(AuditLog)
            .filter(
                AuditLog.action
                == "management_fee_overcollection_strategy_updated"
            )
            .one()
        )
        assert audit.organization_id == org.id
        assert audit.user_id == admin.id
    finally:
        db.close()
        engine.dispose()


def test_overcollection_strategy_requires_release_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, engine = _session()
    try:
        org = Organization(name="Gate Org", slug="gate-org")
        db.add(org)
        db.commit()
        admin = _user(db, org)
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
            management_fees.get_overcollection_strategy(db, admin)
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_overcollection_strategy_rejects_invalid_value() -> None:
    with pytest.raises(ValidationError):
        OvercollectionStrategyUpdate(strategy="INVALID")
