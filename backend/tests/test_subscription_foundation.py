from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.billing import Plan, Subscription, SubscriptionStatus
from app.models.user import Organization


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def test_subscription_status_contract_matches_lifecycle() -> None:
    assert [status.value for status in SubscriptionStatus] == [
        "ACTIVE",
        "PAST_DUE",
        "RESTRICTED",
        "SUSPENDED",
        "CANCELLED",
    ]


def test_subscription_defaults_active_and_not_canceling() -> None:
    db, engine = _session()
    try:
        org = Organization(name="Example", slug="subscription-default")
        plan = Plan(code="starter", name="Starter")
        db.add_all([org, plan])
        db.commit()

        subscription = Subscription(organization_id=org.id, plan_id=plan.id)
        db.add(subscription)
        db.commit()
        db.refresh(subscription)

        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.cancel_at_period_end is False
    finally:
        db.close()
        engine.dispose()


def test_one_current_subscription_per_organization() -> None:
    db, engine = _session()
    try:
        org = Organization(name="Example", slug="subscription-unique")
        starter = Plan(code="starter-unique", name="Starter")
        pro = Plan(code="pro-unique", name="Pro")
        db.add_all([org, starter, pro])
        db.commit()

        db.add(Subscription(organization_id=org.id, plan_id=starter.id))
        db.commit()
        db.add(Subscription(organization_id=org.id, plan_id=pro.id))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()


def test_subscription_period_cannot_end_before_it_starts() -> None:
    db, engine = _session()
    try:
        org = Organization(name="Example", slug="subscription-period")
        plan = Plan(code="period-plan", name="Period")
        db.add_all([org, plan])
        db.commit()

        start = datetime.utcnow()
        db.add(
            Subscription(
                organization_id=org.id,
                plan_id=plan.id,
                current_period_start=start,
                current_period_end=start - timedelta(days=1),
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()


def test_subscription_plan_relationship_resolves() -> None:
    db, engine = _session()
    try:
        org = Organization(name="Example", slug="subscription-relation")
        plan = Plan(code="relationship-plan", name="Relationship")
        subscription = Subscription(organization=org, plan=plan)
        db.add(subscription)
        db.commit()
        db.refresh(subscription)

        assert subscription.plan.code == "relationship-plan"
        assert plan.subscriptions[0].organization_id == org.id
    finally:
        db.close()
        engine.dispose()
