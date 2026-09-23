# Alembic environment for property-platform
# Full replacement — connects Alembic to our SQLAlchemy Base and models
#
# IMPORTANT: Every model module must be imported below. If a
# model isn't imported, Alembic won't see its table.

from logging.config import fileConfig
from sqlalchemy import create_engine, pool
from alembic import context
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.database import Base

import app.models.user
import app.models.audit_log
import app.models.platform_settings
import app.models.sidebar_preference
import app.models.menu_permission
import app.models.user_permission
import app.models.user_display_preference
import app.models.currency
import app.models.charge
import app.models.property
import app.models.lease
import app.models.work_order
import app.models.tax
import app.models.utility
import app.models.insurance
import app.models.expense
import app.models.income
import app.models.application
import app.models.tenant_insurance
import app.models.screening
import app.models.password_reset
import app.models.org_email
import app.models.gl_account
import app.models.gl_transaction
import app.models.gl_entry
import app.models.receipt
import app.models.receipt_line
import app.models.bill
import app.models.bill_line
import app.models.deposit
import app.models.deposit_line
import app.models.management_fee_run
import app.models.owner_statement
import app.models.bank_account
import app.models.property_amenity
import app.models.property_appliance
import app.models.property_improvement
import app.models.property_photo

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str:
    """Use DATABASE_URL when supplied (CI/staging), otherwise alembic.ini."""
    return os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(get_database_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
