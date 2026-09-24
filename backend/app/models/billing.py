"""Commercial billing catalog and customer subscription models."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True)
    code = Column(String(80), nullable=False, unique=True, index=True)
    name = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true", index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    modules = relationship(
        "PlanModule",
        back_populates="plan",
        cascade="all, delete-orphan",
    )
    pricing_tiers = relationship(
        "PricingTier",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="PricingTier.min_properties",
    )
    subscriptions = relationship("Subscription", back_populates="plan")


class Module(Base):
    __tablename__ = "modules"

    id = Column(Integer, primary_key=True)
    key = Column(String(120), nullable=False, unique=True, index=True)
    name = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    is_core = Column(Boolean, nullable=False, default=False, server_default="false")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true", index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    plans = relationship(
        "PlanModule",
        back_populates="module",
        cascade="all, delete-orphan",
    )
    features = relationship(
        "ModuleFeature",
        back_populates="module",
        cascade="all, delete-orphan",
    )


class PlanModule(Base):
    __tablename__ = "plan_modules"
    __table_args__ = (
        UniqueConstraint("plan_id", "module_id", name="uq_plan_modules_plan_module"),
    )

    id = Column(Integer, primary_key=True)
    plan_id = Column(
        Integer,
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    module_id = Column(
        Integer,
        ForeignKey("modules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    plan = relationship("Plan", back_populates="modules")
    module = relationship("Module", back_populates="plans")


class ModuleFeature(Base):
    __tablename__ = "module_features"
    __table_args__ = (
        UniqueConstraint("module_id", "feature_key", name="uq_module_features_module_key"),
    )

    id = Column(Integer, primary_key=True)
    module_id = Column(
        Integer,
        ForeignKey("modules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_key = Column(String(200), nullable=False, index=True)
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    module = relationship("Module", back_populates="features")


class PricingTier(Base):
    __tablename__ = "pricing_tiers"
    __table_args__ = (
        CheckConstraint("min_properties >= 1", name="ck_pricing_tiers_min_properties"),
        CheckConstraint(
            "max_properties IS NULL OR max_properties >= min_properties",
            name="ck_pricing_tiers_property_range",
        ),
        CheckConstraint("monthly_price_cents >= 0", name="ck_pricing_tiers_price"),
        UniqueConstraint("plan_id", "min_properties", name="uq_pricing_tiers_plan_min"),
    )

    id = Column(Integer, primary_key=True)
    plan_id = Column(
        Integer,
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    min_properties = Column(Integer, nullable=False)
    max_properties = Column(Integer, nullable=True)
    monthly_price_cents = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="USD", server_default="USD")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    plan = relationship("Plan", back_populates="pricing_tiers")


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    RESTRICTED = "RESTRICTED"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint(
            "current_period_end IS NULL OR current_period_start IS NULL "
            "OR current_period_end >= current_period_start",
            name="ck_subscriptions_period_range",
        ),
    )

    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    plan_id = Column(
        Integer,
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status = Column(
        SqlEnum(
            SubscriptionStatus,
            name="subscription_status",
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        nullable=False,
        default=SubscriptionStatus.ACTIVE,
        server_default=SubscriptionStatus.ACTIVE.value,
        index=True,
    )
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    organization = relationship("Organization")
    plan = relationship("Plan", back_populates="subscriptions")
