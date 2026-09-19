# ============================================================
# schemas/org_email.py
# ============================================================

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class OrgEmailSettingsBase(BaseModel):
    from_email: EmailStr
    from_name: str = Field("", max_length=255)
    reply_to_email: Optional[EmailStr] = None
    smtp_host: str = Field(..., min_length=1, max_length=255)
    smtp_port: int = Field(587, ge=1, le=65535)
    smtp_user: str = Field(..., min_length=1, max_length=255)
    smtp_use_tls: bool = True


class OrgEmailSettingsCreate(OrgEmailSettingsBase):
    smtp_password: str = Field(..., min_length=1)
    is_enabled: bool = True


class OrgEmailSettingsUpdate(BaseModel):
    from_email: Optional[EmailStr] = None
    from_name: Optional[str] = None
    reply_to_email: Optional[EmailStr] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: Optional[bool] = None
    is_enabled: Optional[bool] = None


class OrgEmailSettingsOut(OrgEmailSettingsBase):
    id: int
    organization_id: int
    is_enabled: bool
    last_test_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TestEmailRequest(BaseModel):
    to: EmailStr


class MessageResponse(BaseModel):
    detail: str
    success: bool = True