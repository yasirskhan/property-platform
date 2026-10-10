"""Transactional subscription lifecycle transitions."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.billing import Subscription, SubscriptionEvent, SubscriptionStatus


_ALLOWED_TRANSITIONS: dict[SubscriptionStatus, set[SubscriptionStatus]] = {
    SubscriptionStatus.ACTIVE: {
        SubscriptionStatus.PAST_DUE,
        SubscriptionStatus.CANCELLED,
    },
    SubscriptionStatus.PAST_DUE: {
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.RESTRICTED,
        SubscriptionStatus.CANCELLED,
    },
    SubscriptionStatus.RESTRICTED: {
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.PAST_DUE,
        SubscriptionStatus.SUSPENDED,
        SubscriptionStatus.CANCELLED,
    },
    SubscriptionStatus.SUSPENDED: {
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.CANCELLED,
    },
    SubscriptionStatus.CANCELLED: set(),
}


class InvalidSubscriptionTransition(ValueError):
    """Raised when a subscription lifecycle transition is not permitted."""


def transition_subscription(
    db: Session,
    *,
    subscription: Subscription,
    target_status: SubscriptionStatus,
    event_type: str | None = None,
    provider: str | None = None,
    provider_event_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> SubscriptionEvent | None:
    """Move a subscription to a valid status and append one lifecycle event.

    The caller owns the transaction. This function flushes, but never commits,
    so the status change and append-only event remain atomic with surrounding
    work such as webhook processing.
    """
    current_status = SubscriptionStatus(subscription.status)
    target_status = SubscriptionStatus(target_status)

    if current_status == target_status:
        return None

    if provider_event_id:
        existing = (
            db.query(SubscriptionEvent)
            .filter(SubscriptionEvent.provider_event_id == provider_event_id)
            .first()
        )
        if existing is not None:
            return existing

    if target_status not in _ALLOWED_TRANSITIONS[current_status]:
        raise InvalidSubscriptionTransition(
            f"Cannot transition subscription {subscription.id} "
            f"from {current_status.value} to {target_status.value}"
        )

    event_payload = {
        "from_status": current_status.value,
        "to_status": target_status.value,
    }
    if payload:
        event_payload.update(payload)

    subscription.status = target_status
    event = SubscriptionEvent(
        subscription_id=subscription.id,
        event_type=event_type or f"subscription.{target_status.value.lower()}",
        provider=provider,
        provider_event_id=provider_event_id,
        payload=event_payload,
    )
    db.add(event)
    db.flush()
    return event


def set_cancel_at_period_end(
    db: Session,
    *,
    subscription: Subscription,
    enabled: bool,
    provider: str | None = None,
    provider_event_id: str | None = None,
) -> SubscriptionEvent | None:
    """Change scheduled cancellation and append an auditable event."""
    enabled = bool(enabled)
    if bool(subscription.cancel_at_period_end) == enabled:
        return None

    if provider_event_id:
        existing = (
            db.query(SubscriptionEvent)
            .filter(SubscriptionEvent.provider_event_id == provider_event_id)
            .first()
        )
        if existing is not None:
            return existing

    subscription.cancel_at_period_end = enabled
    event = SubscriptionEvent(
        subscription_id=subscription.id,
        event_type=(
            "subscription.cancel_scheduled"
            if enabled
            else "subscription.cancel_schedule_removed"
        ),
        provider=provider,
        provider_event_id=provider_event_id,
        payload={"cancel_at_period_end": enabled},
    )
    db.add(event)
    db.flush()
    return event
