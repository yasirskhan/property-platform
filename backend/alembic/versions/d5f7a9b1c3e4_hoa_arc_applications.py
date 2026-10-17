"""HOA ARC applications, private document links, and staff review history.

Revision ID: d5f7a9b1c3e4
Revises: c4e6a8d0f2b1
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "d5f7a9b1c3e4"
down_revision = "c4e6a8d0f2b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hoa_arc_applications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("intake_id", sa.Integer(), sa.ForeignKey("hoa_arc_intakes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("applicant_contact_link_id", sa.Integer(), sa.ForeignKey("hoa_contact_links.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("submitted_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("decision_preparation", sa.String(length=16), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "intake_id", name="uq_hoa_arc_application_org_intake"),
    )
    for name in ("id", "organization_id", "association_id", "property_id", "intake_id", "applicant_contact_link_id"):
        op.create_index(f"ix_hoa_arc_applications_{name}", "hoa_arc_applications", [name])
    op.create_index("ix_hoa_arc_application_scope", "hoa_arc_applications",
                    ["organization_id", "association_id", "property_id", "is_active"])

    op.create_table(
        "hoa_arc_application_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("hoa_arc_applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attachment_id", sa.Integer(), sa.ForeignKey("entity_attachments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("application_id", "attachment_id", name="uq_hoa_arc_application_attachment"),
    )
    for name in ("id", "organization_id", "application_id", "property_id", "attachment_id"):
        op.create_index(f"ix_hoa_arc_application_attachments_{name}", "hoa_arc_application_attachments", [name])
    op.create_index("ix_hoa_arc_attachment_scope", "hoa_arc_application_attachments",
                    ["organization_id", "application_id", "property_id"])

    op.create_table(
        "hoa_arc_review_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("hoa_arc_applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("staff_note", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for name in ("id", "organization_id", "application_id"):
        op.create_index(f"ix_hoa_arc_review_events_{name}", "hoa_arc_review_events", [name])
    op.create_index("ix_hoa_arc_review_event_scope", "hoa_arc_review_events",
                    ["organization_id", "application_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_hoa_arc_review_event_scope", table_name="hoa_arc_review_events")
    for name in ("application_id", "organization_id", "id"):
        op.drop_index(f"ix_hoa_arc_review_events_{name}", table_name="hoa_arc_review_events")
    op.drop_table("hoa_arc_review_events")
    op.drop_index("ix_hoa_arc_attachment_scope", table_name="hoa_arc_application_attachments")
    for name in ("attachment_id", "property_id", "application_id", "organization_id", "id"):
        op.drop_index(f"ix_hoa_arc_application_attachments_{name}", table_name="hoa_arc_application_attachments")
    op.drop_table("hoa_arc_application_attachments")
    op.drop_index("ix_hoa_arc_application_scope", table_name="hoa_arc_applications")
    for name in ("applicant_contact_link_id", "intake_id", "property_id", "association_id", "organization_id", "id"):
        op.drop_index(f"ix_hoa_arc_applications_{name}", table_name="hoa_arc_applications")
    op.drop_table("hoa_arc_applications")
