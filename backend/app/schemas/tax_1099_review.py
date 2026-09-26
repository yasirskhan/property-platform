"""Schemas for manually sourced, non-filing 1099 review records."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

FormType = Literal["1099-NEC", "1099-MISC"]
IncomeCategory = Literal["NONEMPLOYEE_COMPENSATION", "RENTS"]
SourceType = Literal["BILL", "CHECK", "OWNER_LEDGER", "EXTERNAL_STATEMENT", "OTHER"]


class Tax1099DataIn(BaseModel):
    tax_year: int = Field(ge=2020, le=2100)
    form_type: FormType
    income_category: IncomeCategory
    payer_profile_id: int = Field(ge=1)
    recipient_profile_id: int = Field(ge=1)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    source_type: SourceType
    source_reference: str = Field(min_length=1, max_length=160)
    source_note: str | None = Field(default=None, max_length=1000)

    @field_validator("source_reference")
    @classmethod
    def reference_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Supporting reference is required")
        return value

    @field_validator("source_note")
    @classmethod
    def note_text(cls, value: str | None) -> str | None:
        value = value.strip() if value else None
        return value or None

    @model_validator(mode="after")
    def supported_pair(self):
        allowed = {
            ("1099-NEC", "NONEMPLOYEE_COMPENSATION"),
            ("1099-MISC", "RENTS"),
        }
        if (self.form_type, self.income_category) not in allowed:
            raise ValueError("Unsupported 1099 form/category combination")
        return self


class Tax1099PrepareIn(Tax1099DataIn):
    idempotency_key: str = Field(min_length=8, max_length=64)

    @field_validator("idempotency_key")
    @classmethod
    def key_chars(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_:." for ch in value):
            raise ValueError("Invalid idempotency key")
        return value


class Tax1099UpdateIn(Tax1099DataIn):
    pass


class Tax1099ApprovalIn(BaseModel):
    source_review_confirmed: bool
    threshold_review_confirmed: bool
    recipient_review_confirmed: bool

    @model_validator(mode="after")
    def all_confirmed(self):
        if not all((
            self.source_review_confirmed,
            self.threshold_review_confirmed,
            self.recipient_review_confirmed,
        )):
            raise ValueError("All approval review confirmations are required")
        return self


class Tax1099ReviewOut(BaseModel):
    id: int
    tax_year: int
    form_type: str
    income_category: str
    payer_profile_id: int
    payer_tin_last4: str
    recipient_profile_id: int
    recipient_subject_type: str
    recipient_subject_id: int
    recipient_tin_last4: str
    amount: Decimal
    source_type: str
    source_reference: str
    source_note: str | None
    status: str
    w9_evidence_present: bool
    profile_changed_since_review: bool
    source_review_confirmed: bool
    threshold_review_confirmed: bool
    recipient_review_confirmed: bool
    prepared_by_id: int | None
    reviewed_by_id: int | None
    approved_by_id: int | None
    reviewed_at: datetime | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime



class Tax1099PreflightOut(BaseModel):
    """No name, address, full tax ID, or IRS-transmission artifact."""
    record_id: int
    tax_year: int
    form_type: str
    review_status: str
    ready_for_provider_handoff: bool
    filing_enabled: bool = False
    submission_status: Literal["NOT_SUBMITTED"] = "NOT_SUBMITTED"
    blockers: list[str]


class Tax1099ProviderDryRunIn(BaseModel):
    """Explicit consent before encrypted taxpayer data leaves for provider sandbox validation."""
    confirm_external_tax_data_sandbox: Literal[True]


class Tax1099ProviderDryRunOut(BaseModel):
    record_id: int
    provider: Literal["AVALARA_SANDBOX"]
    dry_run: Literal[True] = True
    validated: bool
    provider_http_status: int
    submission_status: Literal["NOT_SUBMITTED"] = "NOT_SUBMITTED"
    filing_enabled: Literal[False] = False
    message: str
