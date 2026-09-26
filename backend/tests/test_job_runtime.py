from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.job_run import JobDeadLetter, JobStatus
from app.services.job_runtime import (
    mark_job_dead_letter,
    mark_job_queued,
    mark_job_retrying,
    mark_job_running,
    mark_job_succeeded,
    reserve_job_run,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def test_job_reservation_is_database_idempotent() -> None:
    db, engine = _session()
    try:
        first, created = reserve_job_run(
            db,
            job_name="billing.reconcile",
            idempotency_key="org:1:2026-09-23",
            payload={"organization_id": 1},
        )
        second, created_again = reserve_job_run(
            db,
            job_name="billing.reconcile",
            idempotency_key="org:1:2026-09-23",
            payload={"organization_id": 999},
        )

        assert created is True
        assert created_again is False
        assert first.id == second.id
        assert second.payload == {"organization_id": 1}
    finally:
        db.close()
        engine.dispose()


def test_job_lifecycle_tracks_attempts_retry_and_success() -> None:
    db, engine = _session()
    try:
        row, _ = reserve_job_run(
            db,
            job_name="health.noop",
            idempotency_key="noop:1",
            max_attempts=3,
        )
        mark_job_queued(db, row, arq_job_id=f"job:{row.id}")
        mark_job_running(db, row)
        assert row.attempts == 1
        assert row.status == JobStatus.RUNNING

        retry_at = datetime.now(timezone.utc) + timedelta(seconds=30)
        mark_job_retrying(db, row, error="temporary", next_retry_at=retry_at)
        assert row.status == JobStatus.RETRYING
        assert row.last_error == "temporary"

        mark_job_running(db, row)
        mark_job_succeeded(db, row, result={"ok": True})
        assert row.attempts == 2
        assert row.status == JobStatus.SUCCEEDED
        assert row.result == {"ok": True}
        assert row.completed_at is not None
    finally:
        db.close()
        engine.dispose()


def test_dead_letter_is_durable_and_unique_per_job_run() -> None:
    db, engine = _session()
    try:
        row, _ = reserve_job_run(
            db,
            job_name="health.fail",
            idempotency_key="fail:1",
            payload={"value": 7},
            max_attempts=1,
        )
        mark_job_running(db, row)
        first = mark_job_dead_letter(db, row, error="boom")
        second = mark_job_dead_letter(db, row, error="boom again")

        assert first.id == second.id
        assert row.status == JobStatus.DEAD_LETTER
        assert db.query(JobDeadLetter).count() == 1
        assert second.error == "boom again"
    finally:
        db.close()
        engine.dispose()
