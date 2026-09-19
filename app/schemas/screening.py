# ============================================================
# schemas/screening.py
# ============================================================

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class ScreeningProviderOut(BaseModel):
    id: int
    slug: str
    name: str
    description: Optional[str] = None
    pricing_info: Optional[str] = None
    api_docs_url: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class ScreeningSettingsBase(BaseModel):
    provider_slug: Optional[str] = None
    is_enabled: bool = False
    application_fee: Decimal = Field(Decimal("0.00"), ge=0)
    fee_waived_for_managers: bool = False
    auto_screen_on_apply: bool = False


class ScreeningSettingsUpdate(ScreeningSettingsBase):
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    account_id: Optional[str] = None


class ScreeningSettingsOut(ScreeningSettingsBase):
    id: int
    organization_id: int
    account_id: Optional[str] = None
    has_api_key: bool = False
    has_api_secret: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True