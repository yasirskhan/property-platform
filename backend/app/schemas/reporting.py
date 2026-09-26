"""Schemas for the shared reporting framework."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


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
