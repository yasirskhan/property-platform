from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class AuditCenterItem(BaseModel):
    id: int
    actor_type: str
    actor_id: Optional[int] = None
    actor_name: str
    actor_email: Optional[str] = None
    entity_type: str
    entity_id: int
    action: str
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime

class AuditCenterList(BaseModel):
    items: list[AuditCenterItem]
    total: int
    limit: int
    offset: int
