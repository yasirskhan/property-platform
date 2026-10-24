"""Validated, read-safe maintenance group and dispatch-policy settings."""
from pydantic import BaseModel, Field, field_validator

class MaintenanceGroupInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    timezone_name: str = Field(default="UTC", min_length=1, max_length=64)
    business_start_hour: int = Field(default=9, ge=0, le=23)
    business_end_hour: int = Field(default=17, ge=1, le=24)
    property_ids: list[int] = Field(default_factory=list, max_length=500)
    automation_requested: bool = False

    @field_validator("name")
    @classmethod
    def trim_name(cls, name: str) -> str:
        value = name.strip()
        if not value:
            raise ValueError("Group name is required")
        return value

    @field_validator("property_ids")
    @classmethod
    def distinct_properties(cls, ids: list[int]) -> list[int]:
        if any(type(n) is not int or n <= 0 for n in ids) or len(ids) != len(set(ids)):
            raise ValueError("Property IDs must be distinct positive integers")
        return ids

class MaintenanceRuleInput(BaseModel):
    first_target: str = Field(pattern="^(crew|vendor|manager)$")
    backup_target: str = Field(pattern="^(vendor|manager)$")
    timeout_minutes: int = Field(ge=1, le=1440)
    escalate: bool = False
    primary_contact_user_id: int | None = Field(default=None, ge=1)
    backup_contact_user_id: int | None = Field(default=None, ge=1)

class MaintenanceRuleOut(BaseModel):
    urgency: str
    daypart: str
    configured: bool
    first_target: str
    backup_target: str
    timeout_minutes: int
    escalate: bool
    primary_contact_user_id: int | None = None
    backup_contact_user_id: int | None = None

class MaintenanceGroupOut(BaseModel):
    id: int
    name: str
    is_default: bool
    timezone_name: str
    business_start_hour: int
    business_end_hour: int
    property_ids: list[int]
    automation_requested: bool = False
    rules: list[MaintenanceRuleOut]

class MaintenanceDispatchPropertyChoice(BaseModel):
    id: int
    name: str

class MaintenanceDispatchContactChoice(BaseModel):
    id: int
    name: str
