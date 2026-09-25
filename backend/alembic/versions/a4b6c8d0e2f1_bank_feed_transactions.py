"""add durable provider-neutral bank feed transactions

Revision ID: a4b6c8d0e2f1
Revises: f2a4c6e8b0d5
"""
from alembic import op
import sqlalchemy as sa

revision = "a4b6c8d0e2f1"
down_revision = "f2a4c6e8b0d5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bank_feed_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("bank_account_id", sa.Integer(), nullable=False),
        sa.Column("source_provider", sa.String(length=40), nullable=False, server_default="CSV"),
        sa.Column("external_id", sa.String(length=200), nullable=True),
        sa.Column("import_key", sa.String(length=64), nullable=False),
        sa.Column("posted_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("payee", sa.String(length=300), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("reference_number", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="UNMATCHED"),
        sa.Column("matched_source_type", sa.String(length=30), nullable=True),
        sa.Column("matched_source_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bank_account_id"], ["bank_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "organization_id",
            "bank_account_id",
            "import_key",
            name="uq_bank_feed_org_bank_import_key",
        ),
        sa.UniqueConstraint(
            "bank_account_id",
            "matched_source_type",
            "matched_source_id",
            name="uq_bank_feed_bank_match",
        ),
    )
    for column in [
        "organization_id",
        "bank_account_id",
        "source_provider",
        "external_id",
        "import_key",
        "posted_date",
        "status",
        "matched_source_type",
        "matched_source_id",
    ]:
        op.create_index(
            f"ix_bank_feed_transactions_{column}",
            "bank_feed_transactions",
            [column],
        )


def downgrade():
    for column in reversed([
        "organization_id",
        "bank_account_id",
        "source_provider",
        "external_id",
        "import_key",
        "posted_date",
        "status",
        "matched_source_type",
        "matched_source_id",
    ]):
        op.drop_index(
            f"ix_bank_feed_transactions_{column}",
            table_name="bank_feed_transactions",
        )
    op.drop_table("bank_feed_transactions")
