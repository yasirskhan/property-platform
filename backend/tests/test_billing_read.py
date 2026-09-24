from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.billing import (
    BillingSettings,
    Plan,
    PricingTier,
    Subscription,
    SubscriptionStatus,
)
from app.models.billing_checkout import BillingCheckoutSession, BillingCheckoutStatus
from app.models.user import Organization, User, UserRole
from app.routers.billing_checkout import read_billing_catalog, read_billing_state
from app.services.billing_read import (
    get_active_billing_catalog,
    get_organization_billing_state,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def _user(
    db,
    org: Organization,
    *,
    email: str,
    role: UserRole = UserRole.ADMIN,
) -> User:
    user = User(
        email=email,
        hashed_password="x",
        first_name="Billing",
        last_name="User",
        role=role,
        organization_id=org.id,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def test_active_billing_catalog_returns_only_active_plans_with_sorted_tiers() -> None:
    db, engine = _session()
    try:
        active = Plan(
            code="active",
            name="Active",
            description="Available plan",
            is_active=True,
        )
        inactive = Plan(
            code="inactive",
            name="Inactive",
            is_active=False,
        )
        db.add_all([active, inactive])
        db.flush()
        upper = PricingTier(
            plan_id=active.id,
            min_properties=11,
            max_properties=50,
            monthly_price_cents=9900,
            currency="USD",
        )
        lower = PricingTier(
            plan_id=active.id,
            min_properties=1,
            max_properties=10,
            monthly_price_cents=4900,
            currency="USD",
        )
        hidden = PricingTier(
            plan_id=inactive.id,
            min_properties=1,
            max_properties=None,
            monthly_price_cents=100,
            currency="USD",
        )
        db.add_all([upper, lower, hidden])
        db.commit()

        result = get_active_billing_catalog(db)

        assert [plan["code"] for plan in result["plans"]] == ["active"]
        assert [
            tier["id"] for tier in result["plans"][0]["pricing_tiers"]
        ] == [lower.id, upper.id]
    finally:
        db.close()
        engine.dispose()


def test_billing_state_is_org_scoped_and_hides_provider_identifiers() -> None:
    db, engine = _session()
    try:
        org = Organization(name="Own Org", slug="own-billing")
        other = Organization(name="Other Org", slug="other-billing")
        plan = Plan(code="growth", name="Growth")
        db.add_all([org, other, plan])
        db.flush()
        tier = PricingTier(
            plan_id=plan.id,
            min_properties=1,
            max_properties=25,
            monthly_price_cents=7900,
            currency="USD",
        )
        db.add(tier)
        db.flush()

        db.add(
            BillingSettings(
                organization_id=org.id,
                stripe_customer_id="cus_secret_own",
                billing_email="billing@own.example",
                currency="USD",
            )
        )
        own_subscription = Subscription(
            organization_id=org.id,
            plan_id=plan.id,
            stripe_subscription_id="sub_secret_own",
            status=SubscriptionStatus.ACTIVE,
            cancel_at_period_end=True,
        )
        db.add(own_subscription)
        db.flush()

        older = BillingCheckoutSession(
            organization_id=org.id,
            plan_id=plan.id,
            pricing_tier_id=tier.id,
            idempotency_key="older-checkout-key-0001",
            provider_session_id="cs_secret_old",
            checkout_url="https://checkout.example/old",
            status=BillingCheckoutStatus.EXPIRED,
            created_at=datetime.utcnow() - timedelta(days=1),
        )
        latest = BillingCheckoutSession(
            organization_id=org.id,
            plan_id=plan.id,
            pricing_tier_id=tier.id,
            idempotency_key="latest-checkout-key-0002",
            provider_session_id="cs_secret_latest",
            checkout_url="https://checkout.example/latest",
            status=BillingCheckoutStatus.CREATED,
            created_at=datetime.utcnow(),
        )
        other_checkout = BillingCheckoutSession(
            organization_id=other.id,
            plan_id=plan.id,
            pricing_tier_id=tier.id,
            idempotency_key="other-checkout-key-0003",
            provider_session_id="cs_secret_other",
            checkout_url="https://checkout.example/other",
            status=BillingCheckoutStatus.CREATED,
        )
        db.add_all([older, latest, other_checkout])
        db.commit()

        result = get_organization_billing_state(
            db,
            organization_id=org.id,
        )

        assert result["billing_settings"] == {
            "billing_email": "billing@own.example",
            "currency": "USD",
            "has_provider_customer": True,
        }
        assert result["subscription"]["subscription_id"] == own_subscription.id
        assert result["subscription"]["plan_code"] == "growth"
        assert result["subscription"]["status"] == "ACTIVE"
        assert result["latest_checkout"]["attempt_id"] == latest.id
        assert result["latest_checkout"]["url"] == "https://checkout.example/latest"

        serialized = repr(result)
        assert "cus_secret_own" not in serialized
        assert "sub_secret_own" not in serialized
        assert "cs_secret_latest" not in serialized
        assert "latest-checkout-key-0002" not in serialized
        assert "https://checkout.example/other" not in serialized
    finally:
        db.close()
        engine.dispose()


def test_billing_read_routes_allow_admin_and_owner_only() -> None:
    db, engine = _session()
    try:
        org = Organization(name="Roles Org", slug="roles-billing")
        db.add(org)
        db.flush()
        admin = _user(
            db,
            org,
            email="admin-billing@example.com",
            role=UserRole.ADMIN,
        )
        owner = _user(
            db,
            org,
            email="owner-billing@example.com",
            role=UserRole.OWNER,
        )
        manager = _user(
            db,
            org,
            email="manager-billing@example.com",
            role=UserRole.MANAGER,
        )
        db.commit()

        assert read_billing_catalog(db, admin) == {"plans": []}
        assert read_billing_state(db, owner) == {
            "billing_settings": None,
            "subscription": None,
            "latest_checkout": None,
        }

        with pytest.raises(HTTPException) as exc:
            read_billing_catalog(db, manager)
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_billing_read_routes_require_customer_organization() -> None:
    db, engine = _session()
    try:
        user = User(
            email="orphan-billing@example.com",
            hashed_password="x",
            first_name="Orphan",
            last_name="Admin",
            role=UserRole.ADMIN,
            organization_id=None,
            is_active=True,
        )

        with pytest.raises(HTTPException) as exc:
            read_billing_state(db, user)
        assert exc.value.status_code == 400
    finally:
        db.close()
        engine.dispose()
