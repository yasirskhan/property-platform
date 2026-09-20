# ============================================================
# bank_account.py (schemas)
# ------------------------------------------------------------
# Pydantic shapes for Bank Accounts.
# ============================================================

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


BANK_ACCOUNT_TYPES = ("OPERATING", "ESCROW")
ACH_FORMATS = ("CSV", "NACHA")


# ============================================================
# WRITE SHAPES
# ============================================================

class BankAccountCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    bank_name: Optional[str] = Field(None, max_length=200)
    routing_number: Optional[str] = Field(None, max_length=20)
    account_number: Optional[str] = Field(None, max_length=40)
    gl_account_id: int
    account_type: str = "OPERATING"
    ach_format: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("account_type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        up = (v or "").strip().upper()
        if up not in BANK_ACCOUNT_TYPES:
            raise ValueError(
                f"account_type must be one of {BANK_ACCOUNT_TYPES}"
            )
        return up

    @field_validator("ach_format")
    @classmethod
    def _valid_ach(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        up = v.strip().upper()
        if up not in ACH_FORMATS:
            raise ValueError(f"ach_format must be one of {ACH_FORMATS}")
        return up


class BankAccountUpdateIn(BaseModel):
    """All fields optional — PATCH-style edit."""
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    bank_name: Optional[str] = Field(None, max_length=200)
    routing_number: Optional[str] = Field(None, max_length=20)
    account_number: Optional[str] = Field(None, max_length=40)
    account_type: Optional[str] = None
    ach_format: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("account_type")
    @classmethod
    def _valid_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        up = v.strip().upper()
        if up not in BANK_ACCOUNT_TYPES:
            raise ValueError(
                f"account_type must be one of {BANK_ACCOUNT_TYPES}"
            )
        return up

    @field_validator("ach_format")
    @classmethod
    def _valid_ach(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        up = v.strip().upper()
        if up not in ACH_FORMATS:
            raise ValueError(f"ach_format must be one of {ACH_FORMATS}")
        return up


# ============================================================
# READ SHAPES
# ============================================================

class BankAccountOut(BaseModel):
    id: int
    organization_id: int
    name: str
    bank_name: Optional[str] = None
    routing_number: Optional[str] = None
    account_number: Optional[str] = None
    gl_account_id: int
    gl_account_number: Optional[str] = None
    gl_account_name: Optional[str] = None
    account_type: str
    ach_format: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool
    created_by_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BankAccountListOut(BaseModel):
    items: List[BankAccountOut]
    total: int