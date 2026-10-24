"""Staff HOA procedure configuration and internal review cases, no legal issuance.

Revision ID: b2d4f6a8c0e1
Revises: a1c3e5f7b9d0
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "b2d4f6a8c0e1"
down_revision = "a1c3e5f7b9d0"
branch_labels = None
depends_on = None


def _common():
    return [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("association_id", sa.Integer(), sa.ForeignKey("hoa_associations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
    ]


def _stewardship():
    return [
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "hoa_procedure_policies",
        *_common(),
        sa.Column("jurisdiction_state", sa.String(64)),
        sa.Column("jurisdiction_locality", sa.String(160)),
        sa.Column("notice_preparation_days", sa.Integer()),
        sa.Column("cure_preparation_days", sa.Integer()),
        sa.Column("hearing_request_days", sa.Integer()),
        sa.Column("proposed_fine_cap", sa.Numeric(14, 2)),
        sa.Column("draft_notice_text", sa.Text()),
        sa.Column("supporting_evidence_id", sa.Integer(),
                  sa.ForeignKey("hoa_governing_evidence.id", ondelete="RESTRICT")),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        *_stewardship(),
        sa.UniqueConstraint("association_id", "property_id", name="uq_hoa_procedure_association_property"),
    )
    for col in ("id", "organization_id", "association_id", "property_id"):
        op.create_index(f"ix_hoa_procedure_policies_{col}", "hoa_procedure_policies", [col])
    op.create_index("ix_hoa_procedure_scope", "hoa_procedure_policies",
                    ["organization_id", "association_id", "property_id"])

    op.create_table(
        "hoa_violation_cases",
        *_common(),
        sa.Column("observation_id", sa.Integer(),
                  sa.ForeignKey("hoa_observations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False, server_default="OPEN"),
        sa.Column("draft_notice_on", sa.Date()),
        sa.Column("tentative_cure_on", sa.Date()),
        sa.Column("tentative_hearing_on", sa.Date()),
        sa.Column("proposed_fine", sa.Numeric(14, 2)),
        sa.Column("staff_resolution", sa.Text()),
        sa.Column("policy_revision", sa.Integer()),
        *_stewardship(),
        sa.UniqueConstraint("organization_id", "observation_id", name="uq_hoa_case_org_observation"),
    )
    for col in ("id", "organization_id", "association_id", "property_id", "observation_id"):
        op.create_index(f"ix_hoa_violation_cases_{col}", "hoa_violation_cases", [col])
    op.create_index("ix_hoa_case_scope", "hoa_violation_cases",
                    ["organization_id", "association_id", "property_id", "stage"])


def downgrade() -> None:
    op.drop_index("ix_hoa_case_scope", table_name="hoa_violation_cases")
    for col in ("observation_id", "property_id", "association_id", "organization_id", "id"):
        op.drop_index(f"ix_hoa_violation_cases_{col}", table_name="hoa_violation_cases")
    op.drop_table("hoa_violation_cases")
    op.drop_index("ix_hoa_procedure_scope", table_name="hoa_procedure_policies")
    for col in ("property_id", "association_id", "organization_id", "id"):
        op.drop_index(f"ix_hoa_procedure_policies_{col}", table_name="hoa_procedure_policies")
    op.drop_table("hoa_procedure_policies")
