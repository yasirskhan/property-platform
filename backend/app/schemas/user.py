# ============================================================
# schemas/user.py
# ------------------------------------------------------------
# Shape of data going in and out of the users API.
#
# Nothing here talks to the database directly.
# These are just validation + formatting rules.
# ============================================================

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


# ------------------------------------------------------------
# Base — fields shared by other user schemas
# ------------------------------------------------------------
class UserBase(BaseModel):
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = None


# ------------------------------------------------------------
# CREATE — used by signup
#
# Two signup paths:
#
#  1. Brand-new company (ADMIN or OWNER with no organization_id):
#     must include `organization_name`. The backend creates
#     the organization and links the user to it.
#
#  2. Invited user (any role WITH organization_id):
#     joins an existing organization. `organization_name` ignored.
#
#  Anything else is refused by create_user().
# ------------------------------------------------------------
class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole = UserRole.TENANT
    organization_id: Optional[int] = None
    organization_name: Optional[str] = Field(None, min_length=2, max_length=255)


# ------------------------------------------------------------
# UPDATE
# ------------------------------------------------------------
class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None


# ------------------------------------------------------------
# OUT — returned to the client. No password field ever.
# ------------------------------------------------------------
class UserOut(UserBase):
    id: int
    role: UserRole
    organization_id: Optional[int] = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    profile_photo_url: Optional[str] = None

    class Config:
        from_attributes = True