"""Add property-scoped staff guest cards attached to leasing prospects.

Revision ID: f6e8a0c2d4e5
Revises: f5e7a9c1d3e4
"""
from alembic import op
import sqlalchemy as sa
revision = "f6e8a0c2d4e5"
down_revision = "f5e7a9c1d3e4"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "leasing_guest_cards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prospect_id", sa.Integer(), sa.ForeignKey("leasing_prospects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("visit_on", sa.Date(), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id", ondelete="RESTRICT")),
        sa.Column("attended", sa.Boolean(), nullable=False),
        sa.Column("next_step", sa.String(24), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "prospect_id", "visit_on", name="uq_guest_card_org_prospect_day"),
    )
    op.create_index("ix_leasing_guest_cards_id", "leasing_guest_cards", ["id"])
    op.create_index("ix_leasing_guest_cards_organization_id", "leasing_guest_cards", ["organization_id"])
    op.create_index("ix_leasing_guest_cards_prospect_id", "leasing_guest_cards", ["prospect_id"])
    op.create_index("ix_guest_cards_org_visit", "leasing_guest_cards", ["organization_id", "visit_on"])

def downgrade():
    op.drop_index("ix_guest_cards_org_visit", table_name="leasing_guest_cards")
    op.drop_index("ix_leasing_guest_cards_prospect_id", table_name="leasing_guest_cards")
    op.drop_index("ix_leasing_guest_cards_organization_id", table_name="leasing_guest_cards")
    op.drop_index("ix_leasing_guest_cards_id", table_name="leasing_guest_cards")
    op.drop_table("leasing_guest_cards")
