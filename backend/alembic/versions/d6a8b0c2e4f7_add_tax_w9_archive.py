"""Add encrypted signed-paper W-9 archive.

Revision ID: d6a8b0c2e4f7
Revises: c5f7a9b1d3e6
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = "d6a8b0c2e4f7"
down_revision = "c5f7a9b1d3e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tax_w9_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("tax_profile_id", sa.Integer(), nullable=False),
        sa.Column("encrypted_pdf", sa.LargeBinary(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tax_profile_id"], ["tax_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tax_w9_documents_id", "tax_w9_documents", ["id"], unique=False)
    op.create_index("ix_tax_w9_documents_organization_id", "tax_w9_documents", ["organization_id"], unique=False)
    op.create_index("ix_tax_w9_documents_tax_profile_id", "tax_w9_documents", ["tax_profile_id"], unique=False)
    op.create_index("ix_tax_w9_org_profile", "tax_w9_documents", ["organization_id", "tax_profile_id", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tax_w9_org_profile", table_name="tax_w9_documents")
    op.drop_index("ix_tax_w9_documents_tax_profile_id", table_name="tax_w9_documents")
    op.drop_index("ix_tax_w9_documents_organization_id", table_name="tax_w9_documents")
    op.drop_index("ix_tax_w9_documents_id", table_name="tax_w9_documents")
    op.drop_table("tax_w9_documents")
