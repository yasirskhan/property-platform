"""Additive work-order requester provenance, leaving legacy tenant_id unchanged.

Revision ID: 2c4e6a8b0d91
Revises: 1b8d3f6a9c20
"""
from alembic import op
import sqlalchemy as sa

revision = "2c4e6a8b0d91"
down_revision = "1b8d3f6a9c20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("work_orders") as batch:
        batch.add_column(sa.Column("request_origin", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("requested_by_user_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_work_orders_requested_by_user_id",
            "users", ["requested_by_user_id"], ["id"],
        )
        batch.create_index("ix_work_orders_requested_by_user_id", ["requested_by_user_id"], unique=False)


def downgrade() -> None:
    # Recoverability: refuse to discard existing recorded provenance.
    conn = op.get_bind()
    has_evidence = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM work_orders "
        "WHERE request_origin IS NOT NULL OR requested_by_user_id IS NOT NULL)"
    )).scalar()
    if has_evidence:
        raise RuntimeError("Cannot drop populated work-order provenance columns")
    with op.batch_alter_table("work_orders") as batch:
        batch.drop_index("ix_work_orders_requested_by_user_id")
        batch.drop_constraint("fk_work_orders_requested_by_user_id", type_="foreignkey")
        batch.drop_column("requested_by_user_id")
        batch.drop_column("request_origin")
