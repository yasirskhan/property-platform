"""Schemas for internal platform authentication and release control."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.platform_user import PlatformUserRole
from app.models.release_gate import ReleaseStage


class PlatformLoginRequest(BaseModel):
    email: EmailStr
    password: str


class PlatformUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    first_name: str
    last_name: str
    role: PlatformUserRole
    is_active: bool


class ReleaseGateUpdateIn(BaseModel):
    stage: ReleaseStage
    organization_ids: list[int] = Field(default_factory=list)


class ReleaseGateOut(BaseModel):
    key: str
    stage: ReleaseStage
    organization_ids: list[int]
    updated_at: datetime
