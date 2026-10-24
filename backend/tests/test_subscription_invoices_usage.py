from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.billing import (
    Plan,
    Subscription,
    SubscriptionItem,
    Module,
)
from app.models.subscription_billing import (
    SubscriptionInvoice,
    SubscriptionInvoiceStatus,
    UsageRecord,
)
from app.models.user import Organization


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def _seed_subscription(db):
    org = Organization(name="Example", slug="invoice-usage-org")
    plan = Plan(code="invoice-usage-plan", name="Plan")
    db.add_all([org, plan])
    db.flush()
    subscription = Subscription(
        organization_id=org.id,
        plan_id=plan.id,
    )
    db.add(subscription)
    db.flush()
    return subscription


def test_invoice_defaults_are_safe() -> None:
    db, engine = _session()
    try:
        subscription = _seed_subscription(db)
        invoice = SubscriptionInvoice(subscription_id=subscription.id)
        db.add(invoice)
        db.commit()
        db.refresh(invoice)

        assert invoice.status == SubscriptionInvoiceStatus.DRAFT
        assert invoice.currency == "USD"
        assert invoice.total_cents == 0
        assert invoice.amount_due_cents == 0
    finally:
        db.close()
        engine.dispose()


def test_invoice_rejects_negative_amounts() -> None:
    db, engine = _session()
    try:
        subscription = _seed_subscription(db)
        db.add(
            SubscriptionInvoice(
                subscription_id=subscription.id,
                total_cents=-1,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()


def test_invoice_period_cannot_end_before_it_starts() -> None:
    db, engine = _session()
    try:
        subscription = _seed_subscription(db)
        start = datetime.utcnow()
        db.add(
            SubscriptionInvoice(
                subscription_id=subscription.id,
                period_start=start,
                period_end=start - timedelta(days=1),
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()


def test_provider_invoice_id_is_unique() -> None:
    db, engine = _session()
    try:
        subscription = _seed_subscription(db)
        db.add(
            SubscriptionInvoice(
                subscription_id=subscription.id,
                provider_invoice_id="in_unique_1",
            )
        )
        db.commit()

        db.add(
            SubscriptionInvoice(
                subscription_id=subscription.id,
                provider_invoice_id="in_unique_1",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()


def test_usage_constraints_and_provider_id_uniqueness() -> None:
    db, engine = _session()
    try:
        subscription = _seed_subscription(db)
        module = Module(key="usage-module", name="Usage Module")
        db.add(module)
        db.flush()
        item = SubscriptionItem(
            subscription_id=subscription.id,
            module_id=module.id,
        )
        db.add(item)
        db.flush()

        record = UsageRecord(
            subscription_id=subscription.id,
            subscription_item_id=item.id,
            metric_key="properties",
            quantity=3,
            provider_usage_id="usage_unique_1",
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        assert record.quantity == 3

        db.add(
            UsageRecord(
                subscription_id=subscription.id,
                metric_key="properties",
                quantity=-1,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        db.add(
            UsageRecord(
                subscription_id=subscription.id,
                metric_key="properties",
                quantity=1,
                provider_usage_id="usage_unique_1",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()
