"""Add organization-scoped vendor company records.

Revision ID: e3f5a7b9c1d2
Revises: d2f4a6c8e0b1
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "e3f5a7b9c1d2"
down_revision = "d2f4a6c8e0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vendors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("trade", sa.String(length=100), nullable=True),
        sa.Column("business_email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("address_line1", sa.String(length=255), nullable=True),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=50), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("contact_user_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vendors_id", "vendors", ["id"], unique=False)
    op.create_index("ix_vendors_organization_id", "vendors", ["organization_id"], unique=False)
    op.create_index("ix_vendors_trade", "vendors", ["trade"], unique=False)
    op.create_index("ix_vendors_contact_user_id", "vendors", ["contact_user_id"], unique=False)
    op.create_index("ix_vendors_org_company", "vendors", ["organization_id", "company_name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_vendors_org_company", table_name="vendors")
    op.drop_index("ix_vendors_contact_user_id", table_name="vendors")
    op.drop_index("ix_vendors_trade", table_name="vendors")
    op.drop_index("ix_vendors_organization_id", table_name="vendors")
    op.drop_index("ix_vendors_id", table_name="vendors")
    op.drop_table("vendors")
