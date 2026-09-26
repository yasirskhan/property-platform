"""Schemas for the shared reporting framework."""
from __future__ import annotations

from typing import Literal
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


ReportTier = Literal["STANDARD", "ENHANCED"]
ReportPresentation = Literal["BUTTON", "TAB"]


class ReportDefinitionOut(BaseModel):
    key: str
    title: str
    category: str
    tier: ReportTier
    presentation: ReportPresentation
    available: bool
    href: str | None = None
    description: str | None = None


class ReportCatalogOut(BaseModel):
    accounting_basis: Literal["ACCRUAL", "CASH"]
    standard: list[ReportDefinitionOut]
    enhanced: list[ReportDefinitionOut]


class ReportEmailIn(BaseModel):
    recipient: EmailStr
    parameters: dict[str, str | int | bool | None] = Field(default_factory=dict)


class ReportEmailOut(BaseModel):
    sent: bool
    filename: str


class SavedReportIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    report_key: str = Field(min_length=1, max_length=100)
    parameters: dict[str, str | int | bool | None] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


class SavedReportOut(SavedReportIn):
    id: int
    organization_id: int
    created_at: datetime
    updated_at: __import__("datetime").datetime


class SavedReportListOut(BaseModel):
    items: list[SavedReportOut]
    total: int
