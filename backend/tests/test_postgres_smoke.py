from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "a4b6c8d0e2f1"
EXPECTED_MODEL_TABLES = 90


@pytest.mark.integration
def test_postgres_fresh_bootstrap_when_ci_database_is_available() -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url or not url.startswith("postgresql"):
        pytest.skip("TEST_DATABASE_URL PostgreSQL service is only required in CI/staging")

    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()

    env = os.environ.copy()
    env["DATABASE_URL"] = url
    result = subprocess.run(
        [sys.executable, "bootstrap_fresh_db.py"],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"PostgreSQL bootstrap failed:\n{result.stdout}\n{result.stderr}"
    )

    engine = create_engine(url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "alembic_version" in tables
        assert len(tables - {"alembic_version"}) == EXPECTED_MODEL_TABLES
        with engine.connect() as conn:
            version = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        assert version == EXPECTED_HEAD

        with engine.begin() as conn:
            audit_id = conn.execute(
                text(
                    "INSERT INTO audit_log "
                    "(entity_type, entity_id, action, created_at) "
                    "VALUES ('ci_probe', 1, 'created', CURRENT_TIMESTAMP) "
                    "RETURNING id"
                )
            ).scalar_one()

        with pytest.raises(DBAPIError, match="append-only"):
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE audit_log SET action='tampered' WHERE id=:id"
                    ),
                    {"id": audit_id},
                )

        with pytest.raises(DBAPIError, match="append-only"):
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM audit_log WHERE id=:id"),
                    {"id": audit_id},
                )

        with engine.begin() as conn:
            org_id = conn.execute(
                text(
                    "INSERT INTO organizations "
                    "(name, slug, state, currency, data_region, created_at, updated_at) "
                    "VALUES "
                    "('Billing Probe', 'billing-probe', 'ACTIVE', 'USD', "
                    "'us-east-1', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                    "RETURNING id"
                )
            ).scalar_one()
            plan_id = conn.execute(
                text(
                    "INSERT INTO plans "
                    "(code, name, is_active, created_at, updated_at) "
                    "VALUES "
                    "('ci-probe', 'CI Probe', true, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                    "RETURNING id"
                )
            ).scalar_one()
            subscription_id = conn.execute(
                text(
                    "INSERT INTO subscriptions "
                    "(organization_id, plan_id, status, cancel_at_period_end, "
                    "created_at, updated_at) "
                    "VALUES "
                    "(:org_id, :plan_id, 'ACTIVE', false, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                    "RETURNING id"
                ),
                {"org_id": org_id, "plan_id": plan_id},
            ).scalar_one()
            event_id = conn.execute(
                text(
                    "INSERT INTO subscription_events "
                    "(subscription_id, event_type, created_at) "
                    "VALUES (:subscription_id, 'created', CURRENT_TIMESTAMP) "
                    "RETURNING id"
                ),
                {"subscription_id": subscription_id},
            ).scalar_one()

        with pytest.raises(DBAPIError, match="append-only"):
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE subscription_events "
                        "SET event_type='tampered' WHERE id=:id"
                    ),
                    {"id": event_id},
                )

        with pytest.raises(DBAPIError, match="append-only"):
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM subscription_events WHERE id=:id"),
                    {"id": event_id},
                )
    finally:
        engine.dispose()
