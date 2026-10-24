from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base
from app.models.billing import (
    BillingSettings,
    Plan,
    PricingTier,
    Subscription,
    SubscriptionEvent,
    SubscriptionStatus,
)
from app.models.billing_checkout import BillingCheckoutSession, BillingCheckoutStatus
from app.models.user import Organization, User, UserRole
from app.services.stripe_billing import (
    CheckoutIdempotencyConflict,
    create_checkout_session,
    process_stripe_event,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def _catalog(db):
    org = Organization(name="Checkout Org", slug="checkout-org")
    user = User(
        email="billing@example.com",
        hashed_password="x",
        first_name="Billing",
        last_name="Admin",
        role=UserRole.ADMIN,
        organization=org,
    )
    plan = Plan(code="checkout-plan", name="Checkout Plan", description="Monthly plan")
    db.add_all([org, user, plan])
    db.flush()
    tier = PricingTier(
        plan_id=plan.id,
        min_properties=1,
        max_properties=10,
        monthly_price_cents=4900,
        currency="USD",
    )
    db.add(tier)
    db.commit()
    return org, user, plan, tier


@pytest.fixture
def stripe_enabled(monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_ENABLED", True)
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_example")
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_example")
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:3000")


def test_checkout_session_is_db_and_provider_idempotent(monkeypatch, stripe_enabled) -> None:
    db, engine = _session()
    calls = []

    class FakeSession:
        id = "cs_test_123"
        url = "https://checkout.stripe.test/session"

    def fake_create(**kwargs):
        calls.append(kwargs)
        return FakeSession()

    monkeypatch.setattr("app.services.stripe_billing.stripe.checkout.Session.create", fake_create)

    try:
        org, user, _plan, tier = _catalog(db)
        key = "11111111-2222-4333-8444-555555555555"
        first = create_checkout_session(
            db,
            organization_id=org.id,
            pricing_tier_id=tier.id,
            billing_email=user.email,
            requested_by_user_id=user.id,
            idempotency_key=key,
        )
        second = create_checkout_session(
            db,
            organization_id=org.id,
            pricing_tier_id=tier.id,
            billing_email=user.email,
            requested_by_user_id=user.id,
            idempotency_key=key,
        )

        assert first == second
        assert len(calls) == 1
        assert calls[0]["idempotency_key"] == f"billing-checkout:{org.id}:{key}"
        assert calls[0]["mode"] == "subscription"
        assert calls[0]["line_items"][0]["price_data"]["unit_amount"] == 4900
        assert db.query(BillingCheckoutSession).count() == 1
        attempt = db.query(BillingCheckoutSession).one()
        assert attempt.status == BillingCheckoutStatus.CREATED
        assert db.query(BillingSettings).one().billing_email == user.email
    finally:
        db.close()
        engine.dispose()


def test_checkout_idempotency_key_reuse_with_different_tier_is_rejected(
    monkeypatch,
    stripe_enabled,
) -> None:
    db, engine = _session()

    class FakeSession:
        id = "cs_test_456"
        url = "https://checkout.stripe.test/session-456"

    monkeypatch.setattr(
        "app.services.stripe_billing.stripe.checkout.Session.create",
        lambda **_kwargs: FakeSession(),
    )

    try:
        org, user, plan, tier = _catalog(db)
        other_tier = PricingTier(
            plan_id=plan.id,
            min_properties=11,
            max_properties=50,
            monthly_price_cents=9900,
            currency="USD",
        )
        db.add(other_tier)
        db.commit()
        key = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"

        create_checkout_session(
            db,
            organization_id=org.id,
            pricing_tier_id=tier.id,
            billing_email=user.email,
            requested_by_user_id=user.id,
            idempotency_key=key,
        )

        with pytest.raises(CheckoutIdempotencyConflict):
            create_checkout_session(
                db,
                organization_id=org.id,
                pricing_tier_id=other_tier.id,
                billing_email=user.email,
                requested_by_user_id=user.id,
                idempotency_key=key,
            )
    finally:
        db.close()
        engine.dispose()


def test_checkout_completed_reconciles_customer_subscription_and_is_idempotent(
    stripe_enabled,
) -> None:
    db, engine = _session()
    try:
        org, user, plan, tier = _catalog(db)
        org.state = "PENDING_BILLING"
        attempt = BillingCheckoutSession(
            organization_id=org.id,
            plan_id=plan.id,
            pricing_tier_id=tier.id,
            requested_by_user_id=user.id,
            idempotency_key="checkout-complete-key-123",
            provider_session_id="cs_complete_123",
            checkout_url="https://checkout.stripe.test/complete",
            status=BillingCheckoutStatus.CREATED,
        )
        db.add(attempt)
        db.commit()

        event = {
            "id": "evt_checkout_complete",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_complete_123",
                    "customer": "cus_123",
                    "subscription": "sub_123",
                }
            },
        }

        assert process_stripe_event(db, event) == "processed"
        db.commit()

        billing_settings = db.query(BillingSettings).one()
        subscription = db.query(Subscription).one()
        attempt = db.query(BillingCheckoutSession).one()
        assert billing_settings.stripe_customer_id == "cus_123"
        assert subscription.stripe_subscription_id == "sub_123"
        assert subscription.plan_id == plan.id
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert attempt.status == BillingCheckoutStatus.COMPLETED
        assert db.query(SubscriptionEvent).count() == 1
        assert org.state == "ACTIVE"

        assert process_stripe_event(db, event) == "duplicate"
        db.commit()
        assert db.query(SubscriptionEvent).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_subscription_and_invoice_webhooks_update_lifecycle_with_new_stripe_shapes(
    stripe_enabled,
) -> None:
    db, engine = _session()
    try:
        org, _user, plan, _tier = _catalog(db)
        subscription = Subscription(
            organization_id=org.id,
            plan_id=plan.id,
            stripe_subscription_id="sub_periods",
            status=SubscriptionStatus.ACTIVE,
        )
        db.add(subscription)
        db.commit()

        updated = {
            "id": "evt_sub_updated",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_periods",
                    "status": "past_due",
                    "cancel_at_period_end": True,
                    "items": {
                        "data": [
                            {
                                "current_period_start": 1_700_000_000,
                                "current_period_end": 1_702_592_000,
                            }
                        ]
                    },
                }
            },
        }
        assert process_stripe_event(db, updated) == "processed"
        db.commit()
        db.refresh(subscription)
        assert subscription.status == SubscriptionStatus.PAST_DUE
        assert subscription.cancel_at_period_end is True
        assert subscription.current_period_start == datetime.utcfromtimestamp(1_700_000_000)
        assert subscription.current_period_end == datetime.utcfromtimestamp(1_702_592_000)

        paid = {
            "id": "evt_invoice_paid",
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": "in_123",
                    "status": "paid",
                    "amount_paid": 4900,
                    "amount_due": 0,
                    "currency": "usd",
                    "parent": {
                        "subscription_details": {
                            "subscription": "sub_periods"
                        }
                    },
                }
            },
        }
        assert process_stripe_event(db, paid) == "processed"
        db.commit()
        db.refresh(subscription)
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert db.query(SubscriptionEvent).count() == 2
        assert org.state == "ACTIVE"
    finally:
        db.close()
        engine.dispose()
