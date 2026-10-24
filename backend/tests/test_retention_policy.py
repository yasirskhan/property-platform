from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.data_retention_policy import DataRetentionPolicy
from app.models.user import Organization
from app.services.retention_policy import (
    resolve_retention_days,
    set_retention_policy,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def test_platform_default_and_org_override_resolve_independently() -> None:
    db, engine = _session()
    try:
        org = Organization(name="Retention Org", slug="retention-org")
        db.add(org)
        db.flush()

        set_retention_policy(
            db,
            data_class="audit",
            retention_days=2555,
        )
        set_retention_policy(
            db,
            organization_id=org.id,
            data_class="audit",
            retention_days=365,
        )
        db.commit()

        assert resolve_retention_days(db, data_class="audit") == 2555
        assert resolve_retention_days(
            db,
            organization_id=org.id,
            data_class="audit",
        ) == 365
    finally:
        db.close()
        engine.dispose()


def test_missing_policy_defaults_to_forever() -> None:
    db, engine = _session()
    try:
        assert resolve_retention_days(db, data_class="financial") is None
    finally:
        db.close()
        engine.dispose()


def test_invalid_retention_window_is_rejected_before_write() -> None:
    db, engine = _session()
    try:
        with pytest.raises(ValueError, match="30, 365, 2555"):
            set_retention_policy(db, data_class="audit", retention_days=90)
        assert db.query(DataRetentionPolicy).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_database_constraint_rejects_unsupported_window() -> None:
    db, engine = _session()
    try:
        db.add(DataRetentionPolicy(data_class="audit", retention_days=90))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()
