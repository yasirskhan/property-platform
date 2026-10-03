# ============================================================
# schemas/utility.py
# ============================================================

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field

from app.models.utility import UtilityType, PaidBy, PickupType


# ------------------------------------------------------------
# PROPERTY UTILITY
# ------------------------------------------------------------
class PropertyUtilityBase(BaseModel):
    utility_type: UtilityType
    company_name: str = Field(..., min_length=1, max_length=255)
    company_phone: Optional[str] = None
    company_website: Optional[str] = None
    paid_by: PaidBy = PaidBy.TENANT
    setup_instructions: Optional[str] = None


class PropertyUtilityCreate(PropertyUtilityBase):
    account_number: Optional[str] = None
    account_holder_name: Optional[str] = None
    internal_notes: Optional[str] = None


class PropertyUtilityUpdate(BaseModel):
    utility_type: Optional[UtilityType] = None
    company_name: Optional[str] = None
    company_phone: Optional[str] = None
    company_website: Optional[str] = None
    paid_by: Optional[PaidBy] = None
    account_number: Optional[str] = None
    account_holder_name: Optional[str] = None
    setup_instructions: Optional[str] = None
    internal_notes: Optional[str] = None
    is_active: Optional[bool] = None


class PropertyUtilityOut(PropertyUtilityBase):
    id: int
    property_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PropertyUtilityAdminOut(PropertyUtilityOut):
    """Full version with account details — for owner/manager/admin only."""
    account_number: Optional[str] = None
    account_holder_name: Optional[str] = None
    internal_notes: Optional[str] = None


# ------------------------------------------------------------
# UTILITY BILL
# ------------------------------------------------------------
class UtilityBillBase(BaseModel):
    billing_period_start: Optional[date] = None
    billing_period_end: Optional[date] = None
    due_date: Optional[date] = None
    amount: Decimal = Field(..., gt=0)
    paid_at: Optional[date] = None
    invoice_url: Optional[str] = None
    notes: Optional[str] = None


class UtilityBillCreate(UtilityBillBase):
    pass


class UtilityBillOut(UtilityBillBase):
    id: int
    utility_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# RUBs METER READINGS
# ------------------------------------------------------------
class MeterReadingCreate(BaseModel):
    meter_identifier: str = Field(..., min_length=1, max_length=120)
    reading_date: date
    reading_value: Decimal = Field(..., ge=0)
    unit_of_measure: str = Field(..., min_length=1, max_length=32)
    unit_id: Optional[int] = Field(default=None, gt=0)
    notes: Optional[str] = Field(default=None, max_length=1000)
    request_key: str = Field(..., min_length=8, max_length=96)


class MeterReadingImportRow(BaseModel):
    meter_identifier: str = Field(..., min_length=1, max_length=120)
    reading_date: date
    reading_value: Decimal = Field(..., ge=0)
    unit_of_measure: str = Field(..., min_length=1, max_length=32)
    unit_id: Optional[int] = Field(default=None, gt=0)
    notes: Optional[str] = Field(default=None, max_length=1000)


class MeterReadingCSVImport(BaseModel):
    request_key: str = Field(..., min_length=8, max_length=96)
    csv_text: str = Field(..., min_length=1, max_length=1_000_000)


class MeterReadingOut(BaseModel):
    id: int
    utility_id: int
    unit_id: Optional[int] = None
    meter_identifier: str
    reading_date: date
    reading_value: Decimal
    unit_of_measure: str
    source: str
    import_batch_key: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MeterReadingImportResult(BaseModel):
    created: int
    replayed: int
    total: int
    readings: List[MeterReadingOut]


# ------------------------------------------------------------
# RUBs ALLOCATION RULES / PREVIEW
# ------------------------------------------------------------
class AllocationUnitInput(BaseModel):
    unit_id: int = Field(..., gt=0)
    weight: Optional[Decimal] = Field(default=None, gt=0)


class AllocationRuleCreate(BaseModel):
    basis: str = Field(..., pattern="^(SQUARE_FEET|OCCUPANCY|FIXTURES|MANUAL_WEIGHT)$")
    effective_date: date
    units: List[AllocationUnitInput] = Field(..., min_length=1, max_length=500)
    request_key: str = Field(..., min_length=8, max_length=96)


class AllocationRuleAuthorize(BaseModel):
    request_key: str = Field(..., min_length=8, max_length=96)


class AllocationRuleOut(BaseModel):
    id: int
    utility_id: int
    revision_number: int
    effective_date: date
    basis: str
    unit_inputs: List[AllocationUnitInput]
    status: str
    is_authorized: bool
    authorized_at: Optional[datetime] = None
    created_at: datetime


class AllocationPreviewRequest(BaseModel):
    rule_revision_id: int = Field(..., gt=0)
    bill_id: int = Field(..., gt=0)


class AllocationSnapshotSave(BaseModel):
    rule_revision_id: int = Field(..., gt=0)
    bill_id: int = Field(..., gt=0)
    request_key: str = Field(..., min_length=8, max_length=96)


class AllocationSnapshotItem(BaseModel):
    unit_id: int
    weight: Decimal
    share: Decimal
    amount: Decimal


class AllocationSnapshotOut(BaseModel):
    id: int
    utility_id: int
    bill_id: int
    rule_revision_id: int
    billing_period_start: date
    billing_period_end: date
    bill_amount: Decimal
    basis: str
    unit_inputs: List[AllocationUnitInput]
    items: List[AllocationSnapshotItem]
    allocated_total: Decimal
    remainder_rule: str
    reviewed_at: datetime


class TrueUpUnitWeight(BaseModel):
    unit_id: int = Field(..., gt=0)
    weight: Decimal = Field(..., gt=0)


class TrueUpPreviewRequest(BaseModel):
    period_start: date
    period_end: date
    snapshot_ids: List[int] = Field(..., min_length=1, max_length=500)
    actual_total: Decimal = Field(..., ge=0)
    unit_weights: List[TrueUpUnitWeight] = Field(..., min_length=1, max_length=500)


# ------------------------------------------------------------
# TRASH SCHEDULE
# ------------------------------------------------------------
class TrashScheduleBase(BaseModel):
    pickup_type: PickupType = PickupType.TRASH
    day_of_week: str = Field(..., min_length=3, max_length=20)
    frequency: str = "weekly"
    time_window: Optional[str] = None
    notes: Optional[str] = None


class TrashScheduleCreate(TrashScheduleBase):
    pass


class TrashScheduleUpdate(BaseModel):
    pickup_type: Optional[PickupType] = None
    day_of_week: Optional[str] = None
    frequency: Optional[str] = None
    time_window: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class TrashScheduleOut(TrashScheduleBase):
    id: int
    property_id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# NESTED
# ------------------------------------------------------------
class PropertyUtilityWithBills(PropertyUtilityAdminOut):
    bills: List[UtilityBillOut] = []