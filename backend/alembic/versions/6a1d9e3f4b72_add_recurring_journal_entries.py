"""add recurring journal entries

Revision ID: 6a1d9e3f4b72
Revises: 4d7f2a9c6e31
Create Date: 2026-09-24
"""

from alembic import op
import sqlalchemy as sa

revision = "6a1d9e3f4b72"
down_revision = "4d7f2a9c6e31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recurring_journal_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("day_of_month", sa.Integer(), nullable=False),
        sa.Column("next_post_date", sa.Date(), nullable=False),
        sa.Column("last_posted_date", sa.Date(), nullable=True),
        sa.Column("reference_number", sa.String(length=60), nullable=True),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recurring_journal_entries_organization_id",
        "recurring_journal_entries",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_recurring_journal_entries_next_post_date",
        "recurring_journal_entries",
        ["next_post_date"],
        unique=False,
    )
    op.create_index(
        "ix_recurring_journal_entries_created_by_id",
        "recurring_journal_entries",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        "ix_recurring_journal_entries_due",
        "recurring_journal_entries",
        ["organization_id", "is_active", "next_post_date"],
        unique=False,
    )

    op.create_table(
        "recurring_journal_entry_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recurring_journal_entry_id", sa.Integer(), nullable=False),
        sa.Column("gl_account_id", sa.Integer(), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=True),
        sa.Column("unit_id", sa.Integer(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("debit", sa.Numeric(12, 2), nullable=False),
        sa.Column("credit", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(
            ["recurring_journal_entry_id"],
            ["recurring_journal_entries.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["gl_account_id"], ["gl_accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["property_id"], ["properties.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"], ["units.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recurring_journal_entry_lines_recurring_journal_entry_id",
        "recurring_journal_entry_lines",
        ["recurring_journal_entry_id"],
        unique=False,
    )
    op.create_index(
        "ix_recurring_journal_entry_lines_gl_account_id",
        "recurring_journal_entry_lines",
        ["gl_account_id"],
        unique=False,
    )
    op.create_index(
        "ix_recurring_journal_entry_lines_property_id",
        "recurring_journal_entry_lines",
        ["property_id"],
        unique=False,
    )
    op.create_index(
        "ix_recurring_journal_entry_lines_owner_id",
        "recurring_journal_entry_lines",
        ["owner_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recurring_journal_entry_lines_owner_id",
        table_name="recurring_journal_entry_lines",
    )
    op.drop_index(
        "ix_recurring_journal_entry_lines_property_id",
        table_name="recurring_journal_entry_lines",
    )
    op.drop_index(
        "ix_recurring_journal_entry_lines_gl_account_id",
        table_name="recurring_journal_entry_lines",
    )
    op.drop_index(
        "ix_recurring_journal_entry_lines_recurring_journal_entry_id",
        table_name="recurring_journal_entry_lines",
    )
    op.drop_table("recurring_journal_entry_lines")
    op.drop_index(
        "ix_recurring_journal_entries_due",
        table_name="recurring_journal_entries",
    )
    op.drop_index(
        "ix_recurring_journal_entries_created_by_id",
        table_name="recurring_journal_entries",
    )
    op.drop_index(
        "ix_recurring_journal_entries_next_post_date",
        table_name="recurring_journal_entries",
    )
    op.drop_index(
        "ix_recurring_journal_entries_organization_id",
        table_name="recurring_journal_entries",
    )
    op.drop_table("recurring_journal_entries")
