# ============================================================
# 00bc0d143eac_add_property_photos.py
# ------------------------------------------------------------
# Hand-written migration (Rule 9 / Rule 13: no autogenerate).
#
# Property photos — uploaded images stored via /uploads/.
# Supports:
#   * caption
#   * is_marketing (list/gallery flag)
#   * is_cover (single cover per property)
#   * sort_order (manual drag order)
#
# Revision ID: 00bc0d143eac
# Revises:     59a25b856f18  (parity fields head)
# ============================================================

"""add property photos

Revision ID: 00bc0d143eac
Revises: 59a25b856f18
Create Date: 2026-09-20
"""

from alembic import op
import sqlalchemy as sa


revision = "00bc0d143eac"
down_revision = "59a25b856f18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "property_photos",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "property_id",
            sa.Integer(),
            sa.ForeignKey("properties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # /uploads/xxxxx.jpg path
        sa.Column("url", sa.String(length=500), nullable=False),
        # server-side filename
        sa.Column("filename", sa.String(length=200), nullable=False),
        # user's original filename
        sa.Column("original_name", sa.String(length=300), nullable=True),
        sa.Column("content_type", sa.String(length=80), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("caption", sa.String(length=500), nullable=True),
        sa.Column(
            "is_marketing",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "is_cover",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("delete_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=True,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=True,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_property_photos_organization_id",
        "property_photos",
        ["organization_id"],
    )
    op.create_index(
        "ix_property_photos_property_id",
        "property_photos",
        ["property_id"],
    )
    op.create_index(
        "ix_property_photos_is_marketing",
        "property_photos",
        ["is_marketing"],
    )
    op.create_index(
        "ix_property_photos_is_cover",
        "property_photos",
        ["is_cover"],
    )
    op.create_index(
        "ix_property_photos_is_active",
        "property_photos",
        ["is_active"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_property_photos_is_active", table_name="property_photos"
    )
    op.drop_index(
        "ix_property_photos_is_cover", table_name="property_photos"
    )
    op.drop_index(
        "ix_property_photos_is_marketing", table_name="property_photos"
    )
    op.drop_index(
        "ix_property_photos_property_id", table_name="property_photos"
    )
    op.drop_index(
        "ix_property_photos_organization_id", table_name="property_photos"
    )
    op.drop_table("property_photos")