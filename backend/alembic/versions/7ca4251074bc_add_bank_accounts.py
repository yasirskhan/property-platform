# ============================================================
# 7ca4251074bc_add_bank_accounts.py
# ------------------------------------------------------------
# Hand-written migration (Rule 9 / Rule 13: no autogenerate).
#
# Creates bank_accounts table + seeds two standard accounts
# per existing org:
#   Client Trust         -> GL 1150 (OPERATING)
#   Security Deposit Trust -> GL 1160 (ESCROW)
#
# AppFolio parity: matches Section 13 (two physical accounts)
# and Section 33 (ACH setup fields).
#
# Revision ID: 7ca4251074bc
# Revises:     4aa1c77e213c  (owner statements head)
# ============================================================

"""add bank accounts

Revision ID: 7ca4251074bc
Revises: 4aa1c77e213c
Create Date: 2026-09-20
"""

from alembic import op
import sqlalchemy as sa


revision = "7ca4251074bc"
down_revision = "4aa1c77e213c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------
    # Table: bank_accounts
    # ---------------------------------------------------------
    op.create_table(
        "bank_accounts",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("bank_name", sa.String(length=200), nullable=True),
        sa.Column("routing_number", sa.String(length=20), nullable=True),
        sa.Column("account_number", sa.String(length=40), nullable=True),
        sa.Column(
            "gl_account_id",
            sa.Integer(),
            sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # OPERATING | ESCROW
        sa.Column("account_type", sa.String(length=20), nullable=False,
                  server_default="OPERATING"),
        # CSV | NACHA (nullable — set later when ACH is configured)
        sa.Column("ach_format", sa.String(length=10), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=True,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=True,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_bank_accounts_organization_id",
        "bank_accounts",
        ["organization_id"],
    )
    op.create_index(
        "ix_bank_accounts_gl_account_id",
        "bank_accounts",
        ["gl_account_id"],
    )
    op.create_index(
        "ix_bank_accounts_is_active", "bank_accounts", ["is_active"]
    )
    # A GL account maps to at most one bank account per org.
    op.create_index(
        "ux_bank_accounts_org_gl",
        "bank_accounts",
        ["organization_id", "gl_account_id"],
        unique=True,
    )

    # ---------------------------------------------------------
    # Seed two standard accounts for each existing org
    # ---------------------------------------------------------
    bind = op.get_bind()
    orgs = bind.execute(sa.text("SELECT id FROM organizations")).fetchall()

    for (org_id,) in orgs:
        # Look up GL 1150 and 1160 for this org
        gl_1150 = bind.execute(
            sa.text(
                "SELECT id FROM gl_accounts "
                "WHERE organization_id = :org AND gl_number = '1150'"
            ),
            {"org": org_id},
        ).fetchone()
        gl_1160 = bind.execute(
            sa.text(
                "SELECT id FROM gl_accounts "
                "WHERE organization_id = :org AND gl_number = '1160'"
            ),
            {"org": org_id},
        ).fetchone()

        if gl_1150:
            existing = bind.execute(
                sa.text(
                    "SELECT id FROM bank_accounts "
                    "WHERE organization_id = :org AND gl_account_id = :gl"
                ),
                {"org": org_id, "gl": gl_1150[0]},
            ).fetchone()
            if not existing:
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO bank_accounts (
                            organization_id, name, bank_name,
                            routing_number, account_number,
                            gl_account_id, account_type, ach_format,
                            notes, is_active, created_at, updated_at
                        ) VALUES (
                            :org, 'Client Trust', NULL,
                            NULL, NULL,
                            :gl, 'OPERATING', NULL,
                            'Primary operating trust account', 1,
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                        """
                    ),
                    {"org": org_id, "gl": gl_1150[0]},
                )

        if gl_1160:
            existing = bind.execute(
                sa.text(
                    "SELECT id FROM bank_accounts "
                    "WHERE organization_id = :org AND gl_account_id = :gl"
                ),
                {"org": org_id, "gl": gl_1160[0]},
            ).fetchone()
            if not existing:
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO bank_accounts (
                            organization_id, name, bank_name,
                            routing_number, account_number,
                            gl_account_id, account_type, ach_format,
                            notes, is_active, created_at, updated_at
                        ) VALUES (
                            :org, 'Security Deposit Trust', NULL,
                            NULL, NULL,
                            :gl, 'ESCROW', NULL,
                            'Security deposit escrow account', 1,
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                        """
                    ),
                    {"org": org_id, "gl": gl_1160[0]},
                )


def downgrade() -> None:
    op.drop_index(
        "ux_bank_accounts_org_gl", table_name="bank_accounts"
    )
    op.drop_index(
        "ix_bank_accounts_is_active", table_name="bank_accounts"
    )
    op.drop_index(
        "ix_bank_accounts_gl_account_id", table_name="bank_accounts"
    )
    op.drop_index(
        "ix_bank_accounts_organization_id", table_name="bank_accounts"
    )
    op.drop_table("bank_accounts")