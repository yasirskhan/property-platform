from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.billing import Plan, PricingTier, Subscription
from app.models.property import Property, PropertyType, Unit
from app.models.user import Organization, User, UserRole
from app.routers.properties import create_unit, restore_unit
from app.schemas.property import UnitCreate
from app.services.plan_limits import (
    PlanUnitLimitExceeded,
    get_unit_plan_limit_state,
    require_unit_capacity,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db, *, max_units: int | None = 2):
    org = Organization(name="Limit Org", slug="limit-org")
    admin = User(
        email="limit-admin@example.com",
        hashed_password="x",
        first_name="Limit",
        last_name="Admin",
        role=UserRole.ADMIN,
        organization=org,
        is_active=True,
    )
    plan = Plan(code="limit-plan", name="Limit Plan")
    db.add_all([org, admin, plan])
    db.flush()
    tier = PricingTier(
        plan_id=plan.id,
        min_properties=1,
        max_properties=max_units,
        monthly_price_cents=4900,
        currency="USD",
    )
    db.add(tier)
    db.flush()
    subscription = Subscription(
        organization_id=org.id,
        plan_id=plan.id,
        pricing_tier_id=tier.id,
    )
    prop = Property(
        organization_id=org.id,
        name="Limit Property",
        property_type=PropertyType.MULTI_FAMILY,
        address_line1="1 Limit St",
        city="Cleveland",
        state="OH",
        zip_code="44113",
    )
    db.add_all([subscription, prop])
    db.flush()
    return org, admin, plan, tier, prop


def _unit(prop: Property, number: str, *, active: bool = True) -> Unit:
    return Unit(
        property_id=prop.id,
        unit_number=number,
        bedrooms=1,
        bathrooms=Decimal("1"),
        monthly_rent=Decimal("1000"),
        is_active=active,
    )


def test_limit_state_counts_active_units_and_finds_next_tier() -> None:
    db, engine = _session()
    try:
        org, _admin, plan, tier, prop = _seed(db, max_units=2)
        next_tier = PricingTier(
            plan_id=plan.id,
            min_properties=3,
            max_properties=10,
            monthly_price_cents=9900,
            currency="USD",
        )
        db.add_all([next_tier, _unit(prop, "1"), _unit(prop, "2", active=False)])
        db.commit()

        state = get_unit_plan_limit_state(db, organization_id=org.id)

        assert state.current_units == 1
        assert state.max_units == 2
        assert state.remaining_units == 1
        assert state.limit_reached is False
        assert state.pricing_tier_id == tier.id
        assert state.next_pricing_tier_id == next_tier.id
        assert state.next_max_units == 10
    finally:
        db.close()
        engine.dispose()


def test_require_unit_capacity_blocks_when_active_units_are_at_cap() -> None:
    db, engine = _session()
    try:
        org, _admin, _plan, _tier, prop = _seed(db, max_units=1)
        db.add(_unit(prop, "1"))
        db.commit()

        with pytest.raises(PlanUnitLimitExceeded):
            require_unit_capacity(db, organization_id=org.id)
    finally:
        db.close()
        engine.dispose()


def test_create_unit_is_blocked_by_plan_limit_without_writing() -> None:
    db, engine = _session()
    try:
        _org, admin, _plan, _tier, prop = _seed(db, max_units=1)
        db.add(_unit(prop, "1"))
        db.commit()

        payload = UnitCreate(
            unit_number="2",
            bedrooms=1,
            bathrooms=Decimal("1"),
            monthly_rent=Decimal("1200"),
        )
        with pytest.raises(HTTPException) as exc:
            create_unit(prop.id, payload, db, admin)

        assert exc.value.status_code == 409
        assert "PLAN_UNIT_LIMIT_REACHED" in str(exc.value.detail)
        assert db.query(Unit).filter(Unit.unit_number == "2").count() == 0
    finally:
        db.close()
        engine.dispose()


def test_restore_unit_is_blocked_at_cap_and_remains_deleted() -> None:
    db, engine = _session()
    try:
        _org, admin, _plan, _tier, prop = _seed(db, max_units=1)
        active = _unit(prop, "1")
        deleted = _unit(prop, "2", active=False)
        db.add_all([active, deleted])
        db.commit()

        with pytest.raises(HTTPException) as exc:
            restore_unit(prop.id, deleted.id, db, admin)

        assert exc.value.status_code == 409
        db.refresh(deleted)
        assert deleted.is_active is False
    finally:
        db.close()
        engine.dispose()


def test_legacy_subscription_without_tier_is_not_accidentally_capped() -> None:
    db, engine = _session()
    try:
        org, _admin, _plan, _tier, prop = _seed(db, max_units=1)
        subscription = db.query(Subscription).filter(
            Subscription.organization_id == org.id
        ).one()
        subscription.pricing_tier_id = None
        db.add_all([_unit(prop, "1"), _unit(prop, "2")])
        db.commit()

        state = require_unit_capacity(db, organization_id=org.id)
        assert state.current_units == 2
        assert state.limit_enforced is False
        assert state.max_units is None
    finally:
        db.close()
        engine.dispose()
