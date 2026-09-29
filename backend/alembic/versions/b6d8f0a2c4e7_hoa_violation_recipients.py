"""Scope the staff violation recipient proposal to an authenticated user.

Revision ID: b6d8f0a2c4e7
Revises: a5c7e9f1b3d6
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "b6d8f0a2c4e7"
down_revision = "a5c7e9f1b3d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hoa_violation_recipient_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("hoa_violation_cases.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("contact_link_id", sa.Integer(), sa.ForeignKey("hoa_contact_links.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("matched_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for key in ("organization_id", "association_id", "property_id"):
        op.create_index(
            "ix_hoa_violation_recipient_drafts_" + key,
            "hoa_violation_recipient_drafts", [key],
        )
    op.create_index(
        "ix_hoa_violation_recipient_scope",
        "hoa_violation_recipient_drafts",
        ["organization_id", "association_id", "property_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_hoa_violation_recipient_scope", table_name="hoa_violation_recipient_drafts")
    for key in ("property_id", "association_id", "organization_id"):
        op.drop_index("ix_hoa_violation_recipient_drafts_" + key, table_name="hoa_violation_recipient_drafts")
    op.drop_table("hoa_violation_recipient_drafts")
