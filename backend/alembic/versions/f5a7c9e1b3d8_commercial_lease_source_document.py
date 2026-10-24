"""Link a private source attachment to a commercial lease staff reference.

Revision ID: f5a7c9e1b3d8
Revises: e4f6a8c0b2d5
"""
from alembic import op
import sqlalchemy as sa

revision = "f5a7c9e1b3d8"
down_revision = "e4f6a8c0b2d5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("commercial_lease_abstracts") as batch:
        batch.add_column(sa.Column("source_attachment_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_commercial_lease_abstract_source_attachment",
            "entity_attachments", ["source_attachment_id"], ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index(
            "ix_commercial_lease_abstract_source_attachment",
            ["source_attachment_id"], unique=False,
        )


def downgrade():
    with op.batch_alter_table("commercial_lease_abstracts") as batch:
        batch.drop_index("ix_commercial_lease_abstract_source_attachment")
        batch.drop_constraint(
            "fk_commercial_lease_abstract_source_attachment",
            type_="foreignkey",
        )
        batch.drop_column("source_attachment_id")
