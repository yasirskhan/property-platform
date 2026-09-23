from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "b7d5e9a3c2f1"
EXPECTED_MODEL_TABLES = 53


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
    assert result.returncode == 0, f"PostgreSQL bootstrap failed:\n{result.stdout}\n{result.stderr}"

    engine = create_engine(url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "alembic_version" in tables
        assert len(tables - {"alembic_version"}) == EXPECTED_MODEL_TABLES
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
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
                    text("UPDATE audit_log SET action='tampered' WHERE id=:id"),
                    {"id": audit_id},
                )

        with pytest.raises(DBAPIError, match="append-only"):
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM audit_log WHERE id=:id"),
                    {"id": audit_id},
                )
    finally:
        engine.dispose()
