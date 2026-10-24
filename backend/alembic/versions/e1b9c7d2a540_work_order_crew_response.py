"""Crew assignment offer and explicit acceptance/rejection without altering legacy jobs.

Revision ID: e1b9c7d2a540
Revises: c4b7e2f9a601
"""
from alembic import op
import sqlalchemy as sa

revision = "e1b9c7d2a540"
down_revision = "c4b7e2f9a601"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("work_orders") as batch:
        batch.add_column(sa.Column("assignment_response", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("assignment_responded_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    populated = op.get_bind().execute(sa.text(
        "SELECT EXISTS(SELECT 1 FROM work_orders "
        "WHERE assignment_response IS NOT NULL OR assignment_responded_at IS NOT NULL)"
    )).scalar()
    if populated:
        raise RuntimeError("Cannot discard existing crew assignment responses")
    with op.batch_alter_table("work_orders") as batch:
        batch.drop_column("assignment_responded_at")
        batch.drop_column("assignment_response")
