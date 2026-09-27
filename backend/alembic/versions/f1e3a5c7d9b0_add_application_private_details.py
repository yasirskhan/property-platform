"""Encrypted applicant address and financial questionnaire.

Revision ID: f1e3a5c7d9b0
Revises: e3f5a7b9c0d2
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "f1e3a5c7d9b0"
down_revision = "e3f5a7b9c0d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_private_details",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["application_id"], ["lease_applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", name="uq_application_private_app"),
    )
    op.create_index("ix_application_private_details_id", "application_private_details", ["id"])
    op.create_index("ix_application_private_details_application_id", "application_private_details", ["application_id"])
    op.create_index("ix_application_private_details_organization_id", "application_private_details", ["organization_id"])
    op.create_index("ix_application_private_scope", "application_private_details", ["organization_id", "application_id"])


def downgrade() -> None:
    op.drop_index("ix_application_private_scope", table_name="application_private_details")
    op.drop_index("ix_application_private_details_organization_id", table_name="application_private_details")
    op.drop_index("ix_application_private_details_application_id", table_name="application_private_details")
    op.drop_index("ix_application_private_details_id", table_name="application_private_details")
    op.drop_table("application_private_details")
