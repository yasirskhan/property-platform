"""Staff-only commercial lease commencement references.

Revision ID: a1c3e5f7b9d0
Revises: f0b2c4d6e8a1
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "a1c3e5f7b9d0"
down_revision = "f0b2c4d6e8a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "commercial_lease_abstracts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lease_id", sa.Integer(), sa.ForeignKey("leases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rent_commencement_on", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "lease_id", name="uq_commercial_lease_abstract_org_lease"),
    )
    for name in ("id", "organization_id", "property_id", "lease_id"):
        op.create_index(f"ix_commercial_lease_abstracts_{name}", "commercial_lease_abstracts", [name])
    op.create_index("ix_commercial_lease_abstract_scope", "commercial_lease_abstracts",
                    ["organization_id", "property_id", "is_active"])


def downgrade() -> None:
    op.drop_index("ix_commercial_lease_abstract_scope", table_name="commercial_lease_abstracts")
    for name in ("lease_id", "property_id", "organization_id", "id"):
        op.drop_index(f"ix_commercial_lease_abstracts_{name}", table_name="commercial_lease_abstracts")
    op.drop_table("commercial_lease_abstracts")
