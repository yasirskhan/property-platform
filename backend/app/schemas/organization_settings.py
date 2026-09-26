from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel


RetentionDays = Literal[30, 365, 2555] | None


class FoundationSettingsUpdate(BaseModel):
    locked_through_date: date | None = None
    data_region: str | None = None
    retention_policies: dict[str, RetentionDays] | None = None
