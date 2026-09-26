from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.billing_extras import AddOn, Discount


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def test_add_on_and_discount_tables_are_registered() -> None:
    assert {"add_ons", "discounts"}.issubset(Base.metadata.tables)


def test_add_on_code_unique_and_price_nonnegative() -> None:
    db, engine = _session()
    try:
        db.add(AddOn(code="api", name="API", unit_price_cents=2500))
        db.commit()
        db.add(AddOn(code="api", name="Duplicate", unit_price_cents=100))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        db.add(AddOn(code="bad-price", name="Bad", unit_price_cents=-1))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize(
    ("percent_off", "amount_off_cents"),
    [(None, None), (10, 1000), (0, None), (101, None), (None, -1)],
)
def test_discount_requires_one_valid_discount_value(
    percent_off: int | None,
    amount_off_cents: int | None,
) -> None:
    db, engine = _session()
    try:
        db.add(
            Discount(
                code=f"d-{percent_off}-{amount_off_cents}",
                name="Discount",
                percent_off=percent_off,
                amount_off_cents=amount_off_cents,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()


def test_discount_accepts_percent_or_fixed_amount_and_valid_date_range() -> None:
    db, engine = _session()
    try:
        now = datetime.utcnow()
        db.add_all(
            [
                Discount(code="pct", name="Ten Percent", percent_off=10),
                Discount(code="fixed", name="Five Dollars", amount_off_cents=500),
            ]
        )
        db.commit()

        db.add(
            Discount(
                code="expired-before-start",
                name="Invalid Range",
                percent_off=5,
                starts_at=now,
                ends_at=now - timedelta(days=1),
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()
