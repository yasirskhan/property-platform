from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.billing import BillingSettings, PaymentMethod
from app.models.user import Organization


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def _org(db, slug: str) -> Organization:
    org = Organization(name="Example", slug=slug)
    db.add(org)
    db.flush()
    return org


def test_billing_settings_defaults_and_one_row_per_org() -> None:
    db, engine = _session()
    try:
        org = _org(db, "billing-settings")
        settings = BillingSettings(organization_id=org.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
        assert settings.currency == "USD"

        db.add(BillingSettings(organization_id=org.id))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()


def test_stripe_customer_id_is_unique_when_present() -> None:
    db, engine = _session()
    try:
        first = _org(db, "billing-customer-a")
        second = _org(db, "billing-customer-b")
        db.add(
            BillingSettings(
                organization_id=first.id,
                stripe_customer_id="cus_unique",
            )
        )
        db.commit()

        db.add(
            BillingSettings(
                organization_id=second.id,
                stripe_customer_id="cus_unique",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()


def test_payment_method_provider_id_is_unique_and_defaults_are_safe() -> None:
    db, engine = _session()
    try:
        first = _org(db, "payment-a")
        second = _org(db, "payment-b")
        method = PaymentMethod(
            organization_id=first.id,
            provider_payment_method_id="pm_unique",
            method_type="card",
            last4="4242",
        )
        db.add(method)
        db.commit()
        db.refresh(method)

        assert method.provider == "stripe"
        assert method.is_active is True
        assert method.is_default is False

        db.add(
            PaymentMethod(
                organization_id=second.id,
                provider_payment_method_id="pm_unique",
                method_type="card",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()


def test_payment_method_metadata_constraints_reject_invalid_values() -> None:
    db, engine = _session()
    try:
        org = _org(db, "payment-invalid")
        db.add(
            PaymentMethod(
                organization_id=org.id,
                provider_payment_method_id="pm_invalid",
                method_type="card",
                last4="123",
                exp_month=13,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()


def test_payment_method_schema_never_stores_pan_or_cvc() -> None:
    column_names = set(PaymentMethod.__table__.columns.keys())
    assert "card_number" not in column_names
    assert "pan" not in column_names
    assert "cvc" not in column_names
    assert "cvv" not in column_names
