"""ARC inspection follow-up completion metadata.

Revision ID: d9f1b3c5e7a2
Revises: c2e4a6b8d0f3
"""
from alembic import op
import sqlalchemy as sa

revision = "d9f1b3c5e7a2"
down_revision = "c2e4a6b8d0f3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("hoa_arc_follow_ups") as batch:
        batch.add_column(sa.Column("completion_on", sa.Date(), nullable=True))
        batch.add_column(sa.Column("completion_note", sa.Text(), nullable=True))
        batch.add_column(sa.Column("completion_attachment_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("completion_request_key", sa.String(64), nullable=True))
        batch.add_column(sa.Column("completed_by_user_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("completed_at", sa.DateTime(), nullable=True))
        batch.create_foreign_key(
            "fk_hoa_arc_follow_up_completion_attachment", "entity_attachments",
            ["completion_attachment_id"], ["id"], ondelete="RESTRICT",
        )
        batch.create_foreign_key(
            "fk_hoa_arc_follow_up_completed_by", "users",
            ["completed_by_user_id"], ["id"], ondelete="RESTRICT",
        )
        batch.create_unique_constraint(
            "uq_hoa_arc_follow_up_completion_request",
            ["organization_id", "completion_request_key"],
        )


def downgrade():
    with op.batch_alter_table("hoa_arc_follow_ups") as batch:
        batch.drop_constraint("uq_hoa_arc_follow_up_completion_request", type_="unique")
        batch.drop_constraint("fk_hoa_arc_follow_up_completed_by", type_="foreignkey")
        batch.drop_constraint("fk_hoa_arc_follow_up_completion_attachment", type_="foreignkey")
        batch.drop_column("completed_at")
        batch.drop_column("completed_by_user_id")
        batch.drop_column("completion_request_key")
        batch.drop_column("completion_attachment_id")
        batch.drop_column("completion_note")
        batch.drop_column("completion_on")
