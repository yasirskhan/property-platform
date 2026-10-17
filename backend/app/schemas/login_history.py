from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LoginHistoryItem(BaseModel):
    id: int
    status: str
    auth_method: str
    reason: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime
