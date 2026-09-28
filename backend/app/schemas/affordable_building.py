"""Agency-provided building identifiers; not a tax form, income certification or credit claim."""
from __future__ import annotations

import re
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


class AffordableBuildingIn(BaseModel):
    building_label: str = Field(min_length=1, max_length=100)
    agency_bin: str = Field(min_length=5, max_length=40)

    @field_validator("building_label")
    @classmethod
    def name_required(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("Building label required")
        return clean

    @field_validator("agency_bin")
    @classmethod
    def bin_reference(cls, value: str) -> str:
        clean = value.strip().upper()
        # Reject plain nine-digit identifiers (TINs). This is a conservative
        # shape check, NOT independent validation of an agency-assigned BIN.
        if not re.fullmatch(r"[A-Z]{2}[A-Z0-9-]{3,38}", clean):
            raise ValueError("Use the agency-issued alphanumeric building ID, beginning with its state prefix")
        return clean


class AffordableBuildingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    program_id: int
    building_label: str
    agency_bin: str
    created_at: datetime
