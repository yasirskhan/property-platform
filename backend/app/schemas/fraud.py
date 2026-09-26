"""Schemas for the internal fraud-review queue."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.fraud import FraudCaseStatus, FraudRiskLevel


class FraudSignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fraud_case_id: int
    organization_id: int | None
    source: str
    signal_type: str
    severity: FraudRiskLevel
    provider_event_id: str | None
    signal_value: str | None
    payload: dict[str, Any]
    created_at: datetime


class FraudCaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int | None
    checkout_session_id: int | None
    provider: str
    provider_case_id: str | None
    status: FraudCaseStatus
    risk_level: FraudRiskLevel
    risk_score: int | None
    reason: str
    details: dict[str, Any]
    reviewed_by_platform_user_id: int | None
    resolution_notes: str | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FraudCaseDetailOut(FraudCaseOut):
    signals: list[FraudSignalOut]


class FraudCaseReviewIn(BaseModel):
    status: FraudCaseStatus
    resolution_notes: str | None = Field(default=None, max_length=4000)
