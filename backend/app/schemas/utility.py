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