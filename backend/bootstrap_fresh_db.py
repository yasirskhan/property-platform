"""Create a brand-new database at the current schema and stamp Alembic head.

Use this ONLY for an empty database. Existing installations must use
`alembic upgrade head` so historical data migrations are preserved.

The script refuses to run when application tables already exist.
"""
from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.core.database import Base, engine
import init_db  # noqa: F401  # imports every model into Base.metadata

BACKEND_ROOT = Path(__file__).resolve().parent


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return cfg


def bootstrap() -> None:
    inspector = inspect(engine)
    existing = sorted(t for t in inspector.get_table_names() if t != "alembic_version")
    if existing:
        preview = ", ".join(existing[:8])
        if len(existing) > 8:
            preview += ", ..."
        raise RuntimeError(
            "Refusing fresh bootstrap: database already contains application tables: "
            + preview
            + ". Existing databases must use `alembic upgrade head`."
        )

    Base.metadata.create_all(bind=engine)
    command.stamp(_alembic_config(), "head")

    created = sorted(t for t in inspect(engine).get_table_names() if t != "alembic_version")
    expected = sorted(Base.metadata.tables)
    if created != expected:
        missing = sorted(set(expected) - set(created))
        extra = sorted(set(created) - set(expected))
        raise RuntimeError(f"Bootstrap schema mismatch. missing={missing} extra={extra}")

    print(f"Fresh database created: {len(created)} application tables; Alembic stamped at head.")


if __name__ == "__main__":
    bootstrap()
