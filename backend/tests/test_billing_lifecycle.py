from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.billing import Plan, Subscription, SubscriptionEvent, SubscriptionStatus
from app.models.user import Organization
from app.services.billing_lifecycle import (
    InvalidSubscriptionTransition,
    set_cancel_at_period_end,
    transition_subscription,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def _subscription(db):
    org = Organization(name="Lifecycle Org", slug="lifecycle-org")
    plan = Plan(code="lifecycle-plan", name="Lifecycle Plan")
    db.add_all([org, plan])
    db.commit()
    subscription = Subscription(
        organization_id=org.id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
    )
    db.add(subscription)
    db.commit()
    return subscription


def test_valid_transition_changes_status_and_appends_event_atomically() -> None:
    db, engine = _session()
    try:
        subscription = _subscription(db)
        event = transition_subscription(
            db,
            subscription=subscription,
            target_status=SubscriptionStatus.PAST_DUE,
            provider="stripe",
            provider_event_id="evt-1",
            payload={"reason": "invoice_failed"},
        )
        assert event is not None
        assert subscription.status == SubscriptionStatus.PAST_DUE
        assert event.payload["from_status"] == "ACTIVE"
        assert event.payload["to_status"] == "PAST_DUE"
        assert event.payload["reason"] == "invoice_failed"
        db.commit()
        assert db.query(SubscriptionEvent).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_invalid_transition_does_not_mutate_or_append_event() -> None:
    db, engine = _session()
    try:
        subscription = _subscription(db)
        with pytest.raises(InvalidSubscriptionTransition):
            transition_subscription(
                db,
                subscription=subscription,
                target_status=SubscriptionStatus.SUSPENDED,
            )
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert db.query(SubscriptionEvent).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_duplicate_provider_event_is_idempotent() -> None:
    db, engine = _session()
    try:
        subscription = _subscription(db)
        first = transition_subscription(
            db,
            subscription=subscription,
            target_status=SubscriptionStatus.PAST_DUE,
            provider="stripe",
            provider_event_id="evt-dupe",
        )
        db.commit()
        second = transition_subscription(
            db,
            subscription=subscription,
            target_status=SubscriptionStatus.RESTRICTED,
            provider="stripe",
            provider_event_id="evt-dupe",
        )
        assert second is not None
        assert first is not None
        assert second.id == first.id
        assert subscription.status == SubscriptionStatus.PAST_DUE
        assert db.query(SubscriptionEvent).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_cancel_at_period_end_is_audited_and_idempotent() -> None:
    db, engine = _session()
    try:
        subscription = _subscription(db)
        event = set_cancel_at_period_end(
            db,
            subscription=subscription,
            enabled=True,
            provider="stripe",
            provider_event_id="evt-cancel",
        )
        assert event is not None
        assert subscription.cancel_at_period_end is True
        db.commit()

        duplicate = set_cancel_at_period_end(
            db,
            subscription=subscription,
            enabled=True,
            provider="stripe",
            provider_event_id="evt-cancel",
        )
        assert duplicate is None
        assert db.query(SubscriptionEvent).count() == 1
    finally:
        db.close()
        engine.dispose()
