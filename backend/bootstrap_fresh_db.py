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
from sqlalchemy.orm import Session

from app.core.database import Base, engine
import init_db  # noqa: F401
from app.services.hoa_addon_catalog import seed_unreleased_hoa_catalog

BACKEND_ROOT = Path(__file__).resolve().parent


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return cfg


def _install_fresh_material_movement_guards() -> None:
    """Match the append-only triggers created by material migration c5d91a7e2f60.

    Fresh bootstrap builds tables with ORM metadata and only stamps Alembic;
    stamping does NOT execute that migration's trigger DDL. Existing databases
    obtain the guards from Alembic upgrade, never from this fresh-only path.
    """
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.exec_driver_sql("""
                CREATE FUNCTION prevent_material_movement_mutation()
                RETURNS trigger AS $stock_guard$
                BEGIN
                    RAISE EXCEPTION 'maintenance_material_movements is append-only';
                END;
                $stock_guard$ LANGUAGE plpgsql
            """)
            conn.exec_driver_sql("""
                CREATE TRIGGER material_movement_immutable
                BEFORE UPDATE OR DELETE ON maintenance_material_movements
                FOR EACH ROW EXECUTE FUNCTION prevent_material_movement_mutation()
            """)
        elif engine.dialect.name == "sqlite":
            conn.exec_driver_sql("""
                CREATE TRIGGER material_movement_no_update
                BEFORE UPDATE ON maintenance_material_movements
                BEGIN
                    SELECT RAISE(ABORT,'maintenance_material_movements is append-only');
                END
            """)
            conn.exec_driver_sql("""
                CREATE TRIGGER material_movement_no_delete
                BEFORE DELETE ON maintenance_material_movements
                BEGIN
                    SELECT RAISE(ABORT,'maintenance_material_movements is append-only');
                END
            """)
        else:
            raise RuntimeError("Unsupported database for immutable stock evidence")


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
    _install_fresh_material_movement_guards()
    # Fresh bootstraps skip data-only Alembic revisions; seed the same
    # hidden, unsubscribed HOA catalog without activating any billing.
    with Session(engine) as db:
        seed_unreleased_hoa_catalog(db)
        db.commit()
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
