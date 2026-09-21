"""add_org_currency

Adds organizations.currency (VARCHAR(3), default 'USD').
Per-org currency. No exchange, no conversion. Each org operates
in exactly one currency.

See PROJECT_MASTER.md Section 59.

Revision ID: 8c2e766863c0
Revises: 00bc0d143eac
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8c2e766863c0"
down_revision = "00bc0d143eac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add organizations.currency with a sensible default.
    # Existing rows get "USD" (the current hard-coded behavior).
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "currency",
                sa.String(length=3),
                nullable=False,
                server_default="USD",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.drop_column("currency")