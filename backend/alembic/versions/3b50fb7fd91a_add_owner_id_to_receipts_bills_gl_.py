# ============================================================
# 3b50fb7fd91a_add_owner_id_to_receipts_bills_gl_.py
# ------------------------------------------------------------
# Hand-written migration (Rule 9 / Rule 13: no autogenerate).
#
# Adds a nullable owner_id column to three tables:
#   - receipts    (which owner this money belongs to)
#   - bills       (which owner pays for this expense)
#   - gl_entries  (the tag that lets us group GL activity by owner)
#
# WHY: To match AppFolio's three-way reconciliation, the GL must
# be scoped by owner as well as property. AppFolio guarantees a
# property on every posting and derives/asks for owner from the
# property. Without owner_id on gl_entries, we can't compute the
# third leg of the trust reconciliation (sum of all sub-ledgers).
#
# NULLABLE: Old rows keep owner_id = NULL. New rows may or may
# not set it depending on the property's owner configuration.
# The service layer decides; nothing breaks.
#
# SQLite note: this migration uses op.batch_alter_table, which
# Alembic rewrites to a safe table-rebuild on SQLite. Same
# pattern used in migration 8a3f2c1e9b44.
#
# Revision ID: 3b50fb7fd91a
# Revises:     e266f7c76a7c  (Deposits head)
# ============================================================

"""add owner_id to receipts, bills, gl_entries

Revision ID: 3b50fb7fd91a
Revises: e266f7c76a7c
Create Date: 2026-09-20
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3b50fb7fd91a"
down_revision = "e266f7c76a7c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------
    # 1. receipts.owner_id
    # ---------------------------------------------------------
    with op.batch_alter_table("receipts") as batch_op:
        batch_op.add_column(
            sa.Column("owner_id", sa.Integer(), nullable=True)
        )
    # Note: batch_alter_table recreates the table. We add the
    # index in a separate statement below for clarity.
    op.create_index(
        "ix_receipts_owner_id", "receipts", ["owner_id"]
    )

    # ---------------------------------------------------------
    # 2. bills.owner_id
    # ---------------------------------------------------------
    with op.batch_alter_table("bills") as batch_op:
        batch_op.add_column(
            sa.Column("owner_id", sa.Integer(), nullable=True)
        )
    op.create_index("ix_bills_owner_id", "bills", ["owner_id"])

    # ---------------------------------------------------------
    # 3. gl_entries.owner_id
    # ---------------------------------------------------------
    with op.batch_alter_table("gl_entries") as batch_op:
        batch_op.add_column(
            sa.Column("owner_id", sa.Integer(), nullable=True)
        )
    op.create_index(
        "ix_gl_entries_owner_id", "gl_entries", ["owner_id"]
    )


def downgrade() -> None:
    # Remove indexes first, then columns, in reverse order.

    op.drop_index("ix_gl_entries_owner_id", table_name="gl_entries")
    with op.batch_alter_table("gl_entries") as batch_op:
        batch_op.drop_column("owner_id")

    op.drop_index("ix_bills_owner_id", table_name="bills")
    with op.batch_alter_table("bills") as batch_op:
        batch_op.drop_column("owner_id")

    op.drop_index("ix_receipts_owner_id", table_name="receipts")
    with op.batch_alter_table("receipts") as batch_op:
        batch_op.drop_column("owner_id")