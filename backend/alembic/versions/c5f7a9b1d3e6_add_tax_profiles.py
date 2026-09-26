"""Add ciphertext-only payer/recipient tax profiles for IRIS readiness.

Revision ID: c5f7a9b1d3e6
Revises: b4e6a8c0d2f5
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = "c5f7a9b1d3e6"
down_revision = "b4e6a8c0d2f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tax_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=16), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("w9_on_file", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("w9_received_on", sa.Date(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "subject_type", "subject_id", name="uq_tax_profile_subject"),
    )
    op.create_index("ix_tax_profiles_id", "tax_profiles", ["id"], unique=False)
    op.create_index("ix_tax_profiles_organization_id", "tax_profiles", ["organization_id"], unique=False)
    op.create_index("ix_tax_profile_subject", "tax_profiles", ["organization_id", "subject_type", "subject_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tax_profile_subject", table_name="tax_profiles")
    op.drop_index("ix_tax_profiles_organization_id", table_name="tax_profiles")
    op.drop_index("ix_tax_profiles_id", table_name="tax_profiles")
    op.drop_table("tax_profiles")
