from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = BACKEND_ROOT / "tests" / "fixtures" / "pre_alembic_1d77_schema.sql"
EXPECTED_HEAD = "f1c9d3e7a6b5"
EXPECTED_MODEL_TABLES = 56


def _run(command: list[str], database_url: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    return subprocess.run(
        command,
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _version(db_path: Path) -> str:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        assert row is not None
        return row[0]
    finally:
        conn.close()


@pytest.mark.integration
def test_fresh_database_bootstrap_creates_current_schema_and_stamps_head(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    url = f"sqlite:///{db_path.as_posix()}"
    result = _run([sys.executable, "bootstrap_fresh_db.py"], url)
    assert result.returncode == 0, f"Bootstrap failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert _version(db_path) == EXPECTED_HEAD

    conn = sqlite3.connect(db_path)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == EXPECTED_MODEL_TABLES


@pytest.mark.integration
def test_fresh_bootstrap_refuses_nonempty_database(tmp_path: Path) -> None:
    db_path = tmp_path / "nonempty.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE existing_business_data (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    result = _run([sys.executable, "bootstrap_fresh_db.py"], f"sqlite:///{db_path.as_posix()}")
    assert result.returncode != 0
    assert "Refusing fresh bootstrap" in (result.stdout + result.stderr)


@pytest.mark.integration
def test_legacy_schema_snapshot_upgrades_to_head(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(FIXTURE.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()

    result = _run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        f"sqlite:///{db_path.as_posix()}",
    )
    assert result.returncode == 0, f"Alembic failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert _version(db_path) == EXPECTED_HEAD
