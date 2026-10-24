"""Human-reviewed maintenance dispatch follow-up, not external delivery."""
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class DispatchReviewOpen(BaseModel):
    reason: str = Field(min_length=12, max_length=1000)

    @field_validator("reason")
    @classmethod
    def require_reason(cls, value: str) -> str:
        if len(value.strip()) < 12:
            raise ValueError("Explain the dispatch issue in at least 12 characters")
        return value.strip()


class DispatchReviewClose(BaseModel):
    resolution_note: str = Field(min_length=12, max_length=1000)

    @field_validator("resolution_note")
    @classmethod
    def require_resolution(cls, value: str) -> str:
        if len(value.strip()) < 12:
            raise ValueError("Document the review outcome in at least 12 characters")
        return value.strip()


class DispatchReviewOut(BaseModel):
    id: int
    organization_id: int
    work_order_id: int
    status: str
    reason: str
    opened_by_user_id: int
    created_at: datetime
    closed_by_user_id: int | None = None
    closed_at: datetime | None = None
    resolution_note: str | None = None
    externally_notified: bool = False

    class Config:
        from_attributes = True
