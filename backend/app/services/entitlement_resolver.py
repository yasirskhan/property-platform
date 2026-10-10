"""Commercial entitlement resolution for customer organizations.

Only feature keys present in the billing catalog are entitlement-managed.
Uncataloged capabilities remain unaffected so billing can be introduced
incrementally without hiding existing product areas before catalog seeding.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.models.billing import (
    Module,
    ModuleFeature,
    Plan,
    PlanModule,
    Subscription,
    SubscriptionItem,
    SubscriptionStatus,
)

ENTITLED_STATUSES = {
    SubscriptionStatus.ACTIVE,
    SubscriptionStatus.PAST_DUE,
}


def resolve_entitlements(
    db: Session,
    *,
    organization_id: int,
    feature_keys: Iterable[str],
) -> dict[str, bool]:
    """Resolve commercial access for feature keys in one bounded query set.

    Missing catalog entries are not entitlement-managed and therefore pass.
    Active core modules pass without a subscription. Paid modules require an
    active plan assignment through an ACTIVE or PAST_DUE subscription.
    """
    keys = list(dict.fromkeys(feature_keys))
    if not keys:
        return {}

    result = {key: True for key in keys}
    rows = (
        db.query(
            ModuleFeature.feature_key,
            Module.id,
            Module.is_core,
            Module.is_active,
        )
        .join(Module, Module.id == ModuleFeature.module_id)
        .filter(ModuleFeature.feature_key.in_(keys))
        .all()
    )
    if not rows:
        return result

    cataloged = {row.feature_key for row in rows}
    active_modules_by_key: dict[str, list[int]] = {key: [] for key in cataloged}
    core_keys: set[str] = set()
    for row in rows:
        if not row.is_active:
            continue
        active_modules_by_key[row.feature_key].append(row.id)
        if row.is_core:
            core_keys.add(row.feature_key)

    for key in cataloged:
        result[key] = key in core_keys
        if not active_modules_by_key[key]:
            result[key] = False

    paid_keys = [
        key
        for key in cataloged
        if active_modules_by_key[key] and key not in core_keys
    ]
    if not paid_keys:
        return result

    subscription = (
        db.query(Subscription)
        .join(Plan, Plan.id == Subscription.plan_id)
        .filter(
            Subscription.organization_id == organization_id,
            Plan.is_active.is_(True),
        )
        .first()
    )
    if subscription is None or subscription.status not in ENTITLED_STATUSES:
        return result

    included_module_ids = {
        row[0]
        for row in (
            db.query(PlanModule.module_id)
            .filter(PlanModule.plan_id == subscription.plan_id)
            .all()
        )
    }
    included_module_ids.update(
        row[0]
        for row in (
            db.query(SubscriptionItem.module_id)
            .filter(SubscriptionItem.subscription_id == subscription.id)
            .all()
        )
    )
    for key in paid_keys:
        result[key] = any(
            module_id in included_module_ids
            for module_id in active_modules_by_key[key]
        )
    return result


def entitlement_allows_feature(
    db: Session,
    *,
    organization_id: int,
    feature_key: str,
) -> bool:
    return resolve_entitlements(
        db,
        organization_id=organization_id,
        feature_keys=[feature_key],
    )[feature_key]
