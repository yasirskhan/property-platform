"""Schemas for the shared reporting framework."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


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
