from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from arq import Retry
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.jobs.queue import enqueue_job_run, stable_arq_job_id, submit_job
from app.jobs.registry import register_job_handler
from app.jobs.worker import execute_job, retry_delay_seconds
from app.models.job_run import JobDeadLetter, JobRun, JobStatus
from app.services.job_runtime import reserve_job_run


class FakeRedis:
    def __init__(self):
        self.calls = []

    async def enqueue_job(self, function, *args, **kwargs):
        self.calls.append((function, args, kwargs))
        return SimpleNamespace(job_id=kwargs.get("_job_id"))


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    maker = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    return maker, engine


def test_submit_job_uses_stable_arq_id_and_db_idempotency() -> None:
    maker, engine = _session()
    db = maker()
    redis = FakeRedis()
    try:
        first, created = asyncio.run(
            submit_job(
                db,
                redis,
                job_name="health.noop",
                idempotency_key="same-business-event",
                payload={"x": 1},
            )
        )
        second, created_again = asyncio.run(
            submit_job(
                db,
                redis,
                job_name="health.noop",
                idempotency_key="same-business-event",
                payload={"x": 999},
            )
        )

        assert created is True
        assert created_again is False
        assert first.id == second.id
        assert first.arq_job_id == stable_arq_job_id(first)
        assert all(call[2]["_job_id"] == stable_arq_job_id(first) for call in redis.calls)
        assert db.query(JobRun).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_scheduled_job_passes_defer_until() -> None:
    maker, engine = _session()
    db = maker()
    redis = FakeRedis()
    try:
        scheduled = datetime.now(timezone.utc) + timedelta(minutes=5)
        row, _ = reserve_job_run(
            db,
            job_name="health.noop",
            idempotency_key="scheduled:1",
            scheduled_for=scheduled,
        )
        asyncio.run(enqueue_job_run(db, redis, row))
        assert redis.calls[0][2]["_defer_until"] is not None
    finally:
        db.close()
        engine.dispose()


def test_retry_backoff_is_bounded() -> None:
    assert retry_delay_seconds(1) == 5
    assert retry_delay_seconds(2) == 10
    assert retry_delay_seconds(3) == 20
    assert retry_delay_seconds(20) == 300


def test_worker_retries_then_dead_letters(monkeypatch) -> None:
    maker, engine = _session()

    @register_job_handler("test.always_fail")
    async def always_fail(_payload):
        raise RuntimeError("planned failure")

    monkeypatch.setattr("app.jobs.worker.SessionLocal", maker)

    db = maker()
    try:
        row, _ = reserve_job_run(
            db,
            job_name="test.always_fail",
            idempotency_key="failure:1",
            max_attempts=2,
        )
        job_id = row.id
    finally:
        db.close()

    with pytest.raises(Retry):
        asyncio.run(execute_job({}, job_id))

    check = maker()
    try:
        row = check.query(JobRun).filter(JobRun.id == job_id).one()
        assert row.status == JobStatus.RETRYING
        assert row.attempts == 1
    finally:
        check.close()

    result = asyncio.run(execute_job({}, job_id))
    assert "dead_letter_id" in result

    check = maker()
    try:
        row = check.query(JobRun).filter(JobRun.id == job_id).one()
        assert row.status == JobStatus.DEAD_LETTER
        assert row.attempts == 2
        assert check.query(JobDeadLetter).filter(JobDeadLetter.job_run_id == job_id).count() == 1
    finally:
        check.close()
        engine.dispose()
