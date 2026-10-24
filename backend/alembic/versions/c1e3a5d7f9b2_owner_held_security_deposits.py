"""owner held security deposit key accounts and lease selection

Revision ID: c1e3a5d7f9b2
Revises: b6d8f0a2c4e7
"""
from alembic import op
import sqlalchemy as sa

revision = "c1e3a5d7f9b2"
down_revision = "b6d8f0a2c4e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounting_key_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("key_type", sa.String(length=50), nullable=False),
        sa.Column("gl_account_id", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["gl_account_id"], ["gl_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "organization_id",
            "key_type",
            "gl_account_id",
            name="uq_accounting_key_account_org_type_gl",
        ),
    )
    op.create_index(
        "ix_accounting_key_accounts_organization_id",
        "accounting_key_accounts",
        ["organization_id"],
    )
    op.create_index(
        "ix_accounting_key_accounts_key_type",
        "accounting_key_accounts",
        ["key_type"],
    )
    op.create_index(
        "ix_accounting_key_accounts_gl_account_id",
        "accounting_key_accounts",
        ["gl_account_id"],
    )
    op.create_index(
        "ix_accounting_key_accounts_org_type",
        "accounting_key_accounts",
        ["organization_id", "key_type"],
    )

    with op.batch_alter_table("leases") as batch_op:
        batch_op.add_column(
            sa.Column("security_deposit_gl_account_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_leases_security_deposit_gl_account_id",
            "gl_accounts",
            ["security_deposit_gl_account_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            "ix_leases_security_deposit_gl_account_id",
            ["security_deposit_gl_account_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("leases") as batch_op:
        batch_op.drop_index("ix_leases_security_deposit_gl_account_id")
        batch_op.drop_constraint(
            "fk_leases_security_deposit_gl_account_id",
            type_="foreignkey",
        )
        batch_op.drop_column("security_deposit_gl_account_id")

    op.drop_index("ix_accounting_key_accounts_org_type", table_name="accounting_key_accounts")
    op.drop_index("ix_accounting_key_accounts_gl_account_id", table_name="accounting_key_accounts")
    op.drop_index("ix_accounting_key_accounts_key_type", table_name="accounting_key_accounts")
    op.drop_index("ix_accounting_key_accounts_organization_id", table_name="accounting_key_accounts")
    op.drop_table("accounting_key_accounts")
