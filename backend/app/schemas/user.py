# ============================================================
# schemas/user.py
# ------------------------------------------------------------
# These are "schemas" — they define the shape of data
# going in and out of the API.
#
# Nothing here talks to the database directly.
# They are just validation + formatting rules.
# ============================================================

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


# ------------------------------------------------------------
# Base schema — fields shared by other user schemas
# ------------------------------------------------------------
class UserBase(BaseModel):
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = None


# ------------------------------------------------------------
# Schema for CREATING a user (signup)
# Includes password — will never be returned to client.
# ------------------------------------------------------------
class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole = UserRole.TENANT
    organization_id: Optional[int] = None


# ------------------------------------------------------------
# Schema for UPDATING a user
# All fields optional so client can send only what changed.
# ------------------------------------------------------------
class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None


# ------------------------------------------------------------
# Schema for RETURNING a user to the client
# Notice: NO password field. Ever.
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
        from_attributes = True  # lets Pydantic read SQLAlchemy objects