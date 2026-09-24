from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.billing import (
    Module,
    ModuleFeature,
    Plan,
    PlanModule,
    Subscription,
    SubscriptionItem,
    SubscriptionStatus,
)
from app.models.user import Organization
from app.services.entitlement_resolver import entitlement_allows_feature


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def _org(db, slug: str = "entitlement-org") -> Organization:
    org = Organization(name="Example", slug=slug)
    db.add(org)
    db.flush()
    return org


def _feature(db, *, key: str, module_key: str, core: bool = False) -> Module:
    module = Module(key=module_key, name=module_key.title(), is_core=core)
    db.add(module)
    db.flush()
    db.add(ModuleFeature(module_id=module.id, feature_key=key))
    db.flush()
    return module


def test_uncataloged_feature_is_not_entitlement_gated() -> None:
    db, engine = _session()
    try:
        org = _org(db)
        db.commit()
        assert entitlement_allows_feature(
            db, organization_id=org.id, feature_key="ACCOUNTING"
        ) is True
    finally:
        db.close()
        engine.dispose()


def test_core_feature_is_available_without_subscription() -> None:
    db, engine = _session()
    try:
        org = _org(db)
        _feature(db, key="DASHBOARD", module_key="core", core=True)
        db.commit()
        assert entitlement_allows_feature(
            db, organization_id=org.id, feature_key="DASHBOARD"
        ) is True
    finally:
        db.close()
        engine.dispose()


def test_paid_feature_requires_subscription_and_plan_module() -> None:
    db, engine = _session()
    try:
        org = _org(db)
        accounting = _feature(db, key="ACCOUNTING", module_key="accounting")
        plan = Plan(code="pro", name="Pro")
        db.add(plan)
        db.flush()
        db.add(PlanModule(plan_id=plan.id, module_id=accounting.id))
        db.commit()

        assert entitlement_allows_feature(
            db, organization_id=org.id, feature_key="ACCOUNTING"
        ) is False

        db.add(Subscription(organization_id=org.id, plan_id=plan.id))
        db.commit()
        assert entitlement_allows_feature(
            db, organization_id=org.id, feature_key="ACCOUNTING"
        ) is True
    finally:
        db.close()
        engine.dispose()


def test_subscription_does_not_grant_module_missing_from_plan() -> None:
    db, engine = _session()
    try:
        org = _org(db)
        _feature(db, key="REPORTING", module_key="reporting")
        plan = Plan(code="starter", name="Starter")
        db.add(plan)
        db.flush()
        db.add(Subscription(organization_id=org.id, plan_id=plan.id))
        db.commit()

        assert entitlement_allows_feature(
            db, organization_id=org.id, feature_key="REPORTING"
        ) is False
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (SubscriptionStatus.ACTIVE, True),
        (SubscriptionStatus.PAST_DUE, True),
        (SubscriptionStatus.RESTRICTED, False),
        (SubscriptionStatus.SUSPENDED, False),
        (SubscriptionStatus.CANCELLED, False),
    ],
)
def test_subscription_status_controls_paid_entitlement(
    status: SubscriptionStatus, expected: bool
) -> None:
    db, engine = _session()
    try:
        org = _org(db, slug=f"status-{status.value.lower()}")
        module = _feature(db, key="MAINTENANCE", module_key="maintenance")
        plan = Plan(code=f"plan-{status.value.lower()}", name="Plan")
        db.add(plan)
        db.flush()
        db.add(PlanModule(plan_id=plan.id, module_id=module.id))
        db.add(Subscription(organization_id=org.id, plan_id=plan.id, status=status))
        db.commit()

        assert entitlement_allows_feature(
            db, organization_id=org.id, feature_key="MAINTENANCE"
        ) is expected
    finally:
        db.close()
        engine.dispose()


def test_inactive_plan_or_module_does_not_grant_paid_feature() -> None:
    db, engine = _session()
    try:
        org = _org(db)
        module = _feature(db, key="LEASING", module_key="leasing")
        plan = Plan(code="inactive-plan", name="Inactive", is_active=False)
        db.add(plan)
        db.flush()
        db.add(PlanModule(plan_id=plan.id, module_id=module.id))
        db.add(Subscription(organization_id=org.id, plan_id=plan.id))
        db.commit()
        assert entitlement_allows_feature(
            db, organization_id=org.id, feature_key="LEASING"
        ) is False

        plan.is_active = True
        module.is_active = False
        db.commit()
        assert entitlement_allows_feature(
            db, organization_id=org.id, feature_key="LEASING"
        ) is False
    finally:
        db.close()
        engine.dispose()


def test_subscription_item_add_on_grants_paid_module_feature() -> None:
    db, engine = _session()
    try:
        org = _org(db, slug="item-addon")
        module = _feature(
            db,
            key="REPORTING.BUILDER",
            module_key="report-builder",
        )
        plan = Plan(code="base-with-addon", name="Base")
        db.add(plan)
        db.flush()
        subscription = Subscription(
            organization_id=org.id,
            plan_id=plan.id,
        )
        db.add(subscription)
        db.flush()
        db.add(
            SubscriptionItem(
                subscription_id=subscription.id,
                module_id=module.id,
            )
        )
        db.commit()

        assert entitlement_allows_feature(
            db,
            organization_id=org.id,
            feature_key="REPORTING.BUILDER",
        ) is True
    finally:
        db.close()
        engine.dispose()
