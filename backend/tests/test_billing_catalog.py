from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.billing import Module, ModuleFeature, Plan, PlanModule, PricingTier


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def test_billing_catalog_registers_expected_tables() -> None:
    assert {
        "plans",
        "modules",
        "plan_modules",
        "module_features",
        "pricing_tiers",
    }.issubset(Base.metadata.tables)


def test_plan_codes_are_unique() -> None:
    db, engine = _session()
    try:
        db.add(Plan(code="starter", name="Starter"))
        db.commit()
        db.add(Plan(code="starter", name="Duplicate"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()


def test_plan_module_and_module_feature_pairs_are_unique() -> None:
    db, engine = _session()
    try:
        plan = Plan(code="pro", name="Pro")
        module = Module(key="accounting", name="Accounting")
        db.add_all([plan, module])
        db.commit()

        db.add(PlanModule(plan_id=plan.id, module_id=module.id))
        db.add(ModuleFeature(module_id=module.id, feature_key="accounting.receipts"))
        db.commit()

        db.add(PlanModule(plan_id=plan.id, module_id=module.id))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        db.add(ModuleFeature(module_id=module.id, feature_key="accounting.receipts"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize(
    ("min_properties", "max_properties", "monthly_price_cents"),
    [
        (0, 10, 1000),
        (11, 10, 1000),
        (1, None, -1),
    ],
)
def test_pricing_tier_rejects_invalid_ranges_and_prices(
    min_properties: int,
    max_properties: int | None,
    monthly_price_cents: int,
) -> None:
    db, engine = _session()
    try:
        plan = Plan(code="growth", name="Growth")
        db.add(plan)
        db.commit()
        db.add(
            PricingTier(
                plan_id=plan.id,
                min_properties=min_properties,
                max_properties=max_properties,
                monthly_price_cents=monthly_price_cents,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()


def test_pricing_tier_defaults_currency_and_unique_lower_bound() -> None:
    db, engine = _session()
    try:
        plan = Plan(code="enterprise", name="Enterprise")
        db.add(plan)
        db.commit()
        tier = PricingTier(
            plan_id=plan.id,
            min_properties=1,
            max_properties=50,
            monthly_price_cents=25000,
        )
        db.add(tier)
        db.commit()
        db.refresh(tier)
        assert tier.currency == "USD"

        db.add(
            PricingTier(
                plan_id=plan.id,
                min_properties=1,
                max_properties=100,
                monthly_price_cents=30000,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()
