from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.core.security import hash_password
from app.models.billing import BillingSettings, Plan, PricingTier
from app.models.billing_checkout import BillingCheckoutSession, BillingCheckoutStatus
from app.models.fraud import FraudCase, FraudCaseStatus, FraudRiskLevel, FraudSignal
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.user import Organization, User, UserRole
from app.routers.platform_fraud import list_fraud_cases, review_fraud_case
from app.schemas.fraud import FraudCaseReviewIn
from app.services.fraud import (
    FraudCheckoutBlocked,
    assess_checkout_velocity,
    process_stripe_fraud_event,
)
from app.services.stripe_billing import create_checkout_session


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def _catalog(db):
    org = Organization(name="Fraud Org", slug="fraud-org", state="PENDING_BILLING")
    user = User(
        email="fraud-buyer@example.com",
        hashed_password="x",
        first_name="Fraud",
        last_name="Buyer",
        role=UserRole.ADMIN,
        organization=org,
    )
    plan = Plan(code="fraud-plan", name="Fraud Plan", is_active=True)
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


def _platform_user(db, role: PlatformUserRole) -> PlatformUser:
    user = PlatformUser(
        email=f"{role.value}-fraud@example.com",
        hashed_password=hash_password("test-platform-password"),
        first_name="Platform",
        last_name="Reviewer",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_checkout_velocity_opens_one_review_case_and_escalates() -> None:
    db, engine = _session()
    try:
        org, user, plan, tier = _catalog(db)
        now = datetime.utcnow().replace(minute=15, second=0, microsecond=0)
        for idx in range(8):
            db.add(
                BillingCheckoutSession(
                    organization_id=org.id,
                    plan_id=plan.id,
                    pricing_tier_id=tier.id,
                    requested_by_user_id=user.id,
                    idempotency_key=f"velocity-key-{idx:02d}-abcdefghijklmnop",
                    status=BillingCheckoutStatus.CREATED,
                    created_at=now - timedelta(minutes=idx),
                    updated_at=now - timedelta(minutes=idx),
                )
            )
        db.commit()

        case = assess_checkout_velocity(db, organization_id=org.id, now=now)
        db.commit()
        assert case is not None
        assert case.status == FraudCaseStatus.OPEN
        assert case.risk_level == FraudRiskLevel.CRITICAL
        assert case.risk_score == 95
        assert db.query(FraudCase).count() == 1
        assert db.query(FraudSignal).count() == 1

        same = assess_checkout_velocity(db, organization_id=org.id, now=now)
        db.commit()
        assert same is not None
        assert same.id == case.id
        assert db.query(FraudCase).count() == 1
        assert db.query(FraudSignal).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_stripe_radar_event_is_idempotent_and_links_customer_org() -> None:
    db, engine = _session()
    try:
        org, _user, _plan, _tier = _catalog(db)
        db.add(
            BillingSettings(
                organization_id=org.id,
                stripe_customer_id="cus_risk_123",
                billing_email="billing@example.com",
                currency="USD",
            )
        )
        db.commit()

        event = {
            "id": "evt_review_opened_123",
            "type": "review.opened",
            "data": {
                "object": {
                    "id": "prv_123",
                    "opened_reason": "rule",
                    "charge": {
                        "id": "ch_123",
                        "customer": "cus_risk_123",
                        "metadata": {},
                    },
                }
            },
        }

        assert process_stripe_fraud_event(db, event) == "processed"
        db.commit()
        case = db.query(FraudCase).one()
        assert case.organization_id == org.id
        assert case.provider == "stripe"
        assert case.provider_case_id == "prv_123"
        assert case.status == FraudCaseStatus.OPEN
        assert case.risk_level == FraudRiskLevel.HIGH
        assert db.query(FraudSignal).count() == 1

        assert process_stripe_fraud_event(db, event) == "duplicate"
        db.commit()
        assert db.query(FraudCase).count() == 1
        assert db.query(FraudSignal).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_nonfraud_dispute_is_not_added_to_review_queue() -> None:
    db, engine = _session()
    try:
        event = {
            "id": "evt_dispute_nonfraud",
            "type": "charge.dispute.created",
            "data": {
                "object": {
                    "id": "dp_nonfraud",
                    "reason": "product_not_received",
                    "status": "needs_response",
                }
            },
        }
        assert process_stripe_fraud_event(db, event) == "ignored_nonfraud_dispute"
        assert db.query(FraudCase).count() == 0
        assert db.query(FraudSignal).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_critical_open_case_blocks_new_checkout_before_stripe(monkeypatch) -> None:
    db, engine = _session()
    calls = []
    monkeypatch.setattr("app.core.config.settings.STRIPE_ENABLED", True)
    monkeypatch.setattr("app.core.config.settings.STRIPE_SECRET_KEY", "sk_test_example")
    try:
        org, user, _plan, tier = _catalog(db)
        db.add(
            FraudCase(
                organization_id=org.id,
                provider="internal",
                provider_case_id="critical-block",
                status=FraudCaseStatus.OPEN,
                risk_level=FraudRiskLevel.CRITICAL,
                risk_score=99,
                reason="Critical test signal",
                details={},
            )
        )
        db.commit()

        monkeypatch.setattr(
            "app.services.stripe_billing.stripe.checkout.Session.create",
            lambda **kwargs: calls.append(kwargs),
        )
        with pytest.raises(FraudCheckoutBlocked):
            create_checkout_session(
                db,
                organization_id=org.id,
                pricing_tier_id=tier.id,
                billing_email=user.email,
                requested_by_user_id=user.id,
                idempotency_key="blocked-checkout-key-123456789",
            )
        assert calls == []
        assert db.query(BillingCheckoutSession).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_platform_billing_can_review_case_and_sales_cannot_view() -> None:
    db, engine = _session()
    try:
        org, _user, _plan, _tier = _catalog(db)
        reviewer = _platform_user(db, PlatformUserRole.PLATFORM_BILLING)
        sales = _platform_user(db, PlatformUserRole.PLATFORM_SALES)
        case = FraudCase(
            organization_id=org.id,
            provider="stripe",
            provider_case_id="prv_review_me",
            status=FraudCaseStatus.OPEN,
            risk_level=FraudRiskLevel.HIGH,
            risk_score=80,
            reason="Review me",
            details={},
        )
        db.add(case)
        db.commit()
        db.refresh(case)

        reviewed = review_fraud_case(
            case.id,
            FraudCaseReviewIn(
                status=FraudCaseStatus.APPROVED,
                resolution_notes="Verified legitimate customer",
            ),
            db=db,
            current_user=reviewer,
        )
        assert reviewed.status == FraudCaseStatus.APPROVED
        assert reviewed.reviewed_by_platform_user_id == reviewer.id
        assert reviewed.resolved_at is not None

        with pytest.raises(HTTPException) as exc:
            list_fraud_cases(
                case_status=None,
                risk_level=None,
                organization_id=None,
                limit=100,
                db=db,
                current_user=sales,
            )
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()
