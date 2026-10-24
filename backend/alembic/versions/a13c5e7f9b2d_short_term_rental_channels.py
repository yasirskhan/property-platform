"""Phase 4.12 short-term-rental channel reference foundation."""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "a13c5e7f9b2d"
down_revision = "d19f3a5c7e2b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "short_term_rental_channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("external_listing_id", sa.String(length=180), nullable=True),
        sa.Column("public_listing_url", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "property_id", "provider", "label",
            name="uq_short_term_rental_channel_property_provider_label",
        ),
    )
    op.create_index("ix_short_term_rental_channels_organization_id", "short_term_rental_channels", ["organization_id"])
    op.create_index("ix_short_term_rental_channels_property_id", "short_term_rental_channels", ["property_id"])
    op.create_index(
        "ix_short_term_rental_channel_scope",
        "short_term_rental_channels",
        ["organization_id", "property_id", "is_active"],
    )

    gate = sa.table(
        "release_gates",
        sa.column("key", sa.String()),
        sa.column("stage", sa.String()),
        sa.column("description", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    now = datetime.utcnow()
    op.bulk_insert(gate, [{
        "key": "release.properties.short_term_rentals",
        "stage": "HIDDEN",
        "description": "Short-term rental Airbnb/Vrbo references, nightly pricing and turnover workflows",
        "created_at": now,
        "updated_at": now,
    }])


def downgrade():
    raise RuntimeError("Downgrade is intentionally disabled for short-term-rental channel records.")
