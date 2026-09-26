"""Platform-only background-job monitoring endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.job_run import JobDeadLetter, JobRun, JobStatus
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.routers.platform_auth import get_current_platform_user
from app.schemas.platform_jobs import JobDeadLetterOut, JobRunOut, JobSummaryOut


router = APIRouter(prefix="/api/platform/jobs", tags=["Platform Jobs"])

_JOB_VIEWERS = {
    PlatformUserRole.PLATFORM_ADMIN,
    PlatformUserRole.PLATFORM_DEV,
    PlatformUserRole.PLATFORM_TECH,
    PlatformUserRole.PLATFORM_SUPPORT,
}


def _require_job_viewer(user: PlatformUser) -> None:
    if user.role not in _JOB_VIEWERS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform job-monitor access required",
        )


@router.get("", response_model=list[JobRunOut])
def list_job_runs(
    job_status: JobStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
) -> list[JobRun]:
    _require_job_viewer(current_user)
    query = db.query(JobRun)
    if job_status is not None:
        query = query.filter(JobRun.status == job_status)
    return query.order_by(JobRun.id.desc()).limit(limit).all()


@router.get("/dead-letters", response_model=list[JobDeadLetterOut])
def list_dead_letters(
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
) -> list[JobDeadLetter]:
    _require_job_viewer(current_user)
    return (
        db.query(JobDeadLetter)
        .order_by(JobDeadLetter.id.desc())
        .limit(limit)
        .all()
    )


@router.get("/summary", response_model=JobSummaryOut)
def job_summary(
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
) -> JobSummaryOut:
    _require_job_viewer(current_user)

    rows = (
        db.query(JobRun.status, func.count(JobRun.id))
        .group_by(JobRun.status)
        .all()
    )
    counts = {
        (job_status.value if hasattr(job_status, "value") else str(job_status)): count
        for job_status, count in rows
    }
    for job_status in JobStatus:
        counts.setdefault(job_status.value, 0)

    return JobSummaryOut(
        counts=counts,
        dead_letters=db.query(JobDeadLetter).count(),
    )
