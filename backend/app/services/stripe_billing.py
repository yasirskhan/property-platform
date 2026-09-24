"""Stripe Checkout creation and signed webhook reconciliation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import stripe
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.billing import (
    BillingSettings,
    Plan,
    PricingTier,
    Subscription,
    SubscriptionEvent,
    SubscriptionStatus,
)
from app.models.billing_checkout import BillingCheckoutSession, BillingCheckoutStatus
from app.models.user import Organization
from app.services.fraud import (
    assess_checkout_velocity,
    process_stripe_fraud_event,
    require_checkout_not_blocked,
)
from app.services.billing_lifecycle import InvalidSubscriptionTransition, transition_subscription


class StripeBillingUnavailable(RuntimeError):
    """Raised when Stripe billing is disabled or not configured."""


class CheckoutIdempotencyConflict(ValueError):
    """Raised when an idempotency key is reused for different checkout input."""


class StripeProviderError(RuntimeError):
    """Raised when Stripe rejects or cannot complete a provider request."""


class InvalidStripeWebhook(ValueError):
    """Raised when a Stripe webhook signature cannot be verified."""


class BillingWebhookIntegrityError(RuntimeError):
    """Raised when a signed webhook conflicts with local billing identity."""


def _require_stripe_enabled(*, require_webhook_secret: bool = False) -> None:
    if not settings.STRIPE_ENABLED:
        raise StripeBillingUnavailable("Stripe billing is disabled")
    if not settings.STRIPE_SECRET_KEY.strip():
        raise StripeBillingUnavailable("Stripe secret key is not configured")
    if require_webhook_secret and not settings.STRIPE_WEBHOOK_SECRET.strip():
        raise StripeBillingUnavailable("Stripe webhook secret is not configured")


def _provider_idempotency_key(organization_id: int, client_key: str) -> str:
    return f"billing-checkout:{organization_id}:{client_key}"


def _value(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _stripe_id(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    object_id = _value(value, "id")
    return str(object_id) if object_id else None


def _utc_from_epoch(value: Any) -> datetime | None:
    if value is None:
        return None
    return datetime.utcfromtimestamp(int(value))


def _subscription_period(subscription_object: Any) -> tuple[datetime | None, datetime | None]:
    items = _value(_value(subscription_object, "items"), "data", []) or []
    starts = [
        _utc_from_epoch(_value(item, "current_period_start"))
        for item in items
        if _value(item, "current_period_start") is not None
    ]
    ends = [
        _utc_from_epoch(_value(item, "current_period_end"))
        for item in items
        if _value(item, "current_period_end") is not None
    ]
    starts = [value for value in starts if value is not None]
    ends = [value for value in ends if value is not None]
    return (min(starts) if starts else None, max(ends) if ends else None)


def _invoice_subscription_id(invoice_object: Any) -> str | None:
    direct = _stripe_id(_value(invoice_object, "subscription"))
    if direct:
        return direct
    parent = _value(invoice_object, "parent")
    subscription_details = _value(parent, "subscription_details")
    return _stripe_id(_value(subscription_details, "subscription"))


def _event_already_processed(db: Session, event_id: str | None) -> bool:
    if not event_id:
        return False
    return (
        db.query(SubscriptionEvent)
        .filter(SubscriptionEvent.provider_event_id == event_id)
        .first()
        is not None
    )


def _append_subscription_event(
    db: Session,
    *,
    subscription: Subscription,
    event_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> SubscriptionEvent:
    event = SubscriptionEvent(
        subscription_id=subscription.id,
        event_type=event_type,
        provider="stripe",
        provider_event_id=event_id,
        payload=payload,
    )
    db.add(event)
    db.flush()
    return event


def create_checkout_session(
    db: Session,
    *,
    organization_id: int,
    pricing_tier_id: int,
    billing_email: str,
    requested_by_user_id: int | None,
    idempotency_key: str,
) -> dict[str, Any]:
    """Create or safely resume one hosted Stripe Checkout Session.

    The attempt row is committed before the external provider call. Repeating
    the same organization/idempotency key either returns the saved session or
    retries Stripe with the exact same provider idempotency key.
    """
    _require_stripe_enabled()
    require_checkout_not_blocked(db, organization_id=organization_id)

    tier = (
        db.query(PricingTier)
        .join(Plan, Plan.id == PricingTier.plan_id)
        .filter(
            PricingTier.id == pricing_tier_id,
            Plan.is_active.is_(True),
        )
        .first()
    )
    if tier is None:
        raise ValueError("Active pricing tier not found")
    plan = tier.plan

    attempt = (
        db.query(BillingCheckoutSession)
        .filter(
            BillingCheckoutSession.organization_id == organization_id,
            BillingCheckoutSession.idempotency_key == idempotency_key,
        )
        .first()
    )
    if attempt is not None:
        if attempt.pricing_tier_id != tier.id or attempt.plan_id != plan.id:
            raise CheckoutIdempotencyConflict(
                "Idempotency key was already used for different checkout input"
            )
        if (
            attempt.status in {
                BillingCheckoutStatus.CREATED,
                BillingCheckoutStatus.COMPLETED,
            }
            and attempt.provider_session_id
            and attempt.checkout_url
        ):
            return {
                "attempt_id": attempt.id,
                "session_id": attempt.provider_session_id,
                "url": attempt.checkout_url,
                "status": attempt.status.value,
            }
        attempt.status = BillingCheckoutStatus.PENDING
    else:
        attempt = BillingCheckoutSession(
            organization_id=organization_id,
            plan_id=plan.id,
            pricing_tier_id=tier.id,
            requested_by_user_id=requested_by_user_id,
            idempotency_key=idempotency_key,
            status=BillingCheckoutStatus.PENDING,
        )
        db.add(attempt)

    billing_settings = (
        db.query(BillingSettings)
        .filter(BillingSettings.organization_id == organization_id)
        .first()
    )
    if billing_settings is None:
        billing_settings = BillingSettings(
            organization_id=organization_id,
            billing_email=billing_email,
            currency=tier.currency.upper(),
        )
        db.add(billing_settings)
    elif not billing_settings.billing_email:
        billing_settings.billing_email = billing_email

    db.commit()
    db.refresh(attempt)
    db.refresh(billing_settings)
    assess_checkout_velocity(db, organization_id=organization_id)
    db.commit()

    metadata = {
        "organization_id": str(organization_id),
        "plan_id": str(plan.id),
        "pricing_tier_id": str(tier.id),
        "checkout_attempt_id": str(attempt.id),
    }
    if requested_by_user_id is not None:
        metadata["requested_by_user_id"] = str(requested_by_user_id)

    product_data: dict[str, Any] = {"name": plan.name}
    if plan.description:
        product_data["description"] = plan.description[:500]

    params: dict[str, Any] = {
        "mode": "subscription",
        "client_reference_id": str(organization_id),
        "line_items": [
            {
                "quantity": 1,
                "price_data": {
                    "currency": tier.currency.lower(),
                    "unit_amount": tier.monthly_price_cents,
                    "recurring": {"interval": "month"},
                    "product_data": product_data,
                },
            }
        ],
        "metadata": metadata,
        "subscription_data": {"metadata": metadata},
        "success_url": (
            f"{settings.FRONTEND_URL.rstrip('/')}/signup"
            "?checkout=success&session_id={CHECKOUT_SESSION_ID}"
        ),
        "cancel_url": f"{settings.FRONTEND_URL.rstrip('/')}/signup?checkout=cancelled",
    }
    if billing_settings.stripe_customer_id:
        params["customer"] = billing_settings.stripe_customer_id
    else:
        params["customer_email"] = billing_settings.billing_email or billing_email

    try:
        session = stripe.checkout.Session.create(
            **params,
            api_key=settings.STRIPE_SECRET_KEY,
            idempotency_key=_provider_idempotency_key(
                organization_id,
                idempotency_key,
            ),
        )
    except Exception as exc:
        attempt.status = BillingCheckoutStatus.FAILED
        db.commit()
        raise StripeProviderError("Stripe checkout session creation failed") from exc

    session_id = _stripe_id(session)
    checkout_url = _value(session, "url")
    if not session_id or not checkout_url:
        attempt.status = BillingCheckoutStatus.FAILED
        db.commit()
        raise StripeProviderError("Stripe returned an incomplete checkout session")

    attempt.provider_session_id = session_id
    attempt.checkout_url = str(checkout_url)
    attempt.status = BillingCheckoutStatus.CREATED
    db.commit()
    db.refresh(attempt)

    return {
        "attempt_id": attempt.id,
        "session_id": attempt.provider_session_id,
        "url": attempt.checkout_url,
        "status": attempt.status.value,
    }


def construct_stripe_event(payload: bytes, signature: str) -> Any:
    _require_stripe_enabled(require_webhook_secret=True)
    try:
        return stripe.Webhook.construct_event(
            payload,
            signature,
            settings.STRIPE_WEBHOOK_SECRET,
        )
    except Exception as exc:
        raise InvalidStripeWebhook("Invalid Stripe webhook signature") from exc


def _stripe_status_to_local(status_value: str | None) -> SubscriptionStatus | None:
    status_value = (status_value or "").lower()
    if status_value in {"active", "trialing"}:
        return SubscriptionStatus.ACTIVE
    if status_value in {"past_due", "unpaid"}:
        return SubscriptionStatus.PAST_DUE
    if status_value in {"canceled", "incomplete_expired"}:
        return SubscriptionStatus.CANCELLED
    return None


def _record_status_event(
    db: Session,
    *,
    subscription: Subscription,
    event_id: str,
    event_type: str,
    target_status: SubscriptionStatus | None,
    payload: dict[str, Any],
) -> None:
    current_status = SubscriptionStatus(subscription.status)
    if current_status == SubscriptionStatus.CANCELLED:
        target_status = None
    if current_status == SubscriptionStatus.SUSPENDED and target_status == SubscriptionStatus.PAST_DUE:
        target_status = None

    if target_status is not None and target_status != current_status:
        try:
            transition_subscription(
                db,
                subscription=subscription,
                target_status=target_status,
                event_type=event_type,
                provider="stripe",
                provider_event_id=event_id,
                payload=payload,
            )
            return
        except InvalidSubscriptionTransition as exc:
            raise BillingWebhookIntegrityError(str(exc)) from exc

    _append_subscription_event(
        db,
        subscription=subscription,
        event_id=event_id,
        event_type=event_type,
        payload=payload,
    )


def _process_checkout_completed(
    db: Session,
    *,
    event_id: str,
    event_type: str,
    session_object: Any,
) -> str:
    provider_session_id = _stripe_id(session_object)
    if not provider_session_id:
        raise BillingWebhookIntegrityError("Checkout event is missing a session id")

    attempt = (
        db.query(BillingCheckoutSession)
        .filter(BillingCheckoutSession.provider_session_id == provider_session_id)
        .first()
    )
    if attempt is None:
        return "ignored_untracked_checkout"

    if _event_already_processed(db, event_id):
        return "duplicate"

    customer_id = _stripe_id(_value(session_object, "customer"))
    provider_subscription_id = _stripe_id(_value(session_object, "subscription"))
    if not customer_id or not provider_subscription_id:
        raise BillingWebhookIntegrityError(
            "Completed subscription checkout is missing customer or subscription id"
        )

    billing_settings = (
        db.query(BillingSettings)
        .filter(BillingSettings.organization_id == attempt.organization_id)
        .first()
    )
    if billing_settings is None:
        billing_settings = BillingSettings(
            organization_id=attempt.organization_id,
            stripe_customer_id=customer_id,
        )
        db.add(billing_settings)
    elif (
        billing_settings.stripe_customer_id
        and billing_settings.stripe_customer_id != customer_id
    ):
        raise BillingWebhookIntegrityError(
            "Stripe customer conflicts with the organization's billing identity"
        )
    else:
        billing_settings.stripe_customer_id = customer_id

    subscription = (
        db.query(Subscription)
        .filter(Subscription.organization_id == attempt.organization_id)
        .first()
    )
    payload = {
        "checkout_session_id": provider_session_id,
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": provider_subscription_id,
        "plan_id": attempt.plan_id,
        "pricing_tier_id": attempt.pricing_tier_id,
    }

    if subscription is None:
        subscription = Subscription(
            organization_id=attempt.organization_id,
            plan_id=attempt.plan_id,
            stripe_subscription_id=provider_subscription_id,
            status=SubscriptionStatus.ACTIVE,
        )
        db.add(subscription)
        db.flush()
        _append_subscription_event(
            db,
            subscription=subscription,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
        )
    else:
        if (
            subscription.stripe_subscription_id
            and subscription.stripe_subscription_id != provider_subscription_id
            and SubscriptionStatus(subscription.status) != SubscriptionStatus.CANCELLED
        ):
            raise BillingWebhookIntegrityError(
                "Stripe subscription conflicts with the active local subscription"
            )
        subscription.plan_id = attempt.plan_id
        subscription.stripe_subscription_id = provider_subscription_id
        _record_status_event(
            db,
            subscription=subscription,
            event_id=event_id,
            event_type=event_type,
            target_status=SubscriptionStatus.ACTIVE,
            payload=payload,
        )

    attempt.status = BillingCheckoutStatus.COMPLETED
    organization = db.get(Organization, attempt.organization_id)
    if organization is not None:
        organization.state = SubscriptionStatus(subscription.status).value
    return "processed"


def _find_subscription_by_provider_id(
    db: Session,
    provider_subscription_id: str | None,
) -> Subscription | None:
    if not provider_subscription_id:
        return None
    return (
        db.query(Subscription)
        .filter(Subscription.stripe_subscription_id == provider_subscription_id)
        .first()
    )


def _process_subscription_event(
    db: Session,
    *,
    event_id: str,
    event_type: str,
    subscription_object: Any,
) -> str:
    provider_subscription_id = _stripe_id(subscription_object)
    subscription = _find_subscription_by_provider_id(db, provider_subscription_id)
    if subscription is None:
        return "ignored_untracked_subscription"
    if _event_already_processed(db, event_id):
        return "duplicate"

    period_start, period_end = _subscription_period(subscription_object)
    if period_start is not None:
        subscription.current_period_start = period_start
    if period_end is not None:
        subscription.current_period_end = period_end
    if _value(subscription_object, "cancel_at_period_end") is not None:
        subscription.cancel_at_period_end = bool(
            _value(subscription_object, "cancel_at_period_end")
        )

    target_status = (
        SubscriptionStatus.CANCELLED
        if event_type == "customer.subscription.deleted"
        else _stripe_status_to_local(_value(subscription_object, "status"))
    )
    payload = {
        "stripe_subscription_id": provider_subscription_id,
        "stripe_status": _value(subscription_object, "status"),
        "cancel_at_period_end": bool(subscription.cancel_at_period_end),
        "current_period_start": (
            subscription.current_period_start.isoformat()
            if subscription.current_period_start
            else None
        ),
        "current_period_end": (
            subscription.current_period_end.isoformat()
            if subscription.current_period_end
            else None
        ),
    }
    _record_status_event(
        db,
        subscription=subscription,
        event_id=event_id,
        event_type=event_type,
        target_status=target_status,
        payload=payload,
    )
    organization = db.get(Organization, subscription.organization_id)
    if organization is not None:
        organization.state = SubscriptionStatus(subscription.status).value
    return "processed"


def _process_invoice_event(
    db: Session,
    *,
    event_id: str,
    event_type: str,
    invoice_object: Any,
) -> str:
    provider_subscription_id = _invoice_subscription_id(invoice_object)
    subscription = _find_subscription_by_provider_id(db, provider_subscription_id)
    if subscription is None:
        return "ignored_untracked_subscription"
    if _event_already_processed(db, event_id):
        return "duplicate"

    target_status = (
        SubscriptionStatus.ACTIVE
        if event_type in {"invoice.paid", "invoice.payment_succeeded"}
        else SubscriptionStatus.PAST_DUE
    )
    payload = {
        "stripe_subscription_id": provider_subscription_id,
        "stripe_invoice_id": _stripe_id(invoice_object),
        "invoice_status": _value(invoice_object, "status"),
        "amount_paid": _value(invoice_object, "amount_paid"),
        "amount_due": _value(invoice_object, "amount_due"),
        "currency": _value(invoice_object, "currency"),
    }
    _record_status_event(
        db,
        subscription=subscription,
        event_id=event_id,
        event_type=event_type,
        target_status=target_status,
        payload=payload,
    )
    organization = db.get(Organization, subscription.organization_id)
    if organization is not None:
        organization.state = SubscriptionStatus(subscription.status).value
    return "processed"


def process_stripe_event(db: Session, event: Any) -> str:
    """Apply a verified Stripe event to local billing state without committing."""
    event_id = _stripe_id(event)
    event_type = str(_value(event, "type") or "")
    data_object = _value(_value(event, "data"), "object")

    if not event_id or not event_type or data_object is None:
        raise BillingWebhookIntegrityError("Stripe event is missing required fields")

    try:
        fraud_result = process_stripe_fraud_event(db, event)
    except ValueError as exc:
        raise BillingWebhookIntegrityError(str(exc)) from exc
    if fraud_result is not None:
        return fraud_result

    if event_type == "checkout.session.completed":
        return _process_checkout_completed(
            db,
            event_id=event_id,
            event_type=event_type,
            session_object=data_object,
        )
    if event_type == "checkout.session.expired":
        session_id = _stripe_id(data_object)
        attempt = (
            db.query(BillingCheckoutSession)
            .filter(BillingCheckoutSession.provider_session_id == session_id)
            .first()
        )
        if attempt is None:
            return "ignored_untracked_checkout"
        attempt.status = BillingCheckoutStatus.EXPIRED
        return "processed"
    if event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        return _process_subscription_event(
            db,
            event_id=event_id,
            event_type=event_type,
            subscription_object=data_object,
        )
    if event_type in {
        "invoice.paid",
        "invoice.payment_succeeded",
        "invoice.payment_failed",
    }:
        return _process_invoice_event(
            db,
            event_id=event_id,
            event_type=event_type,
            invoice_object=data_object,
        )
    return "ignored_event_type"
