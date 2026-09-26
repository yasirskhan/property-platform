from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app.models.platform_user import PlatformUser, PlatformUserRole

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _run(
    command: list[str],
    database_url: str,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        command,
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_platform_user_is_not_org_scoped() -> None:
    columns = set(PlatformUser.__table__.columns.keys())
    assert "organization_id" not in columns
    assert "email" in columns
    assert "role" in columns


def test_platform_roles_are_separate_from_customer_roles() -> None:
    assert {role.value for role in PlatformUserRole} == {
        "platform_admin",
        "platform_sales",
        "platform_billing",
        "platform_tech",
        "platform_support",
        "platform_dev",
    }


@pytest.mark.integration
def test_first_platform_admin_seed_is_guarded_and_one_time(tmp_path: Path) -> None:
    db_path = tmp_path / "platform-identity.db"
    database_url = f"sqlite:///{db_path.as_posix()}"

    bootstrap = _run([sys.executable, "bootstrap_fresh_db.py"], database_url)
    assert bootstrap.returncode == 0, bootstrap.stdout + bootstrap.stderr

    seed_env = {
        "PLATFORM_ADMIN_SEED_ALLOWED": "true",
        "PLATFORM_ADMIN_EMAIL": "platform-admin@example.com",
        "PLATFORM_ADMIN_PASSWORD": "test-platform-1234",
        "PLATFORM_ADMIN_FIRST_NAME": "Platform",
        "PLATFORM_ADMIN_LAST_NAME": "Admin",
    }
    first = _run([sys.executable, "seed_platform_admin.py"], database_url, seed_env)
    assert first.returncode == 0, first.stdout + first.stderr

    conn = sqlite3.connect(db_path)
    try:
        platform_row = conn.execute(
            "SELECT email, role FROM platform_users"
        ).fetchone()
        customer_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        conn.close()

    assert platform_row == ("platform-admin@example.com", "platform_admin")
    assert customer_count == 0

    second = _run([sys.executable, "seed_platform_admin.py"], database_url, seed_env)
    assert second.returncode != 0
    assert "platform_users already contains an account" in (
        second.stdout + second.stderr
    )
