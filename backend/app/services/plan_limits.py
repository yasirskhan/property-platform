"""Authoritative customer plan-limit enforcement.

Foundation 3.4.12 uses the existing pricing-tier upper bound as the
managed-unit ceiling for self-serve subscriptions. Subscriptions that do not
carry a pricing tier are intentionally uncapped for backward-compatible
enterprise/legacy provisioning.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.billing import PricingTier, Subscription
from app.models.property import Property, Unit


@dataclass(frozen=True)
class UnitPlanLimitState:
    current_units: int
    max_units: int | None
    remaining_units: int | None
    limit_enforced: bool
    limit_reached: bool
    pricing_tier_id: int | None
    next_pricing_tier_id: int | None
    next_max_units: int | None

    def as_dict(self) -> dict[str, int | bool | None]:
        return asdict(self)


class PlanUnitLimitExceeded(RuntimeError):
    def __init__(self, state: UnitPlanLimitState) -> None:
        self.state = state
        super().__init__(
            f"Your plan includes up to {state.max_units} active units and "
            f"you already have {state.current_units}. "
            "Upgrade to a higher tier before adding or restoring another unit."
        )


def _active_unit_count(db: Session, *, organization_id: int) -> int:
    value = (
        db.query(func.count(Unit.id))
        .join(Property, Property.id == Unit.property_id)
        .filter(
            Property.organization_id == organization_id,
            Unit.is_active.is_(True),
        )
        .scalar()
    )
    return int(value or 0)


def _next_tier(
    db: Session,
    *,
    plan_id: int,
    current_tier: PricingTier,
) -> PricingTier | None:
    current_max = current_tier.max_properties
    if current_max is None:
        return None
    candidates = [
        tier
        for tier in (
            db.query(PricingTier)
            .filter(
                PricingTier.plan_id == plan_id,
                PricingTier.id != current_tier.id,
            )
            .all()
        )
        if tier.max_properties is None or tier.max_properties > current_max
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda tier: (
            tier.max_properties is None,
            tier.max_properties if tier.max_properties is not None else 2**31,
            tier.min_properties,
            tier.id,
        ),
    )[0]


def get_unit_plan_limit_state(
    db: Session,
    *,
    organization_id: int,
) -> UnitPlanLimitState:
    current_units = _active_unit_count(db, organization_id=organization_id)
    subscription = (
        db.query(Subscription)
        .filter(Subscription.organization_id == organization_id)
        .first()
    )
    if subscription is None or subscription.pricing_tier_id is None:
        return UnitPlanLimitState(
            current_units=current_units,
            max_units=None,
            remaining_units=None,
            limit_enforced=False,
            limit_reached=False,
            pricing_tier_id=None,
            next_pricing_tier_id=None,
            next_max_units=None,
        )

    tier = db.get(PricingTier, subscription.pricing_tier_id)
    if tier is None:
        return UnitPlanLimitState(
            current_units=current_units,
            max_units=None,
            remaining_units=None,
            limit_enforced=False,
            limit_reached=False,
            pricing_tier_id=subscription.pricing_tier_id,
            next_pricing_tier_id=None,
            next_max_units=None,
        )

    max_units = tier.max_properties
    next_tier = _next_tier(
        db,
        plan_id=subscription.plan_id,
        current_tier=tier,
    )
    if max_units is None:
        return UnitPlanLimitState(
            current_units=current_units,
            max_units=None,
            remaining_units=None,
            limit_enforced=False,
            limit_reached=False,
            pricing_tier_id=tier.id,
            next_pricing_tier_id=None,
            next_max_units=None,
        )

    return UnitPlanLimitState(
        current_units=current_units,
        max_units=max_units,
        remaining_units=max(0, max_units - current_units),
        limit_enforced=True,
        limit_reached=current_units >= max_units,
        pricing_tier_id=tier.id,
        next_pricing_tier_id=next_tier.id if next_tier else None,
        next_max_units=next_tier.max_properties if next_tier else None,
    )


def require_unit_capacity(
    db: Session,
    *,
    organization_id: int,
    additional_units: int = 1,
) -> UnitPlanLimitState:
    if additional_units < 1:
        raise ValueError("additional_units must be at least 1")
    state = get_unit_plan_limit_state(
        db,
        organization_id=organization_id,
    )
    if (
        state.limit_enforced
        and state.max_units is not None
        and state.current_units + additional_units > state.max_units
    ):
        raise PlanUnitLimitExceeded(state)
    return state
