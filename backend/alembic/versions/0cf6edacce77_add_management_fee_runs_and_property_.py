# ============================================================
# 0cf6edacce77_add_management_fee_runs_and_property_.py
# ------------------------------------------------------------
# Hand-written migration (Rule 9 / Rule 13: no autogenerate).
#
# AppFolio-parity Management Fees:
#
#   1. properties gets 4 new fee-config columns:
#        mgmt_fee_pct       — percentage of eligible income
#        mgmt_fee_flat      — optional flat fee
#        mgmt_fee_min       — optional minimum
#        mgmt_fee_end_date  — Mgmt End Date (no fees after)
#
#   2. New table management_fee_runs — one row per property per
#      fee period, links to the GL transaction that posted it.
#
#   3. Seed ACCOUNTING.MANAGEMENT_FEES menu permission for every
#      existing org (visible to ADMIN/OWNER/MANAGER).
#
# Revision ID: 0cf6edacce77
# Revises:     bdc8b2be19d9  (property owners head)
# ============================================================

"""add management fee runs and property fee fields

Revision ID: 0cf6edacce77
Revises: bdc8b2be19d9
Create Date: 2026-09-20
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0cf6edacce77"
down_revision = "bdc8b2be19d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------
    # 1. Add fee fields to properties
    # ---------------------------------------------------------
    with op.batch_alter_table("properties") as batch_op:
        batch_op.add_column(
            sa.Column(
                "mgmt_fee_pct",
                sa.Numeric(precision=5, scale=2),
                nullable=True,
                server_default="0.00",
            )
        )
        batch_op.add_column(
            sa.Column(
                "mgmt_fee_flat",
                sa.Numeric(precision=14, scale=2),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "mgmt_fee_min",
                sa.Numeric(precision=14, scale=2),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("mgmt_fee_end_date", sa.Date(), nullable=True)
        )

    # ---------------------------------------------------------
    # 2. Create management_fee_runs table
    # ---------------------------------------------------------
    op.create_table(
        "management_fee_runs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "property_id",
            sa.Integer(),
            sa.ForeignKey("properties.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),

        # Eligible income totals used in the calculation
        sa.Column(
            "rent_income_total",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "other_fee_income_total",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default="0.00",
        ),

        # Percentages used (snapshot at run time)
        sa.Column(
            "rent_fee_pct",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default="0.00",
        )
        ,
        sa.Column(
            "other_fee_pct",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default="0.00",
        ),

        # Computed fee amounts
        sa.Column(
            "rent_fee_amount",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "other_fee_amount",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "total_fee",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default="0.00",
        ),

        # Which expense account was debited (usually 6001)
        sa.Column(
            "expense_gl_account_id",
            sa.Integer(),
            sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # Which cash/trust account was credited (usually 1150)
        sa.Column(
            "cash_gl_account_id",
            sa.Integer(),
            sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),

        sa.Column(
            "gl_transaction_id",
            sa.Integer(),
            sa.ForeignKey("gl_transactions.id", ondelete="SET NULL"),
            nullable=True,
        ),

        sa.Column("notes", sa.Text(), nullable=True),

        # Reversal bookkeeping
        sa.Column(
            "is_reversed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "reversal_of_id",
            sa.Integer(),
            sa.ForeignKey("management_fee_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),

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
        "ix_mgmt_fee_runs_org", "management_fee_runs", ["organization_id"]
    )
    op.create_index(
        "ix_mgmt_fee_runs_property", "management_fee_runs", ["property_id"]
    )
    op.create_index(
        "ix_mgmt_fee_runs_period", "management_fee_runs", ["period_start", "period_end"]
    )
    op.create_index(
        "ix_mgmt_fee_runs_gl_txn", "management_fee_runs", ["gl_transaction_id"]
    )
    op.create_index(
        "ix_mgmt_fee_runs_is_active", "management_fee_runs", ["is_active"]
    )

    # ---------------------------------------------------------
    # 3. Seed ACCOUNTING.MANAGEMENT_FEES menu permission for every org
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
                    "AND menu_key = 'ACCOUNTING.MANAGEMENT_FEES'"
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
                        :org, :role, 'ACCOUNTING.MANAGEMENT_FEES', :visible,
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
            "WHERE menu_key = 'ACCOUNTING.MANAGEMENT_FEES'"
        )
    )

    op.drop_index("ix_mgmt_fee_runs_is_active", table_name="management_fee_runs")
    op.drop_index("ix_mgmt_fee_runs_gl_txn", table_name="management_fee_runs")
    op.drop_index("ix_mgmt_fee_runs_period", table_name="management_fee_runs")
    op.drop_index("ix_mgmt_fee_runs_property", table_name="management_fee_runs")
    op.drop_index("ix_mgmt_fee_runs_org", table_name="management_fee_runs")
    op.drop_table("management_fee_runs")

    with op.batch_alter_table("properties") as batch_op:
        batch_op.drop_column("mgmt_fee_end_date")
        batch_op.drop_column("mgmt_fee_min")
        batch_op.drop_column("mgmt_fee_flat")
        batch_op.drop_column("mgmt_fee_pct")