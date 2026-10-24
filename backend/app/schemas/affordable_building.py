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
        # IRS Notice 88-91: state prefix, allocation year (2 digits;
        # IRS also accepts 4-digit year), and exactly five sequence digits.
        # Normalize formatting aliases to one value for duplicate checks.
        # Shape validation is NOT verification of an agency-issued Form 8609.
        match = re.fullmatch(r"([A-Z]{2})-?((?:19|20)[0-9]{2}|[0-9]{2})-?([0-9]{5})", clean)
        if match is None:
            raise ValueError("BIN must have a two-letter state, 2- or 4-digit year and five digits")
        state, year, sequence = match.groups()
        return f"{state}-{year[-2:]}-{sequence}"


class AffordableBuildingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    program_id: int
    building_label: str
    agency_bin: str
    created_at: datetime
