from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TwoFactorStatus(BaseModel):
    enabled: bool
    recovery_codes_remaining: int = 0
    verified_at: datetime | None = None


class TwoFactorSetupRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)


class TwoFactorSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
    recovery_codes: list[str]


class TwoFactorEnableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=32)


class TwoFactorDisableRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    code: str = Field(min_length=6, max_length=32)


class TwoFactorLoginVerifyRequest(BaseModel):
    challenge_token: str = Field(min_length=20)
    code: str = Field(min_length=6, max_length=32)
