from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator

CHECK_STOCK_POSITIONS = ("TOP", "MIDDLE", "BOTTOM")

class BankCheckSetupUpdateIn(BaseModel):
    next_check_number: int = Field(..., ge=1, le=999999999)
    check_number_prefix: Optional[str] = Field(None, max_length=20)
    check_stock_position: str = "TOP"
    memo_line_enabled: bool = True
    signature_line_enabled: bool = True

    @field_validator("check_stock_position")
    @classmethod
    def validate_position(cls, value: str) -> str:
        normalized = (value or "").strip().upper()
        if normalized not in CHECK_STOCK_POSITIONS:
            raise ValueError(f"check_stock_position must be one of {CHECK_STOCK_POSITIONS}")
        return normalized

    @field_validator("check_number_prefix")
    @classmethod
    def normalize_prefix(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

class BankCheckSetupOut(BaseModel):
    id: Optional[int] = None
    organization_id: int
    bank_account_id: int
    bank_account_name: str
    next_check_number: int
    check_number_prefix: Optional[str] = None
    check_stock_position: str
    memo_line_enabled: bool
    signature_line_enabled: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
