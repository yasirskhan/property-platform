"""Annual budget association linkage; separate member approval and posting remain required."""
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator

class HOAIncreaseCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    source_charge_id: int = Field(ge=1)
    title: str = Field(min_length=3, max_length=120)
    proposed_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    effective_on: date

    @field_validator("title")
    @classmethod
    def clean_title(cls, text: str) -> str:
        value = " ".join(text.split())
        if len(value) < 3:
            raise ValueError("Increase title must identify the proposal.")
        return value

class HOAIncreaseSourceOut(BaseModel):
    charge_id: int
    member_user_id: int
    proposal_id: int
    previous_amount: Decimal
    frequency: str

class HOAIncreaseOut(BaseModel):
    id: int
    budget_id: int
    source_charge_id: int
    proposal_id: int
    member_user_id: int
    previous_amount: Decimal
    proposed_amount: Decimal
    effective_on: date
    new_board_decision_required: bool = True
    new_member_charge_posted: bool = False
