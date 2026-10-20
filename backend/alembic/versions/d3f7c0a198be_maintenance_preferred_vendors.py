"""Property/trade ranked vendor preferences; not automatic dispatch.

Revision ID: d3f7c0a198be
Revises: b5d0c8e7a214
"""
from alembic import op
import sqlalchemy as sa

revision = "d3f7c0a198be"
down_revision = "b5d0c8e7a214"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "maintenance_preferred_vendors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("trade", sa.String(100), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("vendor_id", sa.Integer(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT", name="fk_preferred_vendor_org"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="RESTRICT", name="fk_preferred_vendor_property"),
        sa.ForeignKeyConstraint(["vendor_id"], ["vendors.id"], ondelete="RESTRICT", name="fk_preferred_vendor_vendor"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL", name="fk_preferred_vendor_editor"),
        sa.UniqueConstraint("property_id", "trade", "rank", name="uq_preferred_vendor_rank"),
        sa.UniqueConstraint("property_id", "trade", "vendor_id", name="uq_preferred_vendor_company"),
        sa.CheckConstraint("rank BETWEEN 1 AND 3", name="ck_preferred_vendor_rank"),
    )
    op.create_index("ix_maintenance_preferred_vendors_organization_id", "maintenance_preferred_vendors", ["organization_id"])
    op.create_index("ix_maintenance_preferred_vendors_property_id", "maintenance_preferred_vendors", ["property_id"])


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM maintenance_preferred_vendors)")).scalar():
        raise RuntimeError("Cannot discard active preferred vendor configuration and evidence")
    op.drop_index("ix_maintenance_preferred_vendors_property_id", table_name="maintenance_preferred_vendors")
    op.drop_index("ix_maintenance_preferred_vendors_organization_id", table_name="maintenance_preferred_vendors")
    op.drop_table("maintenance_preferred_vendors")
