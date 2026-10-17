"""Schemas for backend Stripe Checkout orchestration."""

from pydantic import BaseModel, Field


class CheckoutSessionCreate(BaseModel):
    pricing_tier_id: int = Field(gt=0)
    idempotency_key: str = Field(min_length=16, max_length=128)


class CheckoutSessionOut(BaseModel):
    attempt_id: int
    session_id: str
    url: str
    status: str
