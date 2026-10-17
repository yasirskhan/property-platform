"""Schemas for internal background-job monitoring."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.job_run import JobStatus


class JobRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_name: str
    idempotency_key: str
    status: JobStatus
    payload: dict[str, Any]
    result: Any | None
    attempts: int
    max_attempts: int
    arq_job_id: str | None
    scheduled_for: datetime | None
    next_retry_at: datetime | None
    last_error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class JobDeadLetterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_run_id: int
    job_name: str
    idempotency_key: str
    attempts: int
    payload: dict[str, Any]
    error: str
    created_at: datetime


class JobSummaryOut(BaseModel):
    counts: dict[str, int]
    dead_letters: int
