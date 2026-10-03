"""HOA reserve movement planning snapshots; no external payments.

Revision ID: e2f4a6c8b0d3
Revises: d1e3f5a7b9c2
"""
from alembic import op
import sqlalchemy as sa

revision = "e2f4a6c8b0d3"
down_revision = "d1e3f5a7b9c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hoa_reserve_movement_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reserve_gl_account_id", sa.Integer(), sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("counterparty_gl_account_id", sa.Integer(), sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("planned_on", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("memo", sa.String(240), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("cancelled_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("cancelled_at", sa.DateTime()),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_hoa_reserve_plan_idempotency"),
    )
    for name in ("organization_id", "association_id", "property_id", "reserve_gl_account_id", "counterparty_gl_account_id"):
        op.create_index("ix_hoa_reserve_movement_drafts_" + name, "hoa_reserve_movement_drafts", [name])
    op.create_index("ix_hoa_reserve_plan_scope", "hoa_reserve_movement_drafts",
                    ["organization_id", "association_id", "property_id"])


def downgrade() -> None:
    op.drop_index("ix_hoa_reserve_plan_scope", table_name="hoa_reserve_movement_drafts")
    for name in ("counterparty_gl_account_id", "reserve_gl_account_id", "property_id", "association_id", "organization_id"):
        op.drop_index("ix_hoa_reserve_movement_drafts_" + name, table_name="hoa_reserve_movement_drafts")
    op.drop_table("hoa_reserve_movement_drafts")
