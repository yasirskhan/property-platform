"""Scoped, read-only work-order dispatch attention entries."""
from datetime import datetime
from pydantic import BaseModel


class MaintenanceDispatchAttentionOut(BaseModel):
    work_order_id: int
    property_id: int
    property_name: str
    title: str
    priority: str
    status: str
    attention_code: str
    explanation: str
    next_action: str
    assigned_to_id: int | None = None
    assignment_response: str | None = None
    response_due_at: datetime | None = None
    policy_group: str | None = None
    policy_daypart: str | None = None
    policy_configured: bool = False
    primary_target: str | None = None
    backup_target: str | None = None
