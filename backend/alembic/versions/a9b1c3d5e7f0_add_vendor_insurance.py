"""Add organization-scoped vendor insurance and expiration.

Revision ID: a9b1c3d5e7f0
Revises: e3f5a7b9c1d2
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "a9b1c3d5e7f0"
down_revision = "e3f5a7b9c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vendor_insurances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("vendor_id", sa.Integer(), nullable=False),
        sa.Column("carrier", sa.String(length=255), nullable=False),
        sa.Column("coverage_type", sa.String(length=100), nullable=False),
        sa.Column("policy_number", sa.String(length=100), nullable=True),
        sa.Column("coverage_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vendor_id"], ["vendors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vendor_insurances_id", "vendor_insurances", ["id"], unique=False)
    op.create_index("ix_vendor_insurances_organization_id", "vendor_insurances", ["organization_id"], unique=False)
    op.create_index("ix_vendor_insurances_vendor_id", "vendor_insurances", ["vendor_id"], unique=False)
    op.create_index("ix_vendor_insurances_expiration_date", "vendor_insurances", ["expiration_date"], unique=False)
    op.create_index(
        "ix_vendor_insurance_org_vendor_expiry", "vendor_insurances",
        ["organization_id", "vendor_id", "expiration_date"], unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_vendor_insurance_org_vendor_expiry", table_name="vendor_insurances")
    op.drop_index("ix_vendor_insurances_expiration_date", table_name="vendor_insurances")
    op.drop_index("ix_vendor_insurances_vendor_id", table_name="vendor_insurances")
    op.drop_index("ix_vendor_insurances_organization_id", table_name="vendor_insurances")
    op.drop_index("ix_vendor_insurances_id", table_name="vendor_insurances")
    op.drop_table("vendor_insurances")
