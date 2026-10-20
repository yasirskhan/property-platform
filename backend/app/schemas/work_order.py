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
    source_inspection_id: Optional[int] = Field(default=None, ge=1)
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
class WorkOrderVendorAssign(BaseModel):
    vendor_id: Optional[int] = Field(default=None, ge=1)


class WorkOrderVendorOut(BaseModel):
    id: int
    property_id: int
    title: str
    status: WorkOrderStatus
    assigned_to_id: Optional[int] = None
    vendor_id: Optional[int] = None


class WorkOrderReject(BaseModel):
    reason: str = Field(..., min_length=5, max_length=1000)


class WorkOrderTimeCreate(BaseModel):
    started_at: datetime
    ended_at: datetime
    notes: Optional[str] = Field(default=None, max_length=500)


class WorkOrderTimeOut(BaseModel):
    id: int
    work_order_id: int
    crew_user_id: int
    started_at: datetime
    ended_at: datetime
    duration_minutes: int
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PendingCrewTimeCorrectionOut(BaseModel):
    id: int
    work_order_id: int
    work_order_title: str
    property_id: int
    property_name: str
    time_entry_id: int
    requested_by_user_id: int
    original_minutes: int
    proposed_minutes: int
    reason: str
    created_at: datetime


class MaintenanceVendorPreferencesUpdate(BaseModel):
    vendor_ids: List[int] = Field(..., max_length=3)


class MaintenanceVendorPreferenceOut(BaseModel):
    vendor_id: int
    rank: int
    company_name: str
    trade: str
    insurance_status: str = 'MISSING'


class MaintenanceVendorCandidateOut(BaseModel):
    vendor_id: int
    company_name: str
    trade: Optional[str] = None
    insurance_status: str = 'MISSING'


class WorkOrderTimeLedgerOut(BaseModel):
    recorded_entries: int
    recorded_minutes: int
    reviewed_minutes: int
    approved_entries: int
    pending_corrections: int
    payroll_approved: bool = False


class WorkOrderTimeCorrectionCreate(BaseModel):
    started_at: datetime
    ended_at: datetime
    reason: str = Field(..., min_length=5, max_length=1000)


class WorkOrderTimeCorrectionDecision(BaseModel):
    approve: bool
    reason: str = Field(..., min_length=5, max_length=1000)


class WorkOrderTimeCorrectionOut(BaseModel):
    id: int
    work_order_id: int
    time_entry_id: int
    requested_by_user_id: int
    proposed_started_at: datetime
    proposed_ended_at: datetime
    duration_minutes: int
    reason: str
    status: str
    reviewed_by_user_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_reason: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True


class WorkOrderEta(BaseModel):
    """Arrival estimate submitted only by the currently accepted crew."""
    eta_at: datetime


class WorkOrderRecall(BaseModel):
    """Staff withdrawal of an unstarted crew offer (never a crew rejection)."""
    reason: str = Field(..., min_length=5, max_length=1000)


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
# WORK ORDER — CANCEL (reason optional for legacy API clients)
# ============================================================
class WorkOrderCancel(BaseModel):
    reason: Optional[str] = Field(default=None, min_length=5, max_length=1000)


# ============================================================
# WORK ORDER — OUTPUT
# ============================================================
class WorkOrderOut(BaseModel):
    id: int
    unit_id: int
    tenant_id: Optional[int]
    # Optional for old imported/historical rows; never silently substitute tenant_id.
    requested_by_user_id: Optional[int] = None
    property_id: int
    property_name: Optional[str] = None
    unit_number: Optional[str] = None
    assigned_to_id: Optional[int] = None
    assigned_at: Optional[datetime] = None
    assigned_by_id: Optional[int] = None
    assignment_response: Optional[str] = None
    assignment_responded_at: Optional[datetime] = None
    crew_eta_at: Optional[datetime] = None

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
    actor_name: Optional[str] = None
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
    # Only resolved for authorized inspection viewers. Suppressed for crew/tenants/owners.
    source_inspection_id: Optional[int] = None
    # Legacy ORM rows may have NULL until authorized provenance resolution.
    request_origin: Optional[str] = None
    requested_by_user_id: Optional[int] = None
    # Current inventory labels, not immutable historical snapshots.
    property_name: Optional[str] = None
    unit_number: Optional[str] = None
    updates: List[WorkOrderUpdateOut] = []


# ============================================================
# WORK ORDER — ADD COMMENT
# ============================================================
class WorkOrderComment(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)