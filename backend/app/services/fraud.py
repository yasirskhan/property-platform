"""Fraud signal intake, checkout-abuse heuristics, and review helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.billing import BillingSettings
from app.models.billing_checkout import BillingCheckoutSession
from app.models.fraud import (
    FraudCase,
    FraudCaseStatus,
    FraudRiskLevel,
    FraudSignal,
)


class FraudCheckoutBlocked(RuntimeError):
    """Raised when an organization has an unresolved critical fraud case."""


_RISK_RANK = {
    FraudRiskLevel.LOW: 1,
    FraudRiskLevel.MEDIUM: 2,
    FraudRiskLevel.HIGH: 3,
    FraudRiskLevel.CRITICAL: 4,
}
_BLOCKING_STATUSES = {
    FraudCaseStatus.OPEN,
    FraudCaseStatus.IN_REVIEW,
}
_TERMINAL_STATUSES = {
    FraudCaseStatus.APPROVED,
    FraudCaseStatus.BLOCKED,
    FraudCaseStatus.DISMISSED,
}
_STRIPE_FRAUD_EVENTS = {
    "radar.early_fraud_warning.created",
    "radar.early_fraud_warning.updated",
    "review.opened",
    "review.closed",
    "charge.dispute.created",
    "charge.dispute.closed",
}


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


def _metadata_organization_id(obj: Any) -> int | None:
    metadata = _value(obj, "metadata", {}) or {}
    raw = _value(metadata, "organization_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _organization_id_from_provider_object(db: Session, obj: Any) -> int | None:
    candidates = [
        obj,
        _value(obj, "charge"),
        _value(obj, "payment_intent"),
    ]
    for candidate in candidates:
        if candidate is None or isinstance(candidate, str):
            continue
        organization_id = _metadata_organization_id(candidate)
        if organization_id is not None:
            return organization_id

    customer_id = None
    for candidate in candidates:
        if candidate is None or isinstance(candidate, str):
            continue
        customer_id = _stripe_id(_value(candidate, "customer"))
        if customer_id:
            break

    if not customer_id:
        return None

    settings_row = (
        db.query(BillingSettings)
        .filter(BillingSettings.stripe_customer_id == customer_id)
        .first()
    )
    return settings_row.organization_id if settings_row is not None else None


def _case_for_provider(
    db: Session,
    *,
    provider: str,
    provider_case_id: str,
) -> FraudCase | None:
    return (
        db.query(FraudCase)
        .filter(
            FraudCase.provider == provider,
            FraudCase.provider_case_id == provider_case_id,
        )
        .first()
    )


def _upsert_case(
    db: Session,
    *,
    provider: str,
    provider_case_id: str,
    organization_id: int | None,
    checkout_session_id: int | None,
    status: FraudCaseStatus,
    risk_level: FraudRiskLevel,
    risk_score: int | None,
    reason: str,
    details: dict[str, Any],
) -> FraudCase:
    row = _case_for_provider(
        db,
        provider=provider,
        provider_case_id=provider_case_id,
    )
    if row is None:
        row = FraudCase(
            provider=provider,
            provider_case_id=provider_case_id,
            organization_id=organization_id,
            checkout_session_id=checkout_session_id,
            status=status,
            risk_level=risk_level,
            risk_score=risk_score,
            reason=reason,
            details=details,
        )
        if status in _TERMINAL_STATUSES:
            row.resolved_at = datetime.utcnow()
        db.add(row)
        db.flush()
        return row

    if row.organization_id is None and organization_id is not None:
        row.organization_id = organization_id
    if row.checkout_session_id is None and checkout_session_id is not None:
        row.checkout_session_id = checkout_session_id
    if _RISK_RANK[FraudRiskLevel(risk_level)] > _RISK_RANK[FraudRiskLevel(row.risk_level)]:
        row.risk_level = risk_level
    if risk_score is not None and (row.risk_score is None or risk_score > row.risk_score):
        row.risk_score = risk_score
    row.reason = reason
    row.details = details
    row.status = status
    row.resolved_at = datetime.utcnow() if status in _TERMINAL_STATUSES else None
    db.flush()
    return row


def _signal_already_recorded(
    db: Session,
    *,
    source: str,
    provider_event_id: str,
) -> bool:
    return (
        db.query(FraudSignal.id)
        .filter(
            FraudSignal.source == source,
            FraudSignal.provider_event_id == provider_event_id,
        )
        .first()
        is not None
    )


def _append_signal(
    db: Session,
    *,
    fraud_case: FraudCase,
    source: str,
    signal_type: str,
    severity: FraudRiskLevel,
    provider_event_id: str,
    signal_value: str | None,
    payload: dict[str, Any],
) -> FraudSignal:
    row = FraudSignal(
        fraud_case_id=fraud_case.id,
        organization_id=fraud_case.organization_id,
        source=source,
        signal_type=signal_type,
        severity=severity,
        provider_event_id=provider_event_id,
        signal_value=signal_value,
        payload=payload,
    )
    db.add(row)
    db.flush()
    return row


def organization_checkout_is_blocked(
    db: Session,
    *,
    organization_id: int,
) -> bool:
    return (
        db.query(FraudCase.id)
        .filter(
            FraudCase.organization_id == organization_id,
            FraudCase.status.in_(tuple(_BLOCKING_STATUSES)),
            FraudCase.risk_level == FraudRiskLevel.CRITICAL,
        )
        .first()
        is not None
    )


def require_checkout_not_blocked(db: Session, *, organization_id: int) -> None:
    if organization_checkout_is_blocked(db, organization_id=organization_id):
        raise FraudCheckoutBlocked(
            "Checkout is temporarily unavailable while a critical risk review is open"
        )


def assess_checkout_velocity(
    db: Session,
    *,
    organization_id: int,
    now: datetime | None = None,
) -> FraudCase | None:
    """Create/update an internal review case for unusually rapid checkout attempts."""
    now = now or datetime.utcnow()
    window_start = now - timedelta(hours=1)
    attempts = (
        db.query(BillingCheckoutSession)
        .filter(
            BillingCheckoutSession.organization_id == organization_id,
            BillingCheckoutSession.created_at >= window_start,
        )
        .order_by(BillingCheckoutSession.id.asc())
        .all()
    )
    count = len(attempts)
    if count < 5:
        return None

    risk_level = FraudRiskLevel.CRITICAL if count >= 8 else FraudRiskLevel.HIGH
    risk_score = min(99, 55 + count * 5)
    hour_bucket = now.strftime("%Y%m%d%H")
    provider_case_id = f"checkout-velocity:{organization_id}:{hour_bucket}"
    provider_event_id = f"{provider_case_id}:count:{count}"
    details = {
        "window_minutes": 60,
        "attempt_count": count,
        "threshold": 5,
    }
    case = _upsert_case(
        db,
        provider="internal",
        provider_case_id=provider_case_id,
        organization_id=organization_id,
        checkout_session_id=attempts[-1].id if attempts else None,
        status=FraudCaseStatus.OPEN,
        risk_level=risk_level,
        risk_score=risk_score,
        reason="High checkout-attempt velocity",
        details=details,
    )
    if not _signal_already_recorded(
        db,
        source="internal",
        provider_event_id=provider_event_id,
    ):
        _append_signal(
            db,
            fraud_case=case,
            source="internal",
            signal_type="checkout_velocity",
            severity=risk_level,
            provider_event_id=provider_event_id,
            signal_value=str(count),
            payload=details,
        )
    return case


def refresh_checkout_velocity_cases(
    db: Session,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    now = now or datetime.utcnow()
    window_start = now - timedelta(hours=1)
    organization_ids = [
        row[0]
        for row in (
            db.query(BillingCheckoutSession.organization_id)
            .filter(BillingCheckoutSession.created_at >= window_start)
            .distinct()
            .all()
        )
    ]
    reviewed = 0
    opened_or_updated = 0
    for organization_id in organization_ids:
        reviewed += 1
        if assess_checkout_velocity(
            db,
            organization_id=organization_id,
            now=now,
        ) is not None:
            opened_or_updated += 1
    db.flush()
    return {
        "organizations_reviewed": reviewed,
        "cases_opened_or_updated": opened_or_updated,
    }


def process_stripe_fraud_event(db: Session, event: Any) -> str | None:
    """Record supported Stripe Radar/dispute events without storing card data."""
    event_id = _stripe_id(event)
    event_type = str(_value(event, "type") or "")
    if event_type not in _STRIPE_FRAUD_EVENTS:
        return None
    if not event_id:
        raise ValueError("Stripe fraud event is missing an event id")
    if _signal_already_recorded(
        db,
        source="stripe",
        provider_event_id=event_id,
    ):
        return "duplicate"

    obj = _value(_value(event, "data"), "object")
    if obj is None:
        raise ValueError("Stripe fraud event is missing data.object")

    provider_case_id = _stripe_id(obj)
    if not provider_case_id:
        raise ValueError("Stripe fraud event is missing provider case id")

    organization_id = _organization_id_from_provider_object(db, obj)
    status = FraudCaseStatus.OPEN
    risk_level = FraudRiskLevel.HIGH
    risk_score = 75
    signal_type = event_type.replace(".", "_")
    signal_value = None
    details: dict[str, Any] = {"event_type": event_type}

    if event_type.startswith("radar.early_fraud_warning."):
        actionable = bool(_value(obj, "actionable", False))
        fraud_type = str(_value(obj, "fraud_type") or "unknown")
        risk_level = FraudRiskLevel.CRITICAL if actionable else FraudRiskLevel.HIGH
        risk_score = 95 if actionable else 80
        signal_value = fraud_type
        details.update(
            {
                "actionable": actionable,
                "fraud_type": fraud_type,
                "charge_id": _stripe_id(_value(obj, "charge")),
                "payment_intent_id": _stripe_id(_value(obj, "payment_intent")),
            }
        )
        reason = f"Stripe early fraud warning: {fraud_type}"
    elif event_type == "review.opened":
        opened_reason = str(_value(obj, "opened_reason") or _value(obj, "reason") or "rule")
        signal_value = opened_reason
        details.update(
            {
                "opened_reason": opened_reason,
                "charge_id": _stripe_id(_value(obj, "charge")),
                "payment_intent_id": _stripe_id(_value(obj, "payment_intent")),
            }
        )
        reason = f"Stripe Radar review opened: {opened_reason}"
    elif event_type == "review.closed":
        closed_reason = str(_value(obj, "closed_reason") or _value(obj, "reason") or "canceled")
        signal_value = closed_reason
        details.update(
            {
                "closed_reason": closed_reason,
                "charge_id": _stripe_id(_value(obj, "charge")),
                "payment_intent_id": _stripe_id(_value(obj, "payment_intent")),
            }
        )
        if closed_reason == "approved":
            status = FraudCaseStatus.APPROVED
            risk_level = FraudRiskLevel.MEDIUM
            risk_score = 40
        elif closed_reason in {"refunded_as_fraud", "disputed"}:
            status = FraudCaseStatus.BLOCKED
            risk_level = FraudRiskLevel.CRITICAL
            risk_score = 95
        else:
            status = FraudCaseStatus.DISMISSED
            risk_level = FraudRiskLevel.MEDIUM
            risk_score = 40
        reason = f"Stripe Radar review closed: {closed_reason}"
    else:
        dispute_reason = str(_value(obj, "reason") or "unknown")
        dispute_status = str(_value(obj, "status") or "unknown")
        if dispute_reason not in {"fraudulent", "unrecognized"}:
            return "ignored_nonfraud_dispute"
        risk_level = FraudRiskLevel.CRITICAL
        risk_score = 98
        signal_value = dispute_reason
        details.update(
            {
                "dispute_reason": dispute_reason,
                "dispute_status": dispute_status,
                "charge_id": _stripe_id(_value(obj, "charge")),
                "payment_intent_id": _stripe_id(_value(obj, "payment_intent")),
            }
        )
        if event_type == "charge.dispute.closed":
            if dispute_status == "won":
                status = FraudCaseStatus.DISMISSED
            elif dispute_status == "lost":
                status = FraudCaseStatus.BLOCKED
            else:
                status = FraudCaseStatus.IN_REVIEW
        reason = f"Stripe fraud-related dispute: {dispute_reason}"

    case = _upsert_case(
        db,
        provider="stripe",
        provider_case_id=provider_case_id,
        organization_id=organization_id,
        checkout_session_id=None,
        status=status,
        risk_level=risk_level,
        risk_score=risk_score,
        reason=reason,
        details=details,
    )
    _append_signal(
        db,
        fraud_case=case,
        source="stripe",
        signal_type=signal_type,
        severity=risk_level,
        provider_event_id=event_id,
        signal_value=signal_value,
        payload=details,
    )
    return "processed"
