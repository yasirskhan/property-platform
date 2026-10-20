"""Maintenance group overrides and six configurable urgency/daypart policies.

Revision ID: c9e52d4f1b78
Revises: a0c7d4e19f32
"""
from alembic import op
import sqlalchemy as sa

revision = "c9e52d4f1b78"
down_revision = "a0c7d4e19f32"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "maintenance_dispatch_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("name_key", sa.String(100), nullable=False),
        sa.Column("timezone_name", sa.String(64), nullable=False),
        sa.Column("business_start_hour", sa.Integer(), nullable=False),
        sa.Column("business_end_hour", sa.Integer(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("organization_id", "name_key", name="uq_maintenance_group_name"),
        sa.CheckConstraint("business_start_hour BETWEEN 0 AND 23", name="ck_maintenance_start_hour"),
        sa.CheckConstraint("business_end_hour BETWEEN 1 AND 24", name="ck_maintenance_end_hour"),
        sa.CheckConstraint("business_end_hour > business_start_hour", name="ck_maintenance_business_hours"),
    )
    op.create_index("ix_maintenance_dispatch_groups_organization_id", "maintenance_dispatch_groups", ["organization_id"])
    op.create_table(
        "maintenance_dispatch_properties",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["group_id"], ["maintenance_dispatch_groups.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("property_id", name="uq_maintenance_dispatch_property"),
    )
    for col in ("organization_id", "group_id", "property_id"):
        op.create_index("ix_maintenance_dispatch_properties_" + col, "maintenance_dispatch_properties", [col])
    op.create_table(
        "maintenance_dispatch_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("urgency", sa.String(16), nullable=False),
        sa.Column("daypart", sa.String(20), nullable=False),
        sa.Column("first_target", sa.String(12), nullable=False),
        sa.Column("backup_target", sa.String(12), nullable=False),
        sa.Column("timeout_minutes", sa.Integer(), nullable=False),
        sa.Column("escalate", sa.Boolean(), nullable=False),
        sa.Column("primary_contact_user_id", sa.Integer(), nullable=True),
        sa.Column("backup_contact_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["group_id"], ["maintenance_dispatch_groups.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["primary_contact_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["backup_contact_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("group_id", "urgency", "daypart", name="uq_maintenance_dispatch_rule"),
        sa.CheckConstraint("urgency IN ('emergency','normal','low')", name="ck_maintenance_dispatch_urgency"),
        sa.CheckConstraint("daypart IN ('business_hours','after_hours')", name="ck_maintenance_dispatch_daypart"),
        sa.CheckConstraint("first_target IN ('crew','vendor','manager')", name="ck_maintenance_dispatch_first_target"),
        sa.CheckConstraint("backup_target IN ('vendor','manager')", name="ck_maintenance_dispatch_backup_target"),
        sa.CheckConstraint("timeout_minutes BETWEEN 1 AND 1440", name="ck_maintenance_dispatch_timeout"),
    )
    for col in ("organization_id", "group_id"):
        op.create_index("ix_maintenance_dispatch_rules_" + col, "maintenance_dispatch_rules", [col])


def downgrade():
    for table in ("maintenance_dispatch_rules", "maintenance_dispatch_properties", "maintenance_dispatch_groups"):
        if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM " + table + ")")).scalar():
            raise RuntimeError("Cannot discard maintenance dispatch configuration evidence")
    for col in ("organization_id", "group_id"):
        op.drop_index("ix_maintenance_dispatch_rules_" + col, table_name="maintenance_dispatch_rules")
    op.drop_table("maintenance_dispatch_rules")
    for col in ("organization_id", "group_id", "property_id"):
        op.drop_index("ix_maintenance_dispatch_properties_" + col, table_name="maintenance_dispatch_properties")
    op.drop_table("maintenance_dispatch_properties")
    op.drop_index("ix_maintenance_dispatch_groups_organization_id", table_name="maintenance_dispatch_groups")
    op.drop_table("maintenance_dispatch_groups")
