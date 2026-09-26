"""Only safe metadata is returned; signed document bytes are never JSON."""
from datetime import date, datetime

from pydantic import BaseModel


class TaxW9DocumentOut(BaseModel):
    id: int
    tax_profile_id: int
    size_bytes: int
    received_on: date
    uploaded_at: datetime
    uploaded_by_id: int | None
