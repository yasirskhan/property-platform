"""Encrypted restricted Form 8609 staff scans.

Revision ID: a3c5e7f9b1d4
Revises: f2a4b6c8d0e3
"""
from alembic import op
import sqlalchemy as sa

revision = "a3c5e7f9b1d4"
down_revision = "f2a4b6c8d0e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "affordable_lihtc_8609_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("building_id", sa.Integer(), nullable=False),
        sa.Column("encrypted_pdf", sa.LargeBinary(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["program_id"], ["affordable_programs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["building_id"], ["affordable_lihtc_buildings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for name in ("id", "organization_id", "property_id", "program_id", "building_id"):
        op.create_index(f"ix_affordable_lihtc_8609_documents_{name}",
                        "affordable_lihtc_8609_documents", [name])
    op.create_index("ix_lihtc_8609_document_scope",
                    "affordable_lihtc_8609_documents",
                    ["organization_id", "property_id", "program_id", "building_id"])


def downgrade() -> None:
    op.drop_index("ix_lihtc_8609_document_scope", table_name="affordable_lihtc_8609_documents")
    for name in ("building_id", "program_id", "property_id", "organization_id", "id"):
        op.drop_index(f"ix_affordable_lihtc_8609_documents_{name}",
                      table_name="affordable_lihtc_8609_documents")
    op.drop_table("affordable_lihtc_8609_documents")
