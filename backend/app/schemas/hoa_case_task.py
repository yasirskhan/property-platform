"""Internal HOA violation follow-up task schemas."""
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

Kind = Literal["INSPECTION", "REMEDIATION", "REVIEW", "OTHER"]
Status = Literal["OPEN", "IN_PROGRESS", "DONE", "CANCELLED"]

class HOACaseTaskCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    request_key: str = Field(min_length=12, max_length=64)
    kind: Kind
    title: str = Field(min_length=3, max_length=160)
    details: str | None = Field(default=None, max_length=1500)
    assigned_user_id: int = Field(ge=1)
    due_on: date

    @field_validator("title")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Task title required.")
        return value.strip()

class HOACaseTaskTransitionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    expected_version: int = Field(ge=1)
    next_status: Literal["IN_PROGRESS", "DONE", "CANCELLED"]
    action_note: str | None = Field(default=None, max_length=600)

class HOACaseTaskAssigneeOut(BaseModel):
    id: int
    name: str
    role: Literal["ADMIN", "OWNER", "MANAGER"]

class HOACaseTaskOut(BaseModel):
    id: int
    case_id: int
    kind: Kind
    title: str
    details: str | None
    assigned_user_id: int
    due_on: date
    status: Status
    version: int
    completed_at: datetime | None
    result_note: str | None
    updated_at: datetime
    internal_only: Literal[True] = True
    notice_issued: Literal[False] = False
    fine_assessed: Literal[False] = False
