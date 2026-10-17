"""Redis/Arq producer helpers for durable JobRun records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.job_run import JobRun, JobStatus
from app.services.job_runtime import mark_job_queued, reserve_job_run


def get_redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.REDIS_URL)


async def create_job_pool() -> ArqRedis:
    return await create_pool(
        get_redis_settings(),
        default_queue_name=settings.JOB_QUEUE_NAME,
    )


def stable_arq_job_id(row: JobRun) -> str:
    return f"property-platform:job-run:{row.id}"


async def enqueue_job_run(
    db: Session,
    redis: ArqRedis,
    row: JobRun,
) -> JobRun:
    if row.status in {JobStatus.SUCCEEDED, JobStatus.DEAD_LETTER}:
        return row

    job_id = stable_arq_job_id(row)
    defer_until = row.scheduled_for
    if defer_until is not None:
        now = datetime.now(timezone.utc)
        if defer_until.tzinfo is None:
            defer_until = defer_until.replace(tzinfo=timezone.utc)
        if defer_until <= now:
            defer_until = None

    await redis.enqueue_job(
        "execute_job",
        row.id,
        _job_id=job_id,
        _queue_name=settings.JOB_QUEUE_NAME,
        _defer_until=defer_until,
    )
    mark_job_queued(db, row, arq_job_id=job_id)
    return row


async def submit_job(
    db: Session,
    redis: ArqRedis,
    *,
    job_name: str,
    idempotency_key: str,
    payload: dict[str, Any] | None = None,
    max_attempts: int = 5,
    scheduled_for: datetime | None = None,
) -> tuple[JobRun, bool]:
    row, created = reserve_job_run(
        db,
        job_name=job_name,
        idempotency_key=idempotency_key,
        payload=payload,
        max_attempts=max_attempts,
        scheduled_for=scheduled_for,
    )
    if row.status not in {JobStatus.SUCCEEDED, JobStatus.DEAD_LETTER}:
        await enqueue_job_run(db, redis, row)
    return row, created
