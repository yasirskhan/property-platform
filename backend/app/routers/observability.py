"""Bounded browser-error relay into optional Sentry monitoring."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.observability import capture_frontend_error


router = APIRouter(prefix="/api/observability", tags=["Observability"])


class ClientErrorIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    stack: str | None = Field(default=None, max_length=12000)
    path: str | None = Field(default=None, max_length=500)


@router.post("/client-error")
def report_client_error(payload: ClientErrorIn) -> dict[str, bool]:
    event_id = capture_frontend_error(
        message=payload.message,
        stack=payload.stack,
        path=payload.path,
    )
    return {"accepted": event_id is not None}
