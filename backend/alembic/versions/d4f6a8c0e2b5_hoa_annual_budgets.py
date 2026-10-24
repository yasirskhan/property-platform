"""Association-specific annual budget adoption.

Revision ID: d4f6a8c0e2b5
Revises: c3e5a7b9d1f4
"""
from alembic import op
import sqlalchemy as sa

revision = "d4f6a8c0e2b5"
down_revision = "c3e5a7b9d1f4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hoa_annual_budgets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("calendar_year", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("lines_json", sa.Text(), nullable=False),
        sa.Column("total_income", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_expense", sa.Numeric(14, 2), nullable=False),
        sa.Column("reserve_allocation", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("board_seat_id", sa.Integer(), sa.ForeignKey("hoa_board_seats.id")),
        sa.Column("decision_maker_seat_id", sa.Integer(), sa.ForeignKey("hoa_board_seats.id")),
        sa.Column("decision_method", sa.String(16)),
        sa.Column("decided_on", sa.Date()),
        sa.Column("decided_at", sa.DateTime()),
        sa.Column("decision_note", sa.Text()),
        sa.Column("supporting_attachment_id", sa.Integer(), sa.ForeignKey("entity_attachments.id")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("decided_by_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("association_id", "property_id", "calendar_year", "revision",
                            name="uq_hoa_annual_budget_revision"),
    )
    op.create_index("ix_hoa_annual_budget_scope", "hoa_annual_budgets",
                    ["organization_id", "association_id", "property_id", "calendar_year", "is_active"])


def downgrade():
    op.drop_index("ix_hoa_annual_budget_scope", table_name="hoa_annual_budgets")
    op.drop_table("hoa_annual_budgets")
