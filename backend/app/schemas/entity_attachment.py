"""API contracts for universal entity attachments."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class EntityAttachmentOut(BaseModel):
    id: int
    organization_id: int
    entity_type: str
    entity_id: int
    original_name: str
    content_type: str
    size_bytes: int
    share_with_tenants: bool
    share_with_owners: bool
    uploaded_by_id: int | None
    uploaded_by_name: str | None
    created_at: datetime


class EntityAttachmentListOut(BaseModel):
    items: list[EntityAttachmentOut]
    total: int


class EntityAttachmentShareUpdate(BaseModel):
    share_with_tenants: bool | None = None
    share_with_owners: bool | None = None
