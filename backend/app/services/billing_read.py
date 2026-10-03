"""Read-only customer billing catalog and organization billing state."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.billing import BillingSettings, Plan, Subscription
from app.models.billing_checkout import BillingCheckoutSession
from app.models.user import Organization


def get_active_billing_catalog(db: Session) -> dict[str, Any]:
    """Return active customer plans and their pricing tiers."""
    plans = (
        db.query(Plan)
        .filter(Plan.is_active.is_(True))
        .order_by(Plan.id.asc())
        .all()
    )

    return {
        "plans": [
            {
                "id": plan.id,
                "code": plan.code,
                "name": plan.name,
                "description": plan.description,
                "pricing_tiers": [
                    {
                        "id": tier.id,
                        "min_properties": tier.min_properties,
                        "max_properties": tier.max_properties,
                        "monthly_price_cents": tier.monthly_price_cents,
                        "currency": tier.currency,
                    }
                    for tier in sorted(
                        plan.pricing_tiers,
                        key=lambda tier: (tier.min_properties, tier.id),
                    )
                ],
            }
            for plan in plans
        ]
    }


def get_organization_billing_state(
    db: Session,
    *,
    organization_id: int,
) -> dict[str, Any]:
    """Return safe customer-facing billing state for one organization.

    Provider identifiers and idempotency keys are deliberately excluded.
    """
    organization = db.get(Organization, organization_id)
    if organization is None:
        raise ValueError("Organization not found")

    billing_settings = (
        db.query(BillingSettings)
        .filter(BillingSettings.organization_id == organization_id)
        .first()
    )
    subscription = (
        db.query(Subscription)
        .filter(Subscription.organization_id == organization_id)
        .first()
    )
    latest_checkout = (
        db.query(BillingCheckoutSession)
        .filter(BillingCheckoutSession.organization_id == organization_id)
        .order_by(
            BillingCheckoutSession.created_at.desc(),
            BillingCheckoutSession.id.desc(),
        )
        .first()
    )

    settings_payload = None
    if billing_settings is not None:
        settings_payload = {
            "billing_email": billing_settings.billing_email,
            "currency": billing_settings.currency,
            "has_provider_customer": bool(billing_settings.stripe_customer_id),
        }

    subscription_payload = None
    if subscription is not None:
        subscription_payload = {
            "subscription_id": subscription.id,
            "plan_id": subscription.plan_id,
            "plan_code": subscription.plan.code,
            "plan_name": subscription.plan.name,
            "status": (
                subscription.status.value
                if hasattr(subscription.status, "value")
                else str(subscription.status)
            ),
            "current_period_start": subscription.current_period_start,
            "current_period_end": subscription.current_period_end,
            "cancel_at_period_end": bool(subscription.cancel_at_period_end),
        }

    checkout_payload = None
    if latest_checkout is not None:
        checkout_payload = {
            "attempt_id": latest_checkout.id,
            "plan_id": latest_checkout.plan_id,
            "pricing_tier_id": latest_checkout.pricing_tier_id,
            "status": (
                latest_checkout.status.value
                if hasattr(latest_checkout.status, "value")
                else str(latest_checkout.status)
            ),
            "url": latest_checkout.checkout_url,
            "created_at": latest_checkout.created_at,
            "updated_at": latest_checkout.updated_at,
        }

    return {
        "organization_state": organization.state,
        "billing_settings": settings_payload,
        "subscription": subscription_payload,
        "latest_checkout": checkout_payload,
    }
