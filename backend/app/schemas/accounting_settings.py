from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class AccountingGLAccountChoice(BaseModel):
    id: int
    gl_number: str
    name: str
    account_type: str


class AccountingKeyAccountSummary(BaseModel):
    id: int
    key_type: str
    gl_account_id: int
    gl_number: str
    name: str


class AccountingCheckSetupSummary(BaseModel):
    bank_account_id: int
    bank_account_name: str
    configured: bool
    next_check_number: Optional[int] = None


class AccountingSettingsUpdate(BaseModel):
    gpr_rent_gl_account_id: Optional[int] = None
    gpr_market_gl_account_id: Optional[int] = None
    gpr_loss_gain_gl_account_id: Optional[int] = None
    receipt_cash_gl_account_id: Optional[int] = None
    report_export_format: str = Field(default="CSV")
    fiscal_year_start_month: int = Field(default=1, ge=1, le=12)
    accounting_basis: str = Field(default="ACCRUAL")

    @field_validator("report_export_format")
    @classmethod
    def validate_export_format(cls, value: str) -> str:
        normalized = (value or "").strip().upper()
        if normalized not in {"CSV", "EXCEL"}:
            raise ValueError("report_export_format must be CSV or EXCEL")
        return normalized

    @field_validator("accounting_basis")
    @classmethod
    def validate_accounting_basis(cls, value: str) -> str:
        normalized = (value or "").strip().upper()
        if normalized not in {"ACCRUAL", "CASH"}:
            raise ValueError("accounting_basis must be ACCRUAL or CASH")
        return normalized


class AccountingSettingsOut(AccountingSettingsUpdate):
    organization_id: int
    gpr_rent_gl_account: Optional[AccountingGLAccountChoice] = None
    gpr_market_gl_account: Optional[AccountingGLAccountChoice] = None
    gpr_loss_gain_gl_account: Optional[AccountingGLAccountChoice] = None
    receipt_cash_gl_account: Optional[AccountingGLAccountChoice] = None
    eligible_income_accounts: list[AccountingGLAccountChoice] = Field(default_factory=list)
    eligible_cash_accounts: list[AccountingGLAccountChoice] = Field(default_factory=list)
    key_accounts: list[AccountingKeyAccountSummary] = Field(default_factory=list)
    check_setups: list[AccountingCheckSetupSummary] = Field(default_factory=list)
