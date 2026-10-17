"""Phase 4.12 staff-entered nightly pricing."""
from alembic import op
import sqlalchemy as sa


revision = "b24d6f8a0c3e"
down_revision = "a13c5e7f9b2d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "short_term_rental_nightly_prices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id", ondelete="CASCADE"), nullable=False),
        sa.Column("night_date", sa.Date(), nullable=False),
        sa.Column("nightly_rate", sa.Numeric(12, 2), nullable=False),
        sa.Column("minimum_stay_nights", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "property_id", "unit_id", "night_date",
            name="uq_short_term_rental_nightly_price_unit_date",
        ),
    )
    op.create_index("ix_short_term_rental_nightly_prices_organization_id", "short_term_rental_nightly_prices", ["organization_id"])
    op.create_index("ix_short_term_rental_nightly_prices_property_id", "short_term_rental_nightly_prices", ["property_id"])
    op.create_index("ix_short_term_rental_nightly_prices_unit_id", "short_term_rental_nightly_prices", ["unit_id"])
    op.create_index("ix_short_term_rental_nightly_prices_night_date", "short_term_rental_nightly_prices", ["night_date"])
    op.create_index(
        "ix_short_term_rental_nightly_price_scope",
        "short_term_rental_nightly_prices",
        ["organization_id", "property_id", "unit_id", "night_date", "is_active"],
    )


def downgrade():
    raise RuntimeError("Downgrade is intentionally disabled for short-term-rental nightly prices.")
