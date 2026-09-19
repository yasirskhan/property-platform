# ============================================================
# schemas/work_order.py
# ------------------------------------------------------------
# Shapes for work order data going in and out of the API.
# ============================================================

from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field

from app.models.work_order import (
    WorkOrderCategory,
    WorkOrderPriority,
    WorkOrderStatus,
)


# ============================================================
# WORK ORDER — CREATE
# ============================================================
class WorkOrderCreate(BaseModel):
    """What a tenant (or manager) sends to submit a work order."""
    unit_id: int
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=10)
    category: WorkOrderCategory = WorkOrderCategory.OTHER
    priority: WorkOrderPriority = WorkOrderPriority.MEDIUM
    permission_to_enter: bool = False
    entry_notes: Optional[str] = None
    photo_urls: Optional[str] = None  # comma-separated for now


# ============================================================
# WORK ORDER — UPDATE (partial)
# ============================================================
class WorkOrderUpdateFields(BaseModel):
    """Fields a manager can change on a work order."""
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[WorkOrderCategory] = None
    priority: Optional[WorkOrderPriority] = None
    status: Optional[WorkOrderStatus] = None
    resolution_notes: Optional[str] = None


# ============================================================
# WORK ORDER — ASSIGN
# ============================================================
class WorkOrderAssign(BaseModel):
    """Payload to assign a work order to a crew member."""
    crew_user_id: int


# ============================================================
# WORK ORDER — COMPLETE
# ============================================================
class WorkOrderComplete(BaseModel):
    """Payload from crew when marking work complete."""
    resolution_notes: Optional[str] = None
    labor_cost: Optional[Decimal] = Field(None, ge=0)
    materials_cost: Optional[Decimal] = Field(None, ge=0)


# ============================================================
# WORK ORDER — OUTPUT
# ============================================================
class WorkOrderOut(BaseModel):
    id: int
    unit_id: int
    tenant_id: int
    property_id: int
    assigned_to_id: Optional[int] = None
    assigned_at: Optional[datetime] = None
    assigned_by_id: Optional[int] = None

    title: str
    description: str
    category: WorkOrderCategory
    priority: WorkOrderPriority
    status: WorkOrderStatus

    permission_to_enter: bool
    entry_notes: Optional[str] = None
    photo_urls: Optional[str] = None

    labor_cost: Optional[Decimal] = None
    materials_cost: Optional[Decimal] = None
    total_cost: Optional[Decimal] = None
    resolution_notes: Optional[str] = None

    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================================
# UPDATE LOG — OUTPUT
# ============================================================
class WorkOrderUpdateOut(BaseModel):
    id: int
    work_order_id: int
    user_id: int
    from_status: Optional[WorkOrderStatus] = None
    to_status: Optional[WorkOrderStatus] = None
    message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# WORK ORDER — WITH UPDATES (nested output)
# ============================================================
class WorkOrderDetail(WorkOrderOut):
    updates: List[WorkOrderUpdateOut] = []


# ============================================================
# WORK ORDER — ADD COMMENT
# ============================================================
class WorkOrderComment(BaseModel):
    message: str = Field(..., min_length=1)