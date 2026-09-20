# Alembic environment for property-platform
# Full replacement — connects Alembic to our SQLAlchemy Base and models

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys

# Make sure the app package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import our Base and ALL models so Alembic can see every table
from app.core.database import Base

# Import every model module here — this is critical
# If a model isn't imported, Alembic won't know its table exists
import app.models.user
import app.models.property
import app.models.lease
import app.models.work_order
import app.models.password_reset
import app.models.org_email
import app.models.audit_log
import app.models.tax
import app.models.utility
import app.models.insurance
import app.models.expense
import app.models.income
import app.models.application
import app.models.tenant_insurance
import app.models.screening
import app.models.platform_settings

# Alembic Config object
config = context.config

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is what Alembic uses to compare against the database
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # needed for SQLite ALTER support
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # critical for SQLite
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()