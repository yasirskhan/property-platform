# ============================================================
# 59a25b856f18_add_phase3_parity_fields.py
# ------------------------------------------------------------
# Hand-written migration (Rule 9 / Rule 13: no autogenerate).
#
# Closes small AppFolio parity gaps in the Phase 3 tabs +
# diagnostics:
#
#   property_amenities.fee_amount             (numeric 14,2)
#   property_amenities.availability_status    (string 30)
#   property_amenities.delete_reason          (text)
#
#   property_appliances.condition             (string 30)
#   property_appliances.delete_reason         (text)
#
#   property_improvements.warranty_expires    (date)
#   property_improvements.delete_reason       (text)
#
#   gl_accounts.must_clear                    (boolean, default 0)
#       Powers the real "Positive Balance on Fee Accounts"
#       diagnostic.
#
# Revision ID: 59a25b856f18
# Revises:     35529ce17750  (property improvements head)
# ============================================================

"""add phase3 parity fields

Revision ID: 59a25b856f18
Revises: 35529ce17750
Create Date: 2026-09-20
"""

from alembic import op
import sqlalchemy as sa


revision = "59a25b856f18"
down_revision = "35529ce17750"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------
    # property_amenities
    # ---------------------------------------------------------
    with op.batch_alter_table("property_amenities") as batch_op:
        batch_op.add_column(
            sa.Column(
                "fee_amount",
                sa.Numeric(precision=14, scale=2),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "availability_status",
                sa.String(length=30),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("delete_reason", sa.Text(), nullable=True)
        )

    # ---------------------------------------------------------
    # property_appliances
    # ---------------------------------------------------------
    with op.batch_alter_table("property_appliances") as batch_op:
        batch_op.add_column(
            sa.Column(
                "condition",
                sa.String(length=30),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("delete_reason", sa.Text(), nullable=True)
        )

    # ---------------------------------------------------------
    # property_improvements
    # ---------------------------------------------------------
    with op.batch_alter_table("property_improvements") as batch_op:
        batch_op.add_column(
            sa.Column("warranty_expires", sa.Date(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("delete_reason", sa.Text(), nullable=True)
        )

    # ---------------------------------------------------------
    # gl_accounts.must_clear
    # ---------------------------------------------------------
    with op.batch_alter_table("gl_accounts") as batch_op:
        batch_op.add_column(
            sa.Column(
                "must_clear",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("gl_accounts") as batch_op:
        batch_op.drop_column("must_clear")

    with op.batch_alter_table("property_improvements") as batch_op:
        batch_op.drop_column("delete_reason")
        batch_op.drop_column("warranty_expires")

    with op.batch_alter_table("property_appliances") as batch_op:
        batch_op.drop_column("delete_reason")
        batch_op.drop_column("condition")

    with op.batch_alter_table("property_amenities") as batch_op:
        batch_op.drop_column("delete_reason")
        batch_op.drop_column("availability_status")
        batch_op.drop_column("fee_amount")