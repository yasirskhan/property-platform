"""Fixed staff evidence-index categories; no PII, household data, or certifications."""
from __future__ import annotations

from datetime import date, datetime
from ipaddress import ip_address
from urllib.parse import urlsplit
from typing import Literal
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

Category = Literal["AGENCY_GUIDANCE", "PROGRAM_AGREEMENT", "PROPERTY_RECORD_INDEX", "INSPECTION_COORDINATION"]
Readiness = Literal["NOT_RECORDED", "FOLLOW_UP_NEEDED", "REFERENCE_IDENTIFIED"]


class AffordableEvidenceIn(BaseModel):
    category: Category
    status: Readiness
    staff_follow_up_on: date | None = None
    source_url: str | None = None
    source_checked_on: date | None = None

    @field_validator("source_url")
    @classmethod
    def public_https_reference(cls, raw: str | None) -> str | None:
        if raw is None:
            return None
        url = raw.strip()
        if not url:
            return None
        if len(url) > 500 or any(char.isspace() or char == "\\\\" for char in url):
            raise ValueError("Agency reference must be a bounded public HTTPS URL")
        try:
            value = urlsplit(url)
            host = (value.hostname or "").lower().rstrip(".")
            port = value.port
        except ValueError as exc:
            raise ValueError("Invalid agency reference URL") from exc
        if (value.scheme.lower() != "https" or not host or port not in (None, 443)
                or value.username is not None or value.password is not None
                or host in {"localhost", "localhost.localdomain"}
                or host.endswith((".local", ".internal", ".test", ".example"))
                or "." not in host):
            raise ValueError("Agency reference must be a public HTTPS URL")
        try:
            ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError("IP-address references are not permitted")
        return url

    @model_validator(mode="after")
    def staff_reference_only(self):
        if self.source_url and (self.category != "AGENCY_GUIDANCE"
                                or self.status == "NOT_RECORDED"):
            raise ValueError("Only recorded agency guidance accepts a public source URL")
        if self.source_checked_on is not None:
            if not self.source_url:
                raise ValueError("A checked date requires a public reference URL")
            if self.source_checked_on > date.today():
                raise ValueError("A staff-check date cannot be in the future")
        return self


class AffordableEvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    category: Category
    status: Readiness
    staff_follow_up_on: date | None
    source_url: str | None = None
    source_checked_on: date | None = None
    updated_at: datetime | None = None


class StaffInspectionSummaryOut(BaseModel):
    """Existing general staff inspection records; NOT program-specific HQS."""
    total_recorded: int
    latest_recorded_on: date | None
