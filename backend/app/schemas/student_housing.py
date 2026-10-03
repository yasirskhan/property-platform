from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, model_validator


class AcademicCycleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("Academic cycle end date must be on or after the start date.")
        return self


class AcademicCycleOut(BaseModel):
    id: int
    property_id: int
    name: str
    start_date: date
    end_date: date
    is_active: bool
    created_at: datetime


class StudentBedCreate(BaseModel):
    unit_id: int = Field(..., gt=0)
    bed_label: str = Field(..., min_length=1, max_length=80)


class StudentBedOut(BaseModel):
    id: int
    property_id: int
    unit_id: int
    bed_label: str
    is_active: bool
    created_at: datetime


class StudentBedLeaseCreate(BaseModel):
    bed_id: int = Field(..., gt=0)
    tenant_id: int = Field(..., gt=0)
    academic_cycle_id: int = Field(..., gt=0)
    start_date: date
    end_date: date
    monthly_rent: Decimal = Field(..., ge=0)
    security_deposit: Decimal = Field(Decimal("0.00"), ge=0)
    due_day: int = Field(1, ge=1, le=28)
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date <= self.start_date:
            raise ValueError("Student bed lease end date must be after the start date.")
        return self


class StudentBedLeaseOut(BaseModel):
    id: int
    property_id: int
    unit_id: int
    bed_id: int
    bed_label: str
    tenant_id: int
    tenant_name: str
    tenant_email: str
    academic_cycle_id: int
    academic_cycle_name: str
    start_date: date
    end_date: date
    monthly_rent: Decimal
    security_deposit: Decimal
    due_day: int
    status: str
    signed_by_tenant: bool
    signed_by_manager: bool
    created_at: datetime


class StudentGuarantorCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=50)
    relationship_to_tenant: str | None = Field(default=None, max_length=100)


class StudentGuarantorOut(BaseModel):
    id: int
    property_id: int
    lease_id: int
    full_name: str
    email: str
    phone: str | None
    relationship_to_tenant: str | None
    status: str
    requested_at: datetime | None
    received_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime


class StudentHousingContextOut(BaseModel):
    units: list[dict[str, object]]
    tenants: list[dict[str, object]]
