"""A reference to an association contact, never a certified dues payer."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class HOAPayerDraftIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    contact_link_id: int = Field(ge=1)


class HOAPayerDraftOut(BaseModel):
    id: int
    proposal_id: int
    property_id: int
    contact_link_id: int
    contact_name: str
    status: Literal["STAFF_SUGGESTED_UNVERIFIED"] = "STAFF_SUGGESTED_UNVERIFIED"
    legal_payer_verified: Literal[False] = False
    issue_charge_enabled: Literal[False] = False
