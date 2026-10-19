"""Add immutable structured inspection checklist evidence.

Revision ID: 3e6a8b0d91f2
Revises: 2c4e6a8b0d91
"""
from alembic import op
import sqlalchemy as sa

revision = "3e6a8b0d91f2"
down_revision = "2c4e6a8b0d91"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("unit_inspection_records") as batch:
        batch.add_column(sa.Column("checklist_json", sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    evidence = conn.execute(sa.text(
        "SELECT EXISTS(SELECT 1 FROM unit_inspection_records WHERE checklist_json IS NOT NULL)"
    )).scalar()
    if evidence:
        raise RuntimeError("Cannot discard existing inspection checklist evidence")
    with op.batch_alter_table("unit_inspection_records") as batch:
        batch.drop_column("checklist_json")
