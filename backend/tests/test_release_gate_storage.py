from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.release_gate import (
    ReleaseGate,
    ReleaseGateOrganization,
    ReleaseStage,
)
from app.models.user import Organization


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def test_release_stage_contract_is_exact() -> None:
    assert [stage.value for stage in ReleaseStage] == [
        "HIDDEN",
        "BETA",
        "ROLLOUT",
        "ALL_ORGS",
    ]


def test_release_gate_defaults_hidden() -> None:
    db, engine = _session()
    try:
        gate = ReleaseGate(key="release.accounting.receipts")
        db.add(gate)
        db.commit()
        db.refresh(gate)

        assert gate.stage == ReleaseStage.HIDDEN
    finally:
        db.close()
        engine.dispose()


def test_release_gate_org_allowlist_prevents_duplicates() -> None:
    db, engine = _session()
    try:
        org = Organization(name="Example", slug="example")
        gate = ReleaseGate(
            key="release.accounting.receipts.process_nsf",
            stage=ReleaseStage.BETA,
        )
        db.add_all([org, gate])
        db.commit()

        db.add(
            ReleaseGateOrganization(
                release_gate_id=gate.id,
                organization_id=org.id,
            )
        )
        db.commit()

        db.add(
            ReleaseGateOrganization(
                release_gate_id=gate.id,
                organization_id=org.id,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()
