from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


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
