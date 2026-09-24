from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.billing import (
    Module,
    Plan,
    Subscription,
    SubscriptionEvent,
    SubscriptionItem,
)
from app.models.user import Organization


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def _seed(db):
    org = Organization(name="Example", slug="subscription-item-event")
    plan = Plan(code="item-event-plan", name="Plan")
    module = Module(key="item-event-module", name="Module")
    db.add_all([org, plan, module])
    db.flush()
    subscription = Subscription(
        organization_id=org.id,
        plan_id=plan.id,
    )
    db.add(subscription)
    db.commit()
    return subscription, module


def test_subscription_item_defaults_and_prevents_duplicate_module() -> None:
    db, engine = _session()
    try:
        subscription, module = _seed(db)
        item = SubscriptionItem(
            subscription_id=subscription.id,
            module_id=module.id,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        assert item.quantity == 1

        db.add(
            SubscriptionItem(
                subscription_id=subscription.id,
                module_id=module.id,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()


def test_subscription_item_rejects_invalid_quantity_and_price() -> None:
    db, engine = _session()
    try:
        subscription, module = _seed(db)
        db.add(
            SubscriptionItem(
                subscription_id=subscription.id,
                module_id=module.id,
                quantity=0,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        db.add(
            SubscriptionItem(
                subscription_id=subscription.id,
                module_id=module.id,
                unit_price_cents=-1,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()


def test_subscription_event_round_trips_payload_and_provider_id_is_unique() -> None:
    db, engine = _session()
    try:
        subscription, _ = _seed(db)
        event = SubscriptionEvent(
            subscription_id=subscription.id,
            event_type="created",
            provider="stripe",
            provider_event_id="evt_unique_1",
            payload={"source": "test"},
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        assert event.payload == {"source": "test"}

        db.add(
            SubscriptionEvent(
                subscription_id=subscription.id,
                event_type="duplicate",
                provider_event_id="evt_unique_1",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()


def test_subscription_event_update_is_rejected() -> None:
    db, engine = _session()
    try:
        subscription, _ = _seed(db)
        event = SubscriptionEvent(
            subscription_id=subscription.id,
            event_type="created",
        )
        db.add(event)
        db.commit()

        event.event_type = "changed"
        with pytest.raises(RuntimeError, match="append-only"):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()


def test_subscription_event_delete_is_rejected() -> None:
    db, engine = _session()
    try:
        subscription, _ = _seed(db)
        event = SubscriptionEvent(
            subscription_id=subscription.id,
            event_type="created",
        )
        db.add(event)
        db.commit()

        db.delete(event)
        with pytest.raises(RuntimeError, match="append-only"):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()
