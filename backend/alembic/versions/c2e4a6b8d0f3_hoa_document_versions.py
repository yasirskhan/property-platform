"""Governing document evidence version lineage without duplicate file bytes.

Revision ID: c2e4a6b8d0f3
Revises: b1d3f5a7c9e2
"""
from alembic import op
import sqlalchemy as sa

revision = "c2e4a6b8d0f3"
down_revision = "b1d3f5a7c9e2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("hoa_governing_evidence") as batch:
        batch.add_column(sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("supersedes_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("replacement_request_key", sa.String(64), nullable=True))
        batch.create_foreign_key(
            "fk_hoa_governing_evidence_supersedes", "hoa_governing_evidence",
            ["supersedes_id"], ["id"], ondelete="RESTRICT",
        )
        batch.create_unique_constraint("uq_hoa_governing_evidence_supersedes_id", ["supersedes_id"])
        batch.create_unique_constraint(
            "uq_hoa_evidence_replacement_request",
            ["organization_id", "replacement_request_key"],
        )
        batch.create_check_constraint("ck_hoa_evidence_revision_positive", "revision >= 1")


def downgrade():
    with op.batch_alter_table("hoa_governing_evidence") as batch:
        batch.drop_constraint("ck_hoa_evidence_revision_positive", type_="check")
        batch.drop_constraint("uq_hoa_evidence_replacement_request", type_="unique")
        batch.drop_constraint("uq_hoa_governing_evidence_supersedes_id", type_="unique")
        batch.drop_constraint("fk_hoa_governing_evidence_supersedes", type_="foreignkey")
        batch.drop_column("replacement_request_key")
        batch.drop_column("supersedes_id")
        batch.drop_column("revision")
