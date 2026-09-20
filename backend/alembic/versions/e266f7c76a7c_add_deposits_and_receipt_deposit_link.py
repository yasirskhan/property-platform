# ============================================================
# e266f7c76a7c_add_deposits_and_receipt_deposit_link.py
# ------------------------------------------------------------
# Hand-written migration (Rule 9 / Rule 13: no autogenerate).
#
# Creates:
#   1. deposits table       (bank deposit batches)
#   2. deposit_lines table  (which receipts are in a batch)
#   3. Seed ACCOUNTING.DEPOSITS menu permission for every org
#
# NOTE: We do NOT add is_deposited / deposit_id columns to
# receipts. deposit_lines is the single source of truth for
# "is this receipt deposited?". This avoids SQLite's
# batch_alter_table FK issues and stays consistent on Postgres.
#
# Revision ID: e266f7c76a7c
# Revises:     71eda8a9ba77  (Bills head)
# ============================================================

"""add deposits and deposit lines

Revision ID: e266f7c76a7c
Revises: 71eda8a9ba77
Create Date: 2026-09-20
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e266f7c76a7c"
down_revision = "71eda8a9ba77"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------
    # Table 1: deposits
    # ---------------------------------------------------------
    op.create_table(
        "deposits",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "bank_gl_account_id",
            sa.Integer(),
            sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("deposit_date", sa.Date(), nullable=False),
        sa.Column("deposit_number", sa.String(length=40), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column(
            "total",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default="0.00",
        ),
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
        "ix_deposits_organization_id", "deposits", ["organization_id"]
    )
    op.create_index(
        "ix_deposits_bank_gl_account_id", "deposits", ["bank_gl_account_id"]
    )
    op.create_index(
        "ix_deposits_deposit_date", "deposits", ["deposit_date"]
    )
    op.create_index(
        "ix_deposits_deposit_number", "deposits", ["deposit_number"]
    )
    op.create_index("ix_deposits_is_active", "deposits", ["is_active"])

    # ---------------------------------------------------------
    # Table 2: deposit_lines
    # ---------------------------------------------------------
    op.create_table(
        "deposit_lines",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "deposit_id",
            sa.Integer(),
            sa.ForeignKey("deposits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "receipt_id",
            sa.Integer(),
            sa.ForeignKey("receipts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=True,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_deposit_lines_organization_id",
        "deposit_lines",
        ["organization_id"],
    )
    op.create_index(
        "ix_deposit_lines_deposit_id", "deposit_lines", ["deposit_id"]
    )
    op.create_index(
        "ix_deposit_lines_receipt_id", "deposit_lines", ["receipt_id"]
    )
    # A receipt can be in AT MOST ONE deposit.
    op.create_index(
        "ux_deposit_lines_receipt_id",
        "deposit_lines",
        ["receipt_id"],
        unique=True,
    )

    # ---------------------------------------------------------
    # Seed ACCOUNTING.DEPOSITS menu permission for every org.
    # Visible: ADMIN / OWNER / MANAGER
    # Hidden:  CREW / TENANT / VENDOR / VENDOR_CREW / APPLICANT
    # Idempotent: skips rows that already exist.
    # ---------------------------------------------------------
    bind = op.get_bind()
    orgs = bind.execute(sa.text("SELECT id FROM organizations")).fetchall()

    visible_roles = ("ADMIN", "OWNER", "MANAGER")
    hidden_roles = ("CREW", "TENANT", "VENDOR", "VENDOR_CREW", "APPLICANT")
    all_roles = visible_roles + hidden_roles

    for (org_id,) in orgs:
        for role in all_roles:
            existing = bind.execute(
                sa.text(
                    "SELECT id FROM menu_permissions "
                    "WHERE organization_id = :org "
                    "AND role = :role "
                    "AND menu_key = 'ACCOUNTING.DEPOSITS'"
                ),
                {"org": org_id, "role": role},
            ).fetchone()
            if existing:
                continue

            visible = 1 if role in visible_roles else 0
            bind.execute(
                sa.text(
                    """
                    INSERT INTO menu_permissions (
                        organization_id, role, menu_key, visible,
                        created_at, updated_at
                    ) VALUES (
                        :org, :role, 'ACCOUNTING.DEPOSITS', :visible,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {"org": org_id, "role": role, "visible": visible},
            )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM menu_permissions "
            "WHERE menu_key = 'ACCOUNTING.DEPOSITS'"
        )
    )

    op.drop_index("ux_deposit_lines_receipt_id", table_name="deposit_lines")
    op.drop_index("ix_deposit_lines_receipt_id", table_name="deposit_lines")
    op.drop_index("ix_deposit_lines_deposit_id", table_name="deposit_lines")
    op.drop_index(
        "ix_deposit_lines_organization_id", table_name="deposit_lines"
    )
    op.drop_table("deposit_lines")

    op.drop_index("ix_deposits_is_active", table_name="deposits")
    op.drop_index("ix_deposits_deposit_number", table_name="deposits")
    op.drop_index("ix_deposits_deposit_date", table_name="deposits")
    op.drop_index("ix_deposits_bank_gl_account_id", table_name="deposits")
    op.drop_index("ix_deposits_organization_id", table_name="deposits")
    op.drop_table("deposits")