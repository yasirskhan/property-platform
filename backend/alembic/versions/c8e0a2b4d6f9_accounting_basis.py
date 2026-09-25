"""add accounting basis to accounting settings

Revision ID: c8e0a2b4d6f9
Revises: b7d9f1a3c5e8
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa

revision = "c8e0a2b4d6f9"
down_revision = "b7d9f1a3c5e8"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        "accounting_settings",
        sa.Column(
            "accounting_basis",
            sa.String(length=10),
            nullable=False,
            server_default="ACCRUAL",
        ),
    )

def downgrade() -> None:
    with op.batch_alter_table("accounting_settings") as batch:
        batch.drop_column("accounting_basis")
