"""add fraud review foundation

Revision ID: 6f1a9c4d2e7b
Revises: 2d4f8a6c9b10
Create Date: 2026-09-24
"""

from alembic import op
import sqlalchemy as sa


revision = "6f1a9c4d2e7b"
down_revision = "2d4f8a6c9b10"
branch_labels = None
depends_on = None


fraud_case_status = sa.Enum(
    "OPEN",
    "IN_REVIEW",
    "APPROVED",
    "BLOCKED",
    "DISMISSED",
    name="fraud_case_status",
    native_enum=False,
    create_constraint=True,
)

fraud_risk_level = sa.Enum(
    "LOW",
    "MEDIUM",
    "HIGH",
    "CRITICAL",
    name="fraud_risk_level",
    native_enum=False,
    create_constraint=True,
)

fraud_signal_severity = sa.Enum(
    "LOW",
    "MEDIUM",
    "HIGH",
    "CRITICAL",
    name="fraud_signal_severity",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    op.create_table(
        "fraud_cases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("checkout_session_id", sa.Integer(), nullable=True),
        sa.Column(
            "provider",
            sa.String(length=32),
            server_default="internal",
            nullable=False,
        ),
        sa.Column("provider_case_id", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            fraud_case_status,
            server_default="OPEN",
            nullable=False,
        ),
        sa.Column(
            "risk_level",
            fraud_risk_level,
            server_default="LOW",
            nullable=False,
        ),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("details", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("reviewed_by_platform_user_id", sa.Integer(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)",
            name="ck_fraud_cases_risk_score",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["checkout_session_id"],
            ["billing_checkout_sessions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_platform_user_id"],
            ["platform_users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "provider_case_id",
            name="uq_fraud_cases_provider_case",
        ),
    )
    op.create_index("ix_fraud_cases_organization_id", "fraud_cases", ["organization_id"])
    op.create_index("ix_fraud_cases_checkout_session_id", "fraud_cases", ["checkout_session_id"])
    op.create_index("ix_fraud_cases_provider", "fraud_cases", ["provider"])
    op.create_index("ix_fraud_cases_status", "fraud_cases", ["status"])
    op.create_index("ix_fraud_cases_risk_level", "fraud_cases", ["risk_level"])
    op.create_index(
        "ix_fraud_cases_reviewed_by_platform_user_id",
        "fraud_cases",
        ["reviewed_by_platform_user_id"],
    )
    op.create_index("ix_fraud_cases_resolved_at", "fraud_cases", ["resolved_at"])
    op.create_index("ix_fraud_cases_created_at", "fraud_cases", ["created_at"])

    op.create_table(
        "fraud_signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fraud_case_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("signal_type", sa.String(length=120), nullable=False),
        sa.Column("severity", fraud_signal_severity, nullable=False),
        sa.Column("provider_event_id", sa.String(length=255), nullable=True),
        sa.Column("signal_value", sa.String(length=255), nullable=True),
        sa.Column("payload", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["fraud_case_id"],
            ["fraud_cases.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source",
            "provider_event_id",
            name="uq_fraud_signals_source_event",
        ),
    )
    op.create_index("ix_fraud_signals_fraud_case_id", "fraud_signals", ["fraud_case_id"])
    op.create_index("ix_fraud_signals_organization_id", "fraud_signals", ["organization_id"])
    op.create_index("ix_fraud_signals_source", "fraud_signals", ["source"])
    op.create_index("ix_fraud_signals_signal_type", "fraud_signals", ["signal_type"])
    op.create_index("ix_fraud_signals_severity", "fraud_signals", ["severity"])
    op.create_index("ix_fraud_signals_created_at", "fraud_signals", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_fraud_signals_created_at", table_name="fraud_signals")
    op.drop_index("ix_fraud_signals_severity", table_name="fraud_signals")
    op.drop_index("ix_fraud_signals_signal_type", table_name="fraud_signals")
    op.drop_index("ix_fraud_signals_source", table_name="fraud_signals")
    op.drop_index("ix_fraud_signals_organization_id", table_name="fraud_signals")
    op.drop_index("ix_fraud_signals_fraud_case_id", table_name="fraud_signals")
    op.drop_table("fraud_signals")

    op.drop_index("ix_fraud_cases_created_at", table_name="fraud_cases")
    op.drop_index("ix_fraud_cases_resolved_at", table_name="fraud_cases")
    op.drop_index(
        "ix_fraud_cases_reviewed_by_platform_user_id",
        table_name="fraud_cases",
    )
    op.drop_index("ix_fraud_cases_risk_level", table_name="fraud_cases")
    op.drop_index("ix_fraud_cases_status", table_name="fraud_cases")
    op.drop_index("ix_fraud_cases_provider", table_name="fraud_cases")
    op.drop_index("ix_fraud_cases_checkout_session_id", table_name="fraud_cases")
    op.drop_index("ix_fraud_cases_organization_id", table_name="fraud_cases")
    op.drop_table("fraud_cases")
