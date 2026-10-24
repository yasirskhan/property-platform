"""Independent organization-owned address book; no login/tax/vendor auto-links.

Revision ID: d2e4f6a8b0c1
Revises: c1d3e5f7a9b0
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "d2e4f6a8b0c1"
down_revision = "c1d3e5f7a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("contact_type", sa.String(length=16), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("job_title", sa.String(length=100), nullable=True),
        sa.Column("address_line1", sa.String(length=255), nullable=True),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=50), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contacts_id", "contacts", ["id"], unique=False)
    op.create_index("ix_contacts_organization_id", "contacts", ["organization_id"], unique=False)
    op.create_index("ix_contacts_org_name", "contacts", ["organization_id", "display_name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_contacts_org_name", table_name="contacts")
    op.drop_index("ix_contacts_organization_id", table_name="contacts")
    op.drop_index("ix_contacts_id", table_name="contacts")
    op.drop_table("contacts")
