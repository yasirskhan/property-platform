"""Retention-policy helpers."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.data_retention_policy import (
    ALLOWED_RETENTION_DAYS,
    DataRetentionPolicy,
)


def validate_retention_days(retention_days: int | None) -> None:
    if retention_days is not None and retention_days not in ALLOWED_RETENTION_DAYS:
        raise ValueError("retention_days must be 30, 365, 2555, or None (forever)")


def set_retention_policy(
    db: Session,
    *,
    data_class: str,
    retention_days: int | None,
    organization_id: int | None = None,
) -> DataRetentionPolicy:
    normalized = data_class.strip().lower()
    if not normalized:
        raise ValueError("data_class is required")
    validate_retention_days(retention_days)

    row = (
        db.query(DataRetentionPolicy)
        .filter(
            DataRetentionPolicy.organization_id == organization_id,
            DataRetentionPolicy.data_class == normalized,
        )
        .first()
    )
    if row is None:
        row = DataRetentionPolicy(
            organization_id=organization_id,
            data_class=normalized,
            retention_days=retention_days,
        )
        db.add(row)
    else:
        row.retention_days = retention_days

    db.flush()
    return row


def resolve_retention_days(
    db: Session,
    *,
    data_class: str,
    organization_id: int | None = None,
) -> int | None:
    """Resolve org override first, then platform default, then forever."""
    normalized = data_class.strip().lower()
    if not normalized:
        raise ValueError("data_class is required")

    if organization_id is not None:
        org_row = (
            db.query(DataRetentionPolicy)
            .filter(
                DataRetentionPolicy.organization_id == organization_id,
                DataRetentionPolicy.data_class == normalized,
            )
            .first()
        )
        if org_row is not None:
            return org_row.retention_days

    default_row = (
        db.query(DataRetentionPolicy)
        .filter(
            DataRetentionPolicy.organization_id.is_(None),
            DataRetentionPolicy.data_class == normalized,
        )
        .first()
    )
    return default_row.retention_days if default_row is not None else None
