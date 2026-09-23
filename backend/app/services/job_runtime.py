"""Durable job lifecycle helpers.

Ordering rule:
1. Reserve/commit the JobRun first.
2. Dispatch to Redis/Arq.
3. Mark QUEUED only after Redis confirms enqueue.
If dispatch fails, the durable row remains PENDING for scheduler recovery.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.job_run import JobDeadLetter, JobRun, JobStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


def reserve_job_run(
    db: Session,
    *,
    job_name: str,
    idempotency_key: str,
    payload: dict[str, Any] | None = None,
    max_attempts: int = 5,
    scheduled_for: datetime | None = None,
) -> tuple[JobRun, bool]:
    name = job_name.strip()
    key = idempotency_key.strip()
    if not name:
        raise ValueError("job_name is required")
    if not key:
        raise ValueError("idempotency_key is required")
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    existing = (
        db.query(JobRun)
        .filter(
            JobRun.job_name == name,
            JobRun.idempotency_key == key,
        )
        .first()
    )
    if existing is not None:
        return existing, False

    row = JobRun(
        job_name=name,
        idempotency_key=key,
        payload=payload or {},
        max_attempts=max_attempts,
        scheduled_for=scheduled_for,
        status=JobStatus.PENDING,
    )
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
        return row, True
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(JobRun)
            .filter(
                JobRun.job_name == name,
                JobRun.idempotency_key == key,
            )
            .one()
        )
        return existing, False


def mark_job_queued(db: Session, row: JobRun, *, arq_job_id: str) -> None:
    row.status = JobStatus.QUEUED
    row.arq_job_id = arq_job_id
    row.last_error = None
    db.commit()
    db.refresh(row)


def mark_job_running(db: Session, row: JobRun) -> None:
    row.status = JobStatus.RUNNING
    row.attempts += 1
    row.started_at = _now()
    row.next_retry_at = None
    db.commit()
    db.refresh(row)


def mark_job_retrying(
    db: Session,
    row: JobRun,
    *,
    error: str,
    next_retry_at: datetime,
) -> None:
    row.status = JobStatus.RETRYING
    row.last_error = error
    row.next_retry_at = next_retry_at
    db.commit()
    db.refresh(row)


def mark_job_succeeded(
    db: Session,
    row: JobRun,
    *,
    result: Any = None,
) -> None:
    row.status = JobStatus.SUCCEEDED
    row.result = result
    row.last_error = None
    row.next_retry_at = None
    row.completed_at = _now()
    db.commit()
    db.refresh(row)


def mark_job_dead_letter(
    db: Session,
    row: JobRun,
    *,
    error: str,
) -> JobDeadLetter:
    row.status = JobStatus.DEAD_LETTER
    row.last_error = error
    row.next_retry_at = None
    row.completed_at = _now()

    dead = (
        db.query(JobDeadLetter)
        .filter(JobDeadLetter.job_run_id == row.id)
        .first()
    )
    if dead is None:
        dead = JobDeadLetter(
            job_run_id=row.id,
            job_name=row.job_name,
            idempotency_key=row.idempotency_key,
            attempts=row.attempts,
            payload=row.payload or {},
            error=error,
        )
        db.add(dead)
    else:
        dead.attempts = row.attempts
        dead.error = error

    db.commit()
    db.refresh(row)
    db.refresh(dead)
    return dead
