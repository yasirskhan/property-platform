"""add release gate storage

Revision ID: b7d5e9a3c2f1
Revises: a6e4c8f2b1d0
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa


revision = "b7d5e9a3c2f1"
down_revision = "a6e4c8f2b1d0"
branch_labels = None
depends_on = None


release_stage = sa.Enum(
    "HIDDEN",
    "BETA",
    "ROLLOUT",
    "ALL_ORGS",
    name="release_stage",
    native_enum=False,
    length=20,
)


def upgrade() -> None:
    op.create_table(
        "release_gates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column(
            "stage",
            release_stage,
            nullable=False,
            server_default="HIDDEN",
        ),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_release_gates_id", "release_gates", ["id"], unique=False)
    op.create_index("ix_release_gates_key", "release_gates", ["key"], unique=True)
    op.create_index("ix_release_gates_stage", "release_gates", ["stage"], unique=False)

    op.create_table(
        "release_gate_organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("release_gate_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["release_gate_id"],
            ["release_gates.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "release_gate_id",
            "organization_id",
            name="uq_release_gate_organization",
        ),
    )
    op.create_index(
        "ix_release_gate_organizations_release_gate_id",
        "release_gate_organizations",
        ["release_gate_id"],
        unique=False,
    )
    op.create_index(
        "ix_release_gate_organizations_organization_id",
        "release_gate_organizations",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_release_gate_organizations_organization_id",
        table_name="release_gate_organizations",
    )
    op.drop_index(
        "ix_release_gate_organizations_release_gate_id",
        table_name="release_gate_organizations",
    )
    op.drop_table("release_gate_organizations")

    op.drop_index("ix_release_gates_stage", table_name="release_gates")
    op.drop_index("ix_release_gates_key", table_name="release_gates")
    op.drop_index("ix_release_gates_id", table_name="release_gates")
    op.drop_table("release_gates")
