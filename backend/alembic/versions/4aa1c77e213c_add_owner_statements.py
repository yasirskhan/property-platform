# ============================================================
# 4aa1c77e213c_add_owner_statements.py
# ------------------------------------------------------------
# Hand-written migration (Rule 9 / Rule 13: no autogenerate).
#
# Creates:
#   1. owner_statements table — frozen snapshot documents
#   2. Seed ACCOUNTING.OWNER_STATEMENTS menu permission for
#      every existing org
#
# Snapshot model (AppFolio parity):
#   A statement is a historical document. Once generated, the
#   numbers never change — the per-property breakdown lives in
#   a JSON blob so GL corrections later don't rewrite history.
#
# Revision ID: 4aa1c77e213c
# Revises:     0cf6edacce77  (management fees head)
# ============================================================

"""add owner statements

Revision ID: 4aa1c77e213c
Revises: 0cf6edacce77
Create Date: 2026-09-20
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4aa1c77e213c"
down_revision = "0cf6edacce77"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "owner_statements",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),

        # Period this statement covers
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),

        # Snapshot totals (sum across all properties)
        sa.Column("total_beginning_cash", sa.Numeric(14, 2),
                  nullable=False, server_default="0.00"),
        sa.Column("total_ending_cash", sa.Numeric(14, 2),
                  nullable=False, server_default="0.00"),
        sa.Column("total_income", sa.Numeric(14, 2),
                  nullable=False, server_default="0.00"),
        sa.Column("total_expense", sa.Numeric(14, 2),
                  nullable=False, server_default="0.00"),
        sa.Column("total_net", sa.Numeric(14, 2),
                  nullable=False, server_default="0.00"),

        # Per-property breakdown + transaction list, JSON blob
        sa.Column("property_data", sa.Text(), nullable=False, server_default="[]"),

        # Optional generated PDF
        sa.Column("pdf_url", sa.String(length=500), nullable=True),

        sa.Column("notes", sa.Text(), nullable=True),

        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "generated_by_id",
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
        "ix_owner_statements_org", "owner_statements", ["organization_id"]
    )
    op.create_index(
        "ix_owner_statements_owner", "owner_statements", ["owner_id"]
    )
    op.create_index(
        "ix_owner_statements_period",
        "owner_statements",
        ["period_start", "period_end"],
    )
    op.create_index(
        "ix_owner_statements_is_active", "owner_statements", ["is_active"]
    )

    # ---------------------------------------------------------
    # Seed ACCOUNTING.OWNER_STATEMENTS menu permission
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
                    "AND menu_key = 'ACCOUNTING.OWNER_STATEMENTS'"
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
                        :org, :role, 'ACCOUNTING.OWNER_STATEMENTS', :visible,
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
            "WHERE menu_key = 'ACCOUNTING.OWNER_STATEMENTS'"
        )
    )

    op.drop_index(
        "ix_owner_statements_is_active", table_name="owner_statements"
    )
    op.drop_index(
        "ix_owner_statements_period", table_name="owner_statements"
    )
    op.drop_index(
        "ix_owner_statements_owner", table_name="owner_statements"
    )
    op.drop_index(
        "ix_owner_statements_org", table_name="owner_statements"
    )
    op.drop_table("owner_statements")