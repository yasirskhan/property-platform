"""Staff HOA observations, not legal violations or financial obligations.

Revision ID: c7e9a1b3d5f2
Revises: f8b0c2d4e6a9
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "c7e9a1b3d5f2"
down_revision = "f8b0c2d4e6a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hoa_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("summary", sa.String(240), nullable=False),
        sa.Column("observed_on", sa.Date(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for field in ("id", "organization_id", "association_id", "property_id"):
        op.create_index("ix_hoa_observations_" + field, "hoa_observations", [field])
    op.create_index("ix_hoa_observation_scope", "hoa_observations", ["organization_id", "association_id", "property_id"])


def downgrade() -> None:
    op.drop_index("ix_hoa_observation_scope", table_name="hoa_observations")
    for field in ("property_id", "association_id", "organization_id", "id"):
        op.drop_index("ix_hoa_observations_" + field, table_name="hoa_observations")
    op.drop_table("hoa_observations")
