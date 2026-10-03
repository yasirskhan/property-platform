"""add add-ons and discounts catalog

Revision ID: 0ad7c6e2f9b1
Revises: f9d2c5b7a104
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa

revision = "0ad7c6e2f9b1"
down_revision = "f9d2c5b7a104"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "add_ons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("unit_price_cents >= 0", name="ck_add_ons_unit_price"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_add_ons_code", "add_ons", ["code"], unique=True)
    op.create_index("ix_add_ons_is_active", "add_ons", ["is_active"], unique=False)

    op.create_table(
        "discounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("percent_off", sa.Integer(), nullable=True),
        sa.Column("amount_off_cents", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=True),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "(percent_off IS NOT NULL AND amount_off_cents IS NULL) OR "
            "(percent_off IS NULL AND amount_off_cents IS NOT NULL)",
            name="ck_discounts_exactly_one_value",
        ),
        sa.CheckConstraint(
            "percent_off IS NULL OR (percent_off >= 1 AND percent_off <= 100)",
            name="ck_discounts_percent_range",
        ),
        sa.CheckConstraint(
            "amount_off_cents IS NULL OR amount_off_cents >= 0",
            name="ck_discounts_amount_nonnegative",
        ),
        sa.CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at >= starts_at",
            name="ck_discounts_date_range",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_discounts_code", "discounts", ["code"], unique=True)
    op.create_index("ix_discounts_is_active", "discounts", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_discounts_is_active", table_name="discounts")
    op.drop_index("ix_discounts_code", table_name="discounts")
    op.drop_table("discounts")
    op.drop_index("ix_add_ons_is_active", table_name="add_ons")
    op.drop_index("ix_add_ons_code", table_name="add_ons")
    op.drop_table("add_ons")
