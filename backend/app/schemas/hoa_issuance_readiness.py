"""Read-only prerequisites; NEVER legal issuance or posting certification."""
from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel


class HOAIssuanceReadinessOut(BaseModel):
    occurrence_id: int
    property_id: int
    proposed_on: date
    proposed_amount: Decimal
    status: Literal["PLANNED", "VOIDED"]
    accounting_period_unlocked: bool
    candidate_income_account_valid: bool
    governing_authority_verified: Literal[False] = False
    assessment_approval_verified: Literal[False] = False
    legal_payer_liability_verified: Literal[False] = False
    approved_gl_mapping_verified: Literal[False] = False
    posting_enabled: Literal[False] = False
    reversal_enabled: Literal[False] = False
    missing_requirements: list[str]
