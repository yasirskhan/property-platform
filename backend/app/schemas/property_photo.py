# ============================================================
# property_photo.py (schemas)
# ------------------------------------------------------------
# Pydantic shapes for Property Photos.
#
# Two-step upload:
#   1. POST /uploads -> {url, filename, original_name, size, content_type}
#   2. POST /api/properties/{pid}/photos with that data
# ============================================================

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class PropertyPhotoCreateIn(BaseModel):
    property_id: int
    url: str = Field(..., min_length=1, max_length=500)
    filename: str = Field(..., min_length=1, max_length=200)
    original_name: Optional[str] = Field(None, max_length=300)
    content_type: Optional[str] = Field(None, max_length=80)
    size_bytes: Optional[int] = None
    caption: Optional[str] = Field(None, max_length=500)
    is_marketing: bool = False
    is_cover: bool = False
    sort_order: int = 0


class PropertyPhotoUpdateIn(BaseModel):
    caption: Optional[str] = Field(None, max_length=500)
    is_marketing: Optional[bool] = None
    is_cover: Optional[bool] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    delete_reason: Optional[str] = None


class PropertyPhotoOut(BaseModel):
    id: int
    organization_id: int
    property_id: int
    url: str
    filename: str
    original_name: Optional[str] = None
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    caption: Optional[str] = None
    is_marketing: bool
    is_cover: bool
    sort_order: int
    is_active: bool
    delete_reason: Optional[str] = None
    created_by_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PropertyPhotoListOut(BaseModel):
    items: List[PropertyPhotoOut]
    total: int