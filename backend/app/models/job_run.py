"""Durable background-job state and dead-letter records."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    RETRYING = "RETRYING"
    SUCCEEDED = "SUCCEEDED"
    DEAD_LETTER = "DEAD_LETTER"


class JobRun(Base):
    __tablename__ = "job_runs"
    __table_args__ = (
        UniqueConstraint(
            "job_name",
            "idempotency_key",
            name="uq_job_runs_name_idempotency",
        ),
        Index("ix_job_runs_status_scheduled", "status", "scheduled_for"),
    )

    id = Column(Integer, primary_key=True)
    job_name = Column(String(120), nullable=False, index=True)
    idempotency_key = Column(String(255), nullable=False)
    status = Column(
        SqlEnum(
            JobStatus,
            name="job_status",
            native_enum=False,
            length=24,
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        nullable=False,
        default=JobStatus.PENDING,
        server_default=JobStatus.PENDING.value,
        index=True,
    )
    payload = Column(JSON, nullable=False, default=dict)
    result = Column(JSON, nullable=True)

    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    max_attempts = Column(Integer, nullable=False, default=5, server_default="5")

    arq_job_id = Column(String(255), nullable=True, index=True)
    scheduled_for = Column(DateTime(timezone=True), nullable=True, index=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)

    last_error = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    dead_letter = relationship(
        "JobDeadLetter",
        back_populates="job_run",
        uselist=False,
        cascade="all, delete-orphan",
    )


class JobDeadLetter(Base):
    __tablename__ = "job_dead_letters"

    id = Column(Integer, primary_key=True)
    job_run_id = Column(
        Integer,
        ForeignKey("job_runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    job_name = Column(String(120), nullable=False, index=True)
    idempotency_key = Column(String(255), nullable=False)
    attempts = Column(Integer, nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    error = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    job_run = relationship("JobRun", back_populates="dead_letter")
