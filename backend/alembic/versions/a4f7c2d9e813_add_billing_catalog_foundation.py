"""add billing catalog foundation

Revision ID: a4f7c2d9e813
Revises: 46c3d8f2ab10
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa

revision = "a4f7c2d9e813"
down_revision = "46c3d8f2ab10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plans_code", "plans", ["code"], unique=True)
    op.create_index("ix_plans_is_active", "plans", ["is_active"], unique=False)

    op.create_table(
        "modules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_core", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_modules_key", "modules", ["key"], unique=True)
    op.create_index("ix_modules_is_active", "modules", ["is_active"], unique=False)

    op.create_table(
        "plan_modules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("module_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "module_id", name="uq_plan_modules_plan_module"),
    )
    op.create_index("ix_plan_modules_module_id", "plan_modules", ["module_id"], unique=False)
    op.create_index("ix_plan_modules_plan_id", "plan_modules", ["plan_id"], unique=False)

    op.create_table(
        "module_features",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("module_id", sa.Integer(), nullable=False),
        sa.Column("feature_key", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("module_id", "feature_key", name="uq_module_features_module_key"),
    )
    op.create_index("ix_module_features_feature_key", "module_features", ["feature_key"], unique=False)
    op.create_index("ix_module_features_module_id", "module_features", ["module_id"], unique=False)

    op.create_table(
        "pricing_tiers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("min_properties", sa.Integer(), nullable=False),
        sa.Column("max_properties", sa.Integer(), nullable=True),
        sa.Column("monthly_price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("max_properties IS NULL OR max_properties >= min_properties", name="ck_pricing_tiers_property_range"),
        sa.CheckConstraint("min_properties >= 1", name="ck_pricing_tiers_min_properties"),
        sa.CheckConstraint("monthly_price_cents >= 0", name="ck_pricing_tiers_price"),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "min_properties", name="uq_pricing_tiers_plan_min"),
    )
    op.create_index("ix_pricing_tiers_plan_id", "pricing_tiers", ["plan_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pricing_tiers_plan_id", table_name="pricing_tiers")
    op.drop_table("pricing_tiers")
    op.drop_index("ix_module_features_module_id", table_name="module_features")
    op.drop_index("ix_module_features_feature_key", table_name="module_features")
    op.drop_table("module_features")
    op.drop_index("ix_plan_modules_plan_id", table_name="plan_modules")
    op.drop_index("ix_plan_modules_module_id", table_name="plan_modules")
    op.drop_table("plan_modules")
    op.drop_index("ix_modules_is_active", table_name="modules")
    op.drop_index("ix_modules_key", table_name="modules")
    op.drop_table("modules")
    op.drop_index("ix_plans_is_active", table_name="plans")
    op.drop_index("ix_plans_code", table_name="plans")
    op.drop_table("plans")
