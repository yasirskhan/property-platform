"""Read-only schemas for customer billing catalog and state."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PricingTierRead(BaseModel):
    id: int
    min_properties: int
    max_properties: int | None
    monthly_price_cents: int
    currency: str


class PlanCatalogRead(BaseModel):
    id: int
    code: str
    name: str
    description: str | None
    pricing_tiers: list[PricingTierRead]


class BillingCatalogOut(BaseModel):
    plans: list[PlanCatalogRead]


class BillingSettingsStateOut(BaseModel):
    billing_email: str | None
    currency: str
    has_provider_customer: bool


class SubscriptionStateOut(BaseModel):
    subscription_id: int
    plan_id: int
    plan_code: str
    plan_name: str
    status: str
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool


class CheckoutStateOut(BaseModel):
    attempt_id: int
    plan_id: int
    pricing_tier_id: int
    status: str
    url: str | None
    created_at: datetime
    updated_at: datetime


class BillingStateOut(BaseModel):
    organization_state: str
    billing_settings: BillingSettingsStateOut | None
    subscription: SubscriptionStateOut | None
    latest_checkout: CheckoutStateOut | None
