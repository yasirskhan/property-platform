"""Safely prepare a database for application startup/deploy.

Rules:
- Empty database: create current model schema and stamp Alembic head.
- Versioned existing database: run `alembic upgrade head`.
- Nonempty database without alembic_version: refuse to guess.
"""
from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.core.database import engine
from bootstrap_fresh_db import bootstrap

BACKEND_ROOT = Path(__file__).resolve().parent


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return cfg


def prepare() -> str:
    tables = set(inspect(engine).get_table_names())
    app_tables = tables - {"alembic_version"}

    if not app_tables:
        bootstrap()
        return "bootstrapped"

    if "alembic_version" not in tables:
        preview = ", ".join(sorted(app_tables)[:8])
        if len(app_tables) > 8:
            preview += ", ..."
        raise RuntimeError(
            "Refusing automatic database preparation: application tables exist but "
            "alembic_version is missing. Treat this as a legacy/manual migration case. "
            f"Tables found: {preview}"
        )

    command.upgrade(_alembic_config(), "head")
    return "upgraded"


if __name__ == "__main__":
    result = prepare()
    print(f"Database preparation complete: {result}.")
