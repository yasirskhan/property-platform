# Alembic environment for property-platform
# Full replacement — connects Alembic to our SQLAlchemy Base and models
#
# IMPORTANT: Every model module must be imported below. If a
# model isn't imported, Alembic won't see its table. This matters
# for two things:
#   1. Any future autogenerate attempt (we don't use it, but
#      a future session might try).
#   2. Consistency — the list here should match init_db.py.

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys

# Make sure the app package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import our Base and ALL models so Alembic can see every table
from app.core.database import Base

# ---- Core ----
import app.models.user
import app.models.audit_log
import app.models.platform_settings
import app.models.sidebar_preference
import app.models.menu_permission
import app.models.user_permission

# ---- Properties / leases / operations ----
import app.models.property
import app.models.lease
import app.models.work_order
import app.models.tax
import app.models.utility
import app.models.insurance
import app.models.expense
import app.models.income

# ---- Applications / screening / insurance ----
import app.models.application
import app.models.tenant_insurance
import app.models.screening

# ---- Auth / settings ----
import app.models.password_reset
import app.models.org_email

# ---- Accounting: General Ledger ----
import app.models.gl_account
import app.models.gl_transaction
import app.models.gl_entry

# ---- Accounting: Receipts ----
import app.models.receipt
import app.models.receipt_line

# ---- Accounting: Bills ----
import app.models.bill
import app.models.bill_line

# ---- Accounting: Deposits ----
import app.models.deposit
import app.models.deposit_line

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