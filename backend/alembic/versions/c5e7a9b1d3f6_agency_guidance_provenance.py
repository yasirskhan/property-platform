"""Public agency-reference provenance on existing affordable evidence index.

Revision ID: c5e7a9b1d3f6
Revises: b4d6f8a0c2e5
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "c5e7a9b1d3f6"
down_revision = "b4d6f8a0c2e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("affordable_program_evidence",
                  sa.Column("source_url", sa.String(length=500), nullable=True))
    op.add_column("affordable_program_evidence",
                  sa.Column("source_checked_on", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("affordable_program_evidence", "source_checked_on")
    op.drop_column("affordable_program_evidence", "source_url")
