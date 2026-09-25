from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "c7d9e1f3a5b2"
EXPECTED_MODEL_TABLES = 85


def run_prepare(db_path: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    return subprocess.run(
        [sys.executable, "prepare_database.py"],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_prepare_database_bootstraps_empty_then_upgrades_safely(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "staging.db"

    first = run_prepare(db_path)
    assert first.returncode == 0, first.stdout + first.stderr
    assert "bootstrapped" in first.stdout

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    try:
        tables = set(inspect(engine).get_table_names())
        assert len(tables - {"alembic_version"}) == EXPECTED_MODEL_TABLES
        with engine.connect() as conn:
            version = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        assert version == EXPECTED_HEAD
    finally:
        engine.dispose()

    second = run_prepare(db_path)
    assert second.returncode == 0, second.stdout + second.stderr
    assert "upgraded" in second.stdout


def test_prepare_database_refuses_nonempty_unversioned_database(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "legacy-unknown.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE unknown_legacy_table (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    result = run_prepare(db_path)
    assert result.returncode != 0
    assert "alembic_version is missing" in (result.stdout + result.stderr)
