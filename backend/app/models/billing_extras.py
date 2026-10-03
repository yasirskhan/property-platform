"""Billing add-on and discount catalog models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Integer, String, Text

from app.core.database import Base


class AddOn(Base):
    __tablename__ = "add_ons"
    __table_args__ = (
        CheckConstraint("unit_price_cents >= 0", name="ck_add_ons_unit_price"),
    )

    id = Column(Integer, primary_key=True)
    code = Column(String(80), nullable=False, unique=True, index=True)
    name = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    unit_price_cents = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="USD", server_default="USD")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true", index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Discount(Base):
    __tablename__ = "discounts"
    __table_args__ = (
        CheckConstraint(
            "(percent_off IS NOT NULL AND amount_off_cents IS NULL) OR "
            "(percent_off IS NULL AND amount_off_cents IS NOT NULL)",
            name="ck_discounts_exactly_one_value",
        ),
        CheckConstraint(
            "percent_off IS NULL OR (percent_off >= 1 AND percent_off <= 100)",
            name="ck_discounts_percent_range",
        ),
        CheckConstraint(
            "amount_off_cents IS NULL OR amount_off_cents >= 0",
            name="ck_discounts_amount_nonnegative",
        ),
        CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at >= starts_at",
            name="ck_discounts_date_range",
        ),
    )

    id = Column(Integer, primary_key=True)
    code = Column(String(80), nullable=False, unique=True, index=True)
    name = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    percent_off = Column(Integer, nullable=True)
    amount_off_cents = Column(Integer, nullable=True)
    currency = Column(String(3), nullable=False, default="USD", server_default="USD")
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true", index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
