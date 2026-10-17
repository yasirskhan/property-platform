"""Interest readiness is a recorded proposal, not a jurisdictional legal ruling."""
from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator


ProposedRecipient = Literal["UNDETERMINED", "TENANT", "STATE", "HOUSING_FUND", "OTHER"]


class TrustInterestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    jurisdiction: str | None = Field(default=None, max_length=80)
    proposed_recipient: ProposedRecipient = "UNDETERMINED"
    basis_reference: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_reference(self):
        self.jurisdiction = self.jurisdiction.strip() or None if self.jurisdiction else None
        self.basis_reference = self.basis_reference.strip() or None if self.basis_reference else None
        if self.proposed_recipient != "UNDETERMINED" and (not self.jurisdiction or not self.basis_reference):
            raise ValueError("A jurisdiction and supporting reference are required for a proposed recipient")
        return self


class TrustInterestOut(BaseModel):
    bank_account_id: int
    bank_account_type: str
    configured: bool
    jurisdiction: str | None
    proposed_recipient: ProposedRecipient
    basis_reference_recorded: bool
    legal_review_required: Literal[True] = True
    interest_allocation_enabled: Literal[False] = False
    interest_posting_enabled: Literal[False] = False
    updated_at: datetime | None = None
