from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.core.security import hash_password
from app.models.job_run import JobStatus
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.routers.platform_jobs import job_summary, list_dead_letters, list_job_runs
from app.services.job_runtime import mark_job_dead_letter, mark_job_running, reserve_job_run


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def _platform_user(db, role: PlatformUserRole) -> PlatformUser:
    user = PlatformUser(
        email=f"{role.value}@example.com",
        hashed_password=hash_password("test-platform-password"),
        first_name="Platform",
        last_name="User",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_support_can_monitor_jobs_and_dead_letters() -> None:
    db, engine = _session()
    try:
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        row, _ = reserve_job_run(
            db,
            job_name="health.fail",
            idempotency_key="monitor:1",
            max_attempts=1,
        )
        mark_job_running(db, row)
        mark_job_dead_letter(db, row, error="planned")

        jobs = list_job_runs(
            job_status=None,
            limit=100,
            db=db,
            current_user=support,
        )
        dead = list_dead_letters(limit=100, db=db, current_user=support)
        summary = job_summary(db=db, current_user=support)

        assert len(jobs) == 1
        assert jobs[0].status == JobStatus.DEAD_LETTER
        assert len(dead) == 1
        assert summary.dead_letters == 1
        assert summary.counts["DEAD_LETTER"] == 1
    finally:
        db.close()
        engine.dispose()


def test_sales_role_cannot_monitor_jobs() -> None:
    db, engine = _session()
    try:
        sales = _platform_user(db, PlatformUserRole.PLATFORM_SALES)
        with pytest.raises(HTTPException) as exc:
            job_summary(db=db, current_user=sales)
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()
