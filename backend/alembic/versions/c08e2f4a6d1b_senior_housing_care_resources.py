"""Phase 4.11 senior-housing care coordination resource placeholders."""
from alembic import op
import sqlalchemy as sa


revision = "c08e2f4a6d1b"
down_revision = "bf7d1e3a5c9f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "senior_care_resources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_type", sa.String(length=40), nullable=False),
        sa.Column("provider_name", sa.String(length=180), nullable=False),
        sa.Column("contact_name", sa.String(length=180), nullable=True),
        sa.Column("phone", sa.String(length=60), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("reference_url", sa.String(length=500), nullable=True),
        sa.Column("availability_notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "property_id",
            "resource_type",
            "provider_name",
            name="uq_senior_care_resource_property_type_provider",
        ),
    )
    op.create_index("ix_senior_care_resources_organization_id", "senior_care_resources", ["organization_id"])
    op.create_index("ix_senior_care_resources_property_id", "senior_care_resources", ["property_id"])
    op.create_index(
        "ix_senior_care_resource_scope",
        "senior_care_resources",
        ["organization_id", "property_id", "is_active"],
    )


def downgrade():
    raise RuntimeError("Downgrade is intentionally disabled for senior-housing care resource records.")
