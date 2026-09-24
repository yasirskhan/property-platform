"""Arq worker, retry policy, cron recovery, and dead-letter handling."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from arq import Retry, cron
from sqlalchemy import or_

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.observability import capture_exception, init_sentry
from app.jobs import handlers  # noqa: F401 - registers built-in handlers
from app.jobs.queue import enqueue_job_run, get_redis_settings, stable_arq_job_id
from app.jobs.registry import get_job_handler
from app.models.job_run import JobRun, JobStatus
from app.services.job_runtime import (
    mark_job_dead_letter,
    mark_job_queued,
    mark_job_retrying,
    mark_job_running,
    mark_job_succeeded,
    reserve_job_run,
)


def retry_delay_seconds(attempt: int) -> int:
    return min(300, 5 * (2 ** max(attempt - 1, 0)))


async def worker_startup(_ctx) -> None:
    init_sentry()


async def execute_job(ctx, job_run_id: int):
    db = SessionLocal()
    try:
        row = db.query(JobRun).filter(JobRun.id == job_run_id).first()
        if row is None:
            return {"missing_job_run": job_run_id}
        if row.status == JobStatus.SUCCEEDED:
            return row.result
        if row.status == JobStatus.DEAD_LETTER:
            return {"dead_letter": True, "job_run_id": row.id}

        handler = get_job_handler(row.job_name)
        if handler is None:
            dead = mark_job_dead_letter(
                db,
                row,
                error=f"Unknown job handler: {row.job_name}",
            )
            return {"dead_letter_id": dead.id}

        mark_job_running(db, row)
        try:
            result = await handler(dict(row.payload or {}))
        except Exception as exc:
            capture_exception(exc)
            error = f"{type(exc).__name__}: {exc}"
            if row.attempts >= row.max_attempts:
                dead = mark_job_dead_letter(db, row, error=error)
                return {"dead_letter_id": dead.id}

            delay = retry_delay_seconds(row.attempts)
            next_retry = datetime.now(timezone.utc) + timedelta(seconds=delay)
            mark_job_retrying(
                db,
                row,
                error=error,
                next_retry_at=next_retry,
            )
            raise Retry(defer=delay)

        mark_job_succeeded(db, row, result=result)
        return result
    finally:
        db.close()


async def recover_pending_jobs(ctx):
    """Cron sweep for DB-first jobs whose Redis dispatch was lost."""
    redis = ctx["redis"]
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        rows = (
            db.query(JobRun)
            .filter(
                or_(
                    JobRun.status == JobStatus.PENDING,
                    JobRun.status == JobStatus.RETRYING,
                ),
                or_(
                    JobRun.scheduled_for.is_(None),
                    JobRun.scheduled_for <= now,
                ),
                or_(
                    JobRun.next_retry_at.is_(None),
                    JobRun.next_retry_at <= now,
                ),
            )
            .order_by(JobRun.id.asc())
            .limit(200)
            .all()
        )

        recovered = 0
        for row in rows:
            job_id = stable_arq_job_id(row)
            await redis.enqueue_job(
                "execute_job",
                row.id,
                _job_id=job_id,
                _queue_name=settings.JOB_QUEUE_NAME,
            )
            mark_job_queued(db, row, arq_job_id=job_id)
            recovered += 1
        return {"recovered": recovered}
    finally:
        db.close()


async def schedule_hourly_fraud_refresh(ctx):
    """Reserve one durable fraud-refresh job per UTC hour."""
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        row, created = reserve_job_run(
            db,
            job_name="fraud.refresh",
            idempotency_key=f"fraud-refresh:{now.strftime('%Y%m%d%H')}",
            payload={"scheduled_hour": now.strftime("%Y-%m-%dT%H:00:00Z")},
            max_attempts=3,
        )
        if created or row.status in {JobStatus.PENDING, JobStatus.RETRYING}:
            await enqueue_job_run(db, ctx["redis"], row)
        return {"job_run_id": row.id, "created": created}
    finally:
        db.close()


class WorkerSettings:
    on_startup = worker_startup
    functions = [execute_job]
    cron_jobs = [
        cron(
            recover_pending_jobs,
            minute=set(range(60)),
            second=15,
            unique=True,
            max_tries=1,
        ),
        cron(
            schedule_hourly_fraud_refresh,
            minute={0},
            second=30,
            unique=True,
            max_tries=1,
        )
    ]
    redis_settings = get_redis_settings()
    queue_name = settings.JOB_QUEUE_NAME
    max_tries = 20
    keep_result = 3600
