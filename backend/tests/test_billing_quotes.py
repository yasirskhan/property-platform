from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.billing import Module
from app.models.billing_extras import AddOn
from app.models.billing_quotes import Quote, QuoteLineItem
from app.models.user import Organization


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def test_quote_tables_are_registered() -> None:
    assert {"quotes", "quote_line_items"}.issubset(Base.metadata.tables)


def test_quote_status_and_amount_constraints() -> None:
    db, engine = _session()
    try:
        org = Organization(name="Quote Org", slug="quote-org")
        db.add(org)
        db.commit()

        db.add(Quote(organization_id=org.id, status="BOGUS"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        db.add(Quote(organization_id=org.id, subtotal_cents=-1))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()


def test_quote_line_rejects_two_catalog_references_and_invalid_amounts() -> None:
    db, engine = _session()
    try:
        org = Organization(name="Line Org", slug="line-org")
        module = Module(key="accounting-q", name="Accounting")
        add_on = AddOn(code="api-q", name="API", unit_price_cents=500)
        db.add_all([org, module, add_on])
        db.commit()
        quote = Quote(organization_id=org.id)
        db.add(quote)
        db.commit()

        db.add(
            QuoteLineItem(
                quote_id=quote.id,
                module_id=module.id,
                add_on_id=add_on.id,
                description="Invalid double reference",
                quantity=1,
                unit_price_cents=500,
                line_total_cents=500,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        db.add(
            QuoteLineItem(
                quote_id=quote.id,
                description="Invalid quantity",
                quantity=0,
                unit_price_cents=500,
                line_total_cents=0,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()


def test_quote_accepts_custom_and_catalog_lines() -> None:
    db, engine = _session()
    try:
        org = Organization(name="Valid Quote Org", slug="valid-quote-org")
        module = Module(key="reporting-q", name="Reporting")
        db.add_all([org, module])
        db.commit()
        quote = Quote(organization_id=org.id, subtotal_cents=2000, total_cents=2000)
        db.add(quote)
        db.commit()

        db.add_all(
            [
                QuoteLineItem(
                    quote_id=quote.id,
                    description="Custom setup",
                    quantity=1,
                    unit_price_cents=1000,
                    line_total_cents=1000,
                ),
                QuoteLineItem(
                    quote_id=quote.id,
                    module_id=module.id,
                    description="Reporting",
                    quantity=1,
                    unit_price_cents=1000,
                    line_total_cents=1000,
                ),
            ]
        )
        db.commit()
        assert len(quote.line_items) == 2
    finally:
        db.close()
        engine.dispose()
