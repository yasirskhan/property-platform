from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.services.audit import append_audit_log


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def test_append_audit_log_writes_without_committing_for_caller() -> None:
    db, engine = _session()
    try:
        row = append_audit_log(
            db,
            entity_type="property",
            entity_id=7,
            action="updated",
            old_value={"name": "Old"},
            new_value={"name": "New"},
        )

        assert row.id is not None
        assert row.old_value == '{"name":"Old"}'
        assert row.new_value == '{"name":"New"}'

        db.rollback()
        assert db.query(type(row)).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_audit_log_rejects_orm_update() -> None:
    db, engine = _session()
    try:
        row = append_audit_log(
            db,
            entity_type="lease",
            entity_id=9,
            action="created",
        )
        db.commit()

        row.action = "tampered"
        with pytest.raises(RuntimeError, match="append-only"):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()


def test_audit_log_rejects_orm_delete() -> None:
    db, engine = _session()
    try:
        row = append_audit_log(
            db,
            entity_type="receipt",
            entity_id=11,
            action="created",
        )
        db.commit()

        db.delete(row)
        with pytest.raises(RuntimeError, match="append-only"):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()
