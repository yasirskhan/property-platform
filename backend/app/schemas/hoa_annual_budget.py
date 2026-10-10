"""HOA annual operating budgets, explicit board decisions and stable snapshots."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HOAAnnualBudgetLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gl_account_id: int = Field(ge=1)
    annual_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class HOAAnnualBudgetLineOut(HOAAnnualBudgetLineIn):
    gl_number: str
    gl_name: str
    account_type: Literal["INCOME", "EXPENSE"]


class HOAAnnualBudgetCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    calendar_year: int = Field(ge=2000, le=2100)
    description: str = Field(min_length=3, max_length=300)
    lines: list[HOAAnnualBudgetLineIn] = Field(min_length=1, max_length=100)
    reserve_allocation: Decimal = Field(ge=0, max_digits=14, decimal_places=2)

    @field_validator("description")
    @classmethod
    def trim_description(cls, text: str) -> str:
        text = text.strip()
        if len(text) < 3:
            raise ValueError("Budget description required.")
        return text

    @model_validator(mode="after")
    def distinct_accounts(self):
        ids = [r.gl_account_id for r in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("Use one annual line per GL account.")
        return self


class HOAAnnualBudgetReviseIn(HOAAnnualBudgetCreateIn):
    expected_version: int = Field(ge=1)


class HOAAnnualBudgetDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    expected_version: int = Field(ge=1)
    decision: Literal["APPROVED", "DENIED"]
    decision_note: str = Field(min_length=3, max_length=1500)
    offline_meeting_on: date | None = None
    decision_maker_seat_id: int | None = Field(default=None, ge=1)
    supporting_attachment_id: int | None = Field(default=None, ge=1)

    @field_validator("decision_note")
    @classmethod
    def trim_note(cls, text: str) -> str:
        if len(text.strip()) < 3:
            raise ValueError("An association decision note is required.")
        return text.strip()

    @model_validator(mode="after")
    def record_method(self):
        has_offline = self.offline_meeting_on is not None
        if has_offline != (self.decision_maker_seat_id is not None):
            raise ValueError("Offline decision requires a named board member.")
        if has_offline != (self.supporting_attachment_id is not None):
            raise ValueError("Offline decision requires a private board meeting record.")
        return self


class HOAAnnualBudgetOut(BaseModel):
    id: int
    property_id: int
    calendar_year: int
    revision: int
    version: int
    description: str
    lines: list[HOAAnnualBudgetLineOut]
    total_income: Decimal
    total_expense: Decimal
    reserve_allocation: Decimal
    status: Literal["DRAFT", "APPROVED", "DENIED"]
    board_seat_id: int | None
    decision_maker_seat_id: int | None
    decision_method: Literal["DIRECT", "OFFLINE"] | None
    decided_on: date | None
    decision_note: str | None
    created_at: datetime
    # Approval of an operating budget does not itself bill any member.
    member_assessment_issued: Literal[False] = False
    reserve_cash_transferred: Literal[False] = False


class HOAAnnualBudgetAccountOut(BaseModel):
    id: int
    number: str
    name: str
    account_type: Literal["INCOME", "EXPENSE"]
