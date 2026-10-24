"""Commercial lease staff references and source-linked abstracted terms."""
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class CommercialLeaseAbstractIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lease_id: int = Field(ge=1)
    source_attachment_id: int | None = Field(default=None, ge=1)
    rent_commencement_on: date | None = None


class CommercialLeaseAbstractUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rent_commencement_on: date | None = None
    source_attachment_id: int | None = Field(default=None, ge=1)


class CommercialLeaseCandidateOut(BaseModel):
    lease_id: int
    unit_id: int
    unit_number: str
    lease_start_on: date
    lease_end_on: date
    lease_status: str


class CommercialLeaseSourceOut(BaseModel):
    id: int
    filename: str
    content_type: str
    size_bytes: int
    source_status: Literal["PRIVATE_STAFF_ATTACHMENT"] = "PRIVATE_STAFF_ATTACHMENT"


class CommercialLeaseAbstractOut(CommercialLeaseCandidateOut):
    id: int
    property_id: int
    rent_commencement_on: date | None
    source_attachment_id: int | None = None
    source_filename: str | None = None
    source_status: Literal["STAFF_LINKED_UNVERIFIED"] | None = None
    reference_status: str = "STAFF_RECORDED_UNVERIFIED"
    recorded_at: datetime


class CommercialRentEscalationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    starts_on: date
    monthly_base_rent: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class CommercialRentEscalationOut(CommercialRentEscalationIn):
    id: int


class CommercialLeaseOptionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    option_type: Literal["RENEWAL", "EXPANSION", "TERMINATION", "PURCHASE", "OTHER"]
    exercise_start_on: date | None = None
    exercise_end_on: date | None = None
    summary: str = Field(min_length=3, max_length=2000)

    @model_validator(mode="after")
    def valid_window(self):
        if (self.exercise_start_on is not None and self.exercise_end_on is not None
                and self.exercise_end_on < self.exercise_start_on):
            raise ValueError("Option exercise end cannot precede start.")
        return self


class CommercialLeaseOptionOut(CommercialLeaseOptionIn):
    id: int


class CommercialLeaseTermsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_attachment_id: int = Field(ge=1)
    effective_on: date
    base_rent_monthly: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    cam_estimate_monthly: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)
    property_tax_estimate_monthly: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)
    insurance_estimate_monthly: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)
    cam_share_percent: Decimal | None = Field(default=None, gt=0, le=100, max_digits=7, decimal_places=4)
    percentage_rent_rate: Decimal | None = Field(default=None, gt=0, le=100, max_digits=7, decimal_places=4)
    percentage_rent_breakpoint_annual: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    ti_allowance_total: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    co_tenancy_summary: str | None = Field(default=None, max_length=4000)
    escalations: list[CommercialRentEscalationIn] = Field(default_factory=list, max_length=50)
    options: list[CommercialLeaseOptionIn] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def paired_percentage_terms(self):
        if (self.percentage_rent_rate is None) != (self.percentage_rent_breakpoint_annual is None):
            raise ValueError("Percentage rent rate and annual breakpoint must be supplied together.")
        starts = [row.starts_on for row in self.escalations]
        if len(starts) != len(set(starts)):
            raise ValueError("Rent escalation start dates must be unique.")
        return self


class CommercialBillingAuthorizationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str = Field(min_length=10, max_length=2000)


class CommercialLeaseTermsOut(BaseModel):
    id: int
    abstract_id: int
    property_id: int
    lease_id: int
    revision: int
    source_attachment_id: int
    source_filename: str
    source_status: Literal["STAFF_LINKED_UNVERIFIED"] = "STAFF_LINKED_UNVERIFIED"
    effective_on: date
    base_rent_monthly: Decimal | None
    cam_estimate_monthly: Decimal
    property_tax_estimate_monthly: Decimal
    insurance_estimate_monthly: Decimal
    cam_share_percent: Decimal | None
    percentage_rent_rate: Decimal | None
    percentage_rent_breakpoint_annual: Decimal | None
    ti_allowance_total: Decimal | None
    co_tenancy_summary: str | None
    billing_authorized: bool = False
    billing_authorized_at: datetime | None = None
    billing_authorization_note: str | None = None
    escalations: list[CommercialRentEscalationOut]
    options: list[CommercialLeaseOptionOut]
    is_active: bool
    recorded_at: datetime
    terms_status: Literal["STAFF_ABSTRACTED_UNVERIFIED"] = "STAFF_ABSTRACTED_UNVERIFIED"
