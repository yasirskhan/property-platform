"""add per-bank deposit sequence and release deposit edit/print
Revision ID: c7d9e1f3a5b2
Revises: f4a6c8d0e2b1
"""
from alembic import op
import sqlalchemy as sa

revision = "c7d9e1f3a5b2"
down_revision = "f4a6c8d0e2b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deposits", sa.Column("bank_sequence", sa.Integer(), nullable=True))
    op.create_index("ix_deposits_bank_sequence", "deposits", ["bank_sequence"])
    bind = op.get_bind()
    bind.execute(sa.text("""
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY organization_id, bank_gl_account_id
                       ORDER BY deposit_date, id
                   ) AS seq
            FROM deposits
        )
        UPDATE deposits
        SET bank_sequence = (
            SELECT ranked.seq FROM ranked WHERE ranked.id = deposits.id
        )
    """))
    op.create_index(
        "ux_deposits_org_bank_sequence",
        "deposits",
        ["organization_id", "bank_gl_account_id", "bank_sequence"],
        unique=True,
    )
    for key, description in [
        ("release.accounting.deposits.print", "Print Bank Deposit"),
        ("release.accounting.deposits.edit", "Edit Bank Deposit"),
    ]:
        bind.execute(
            sa.text(
                "INSERT INTO release_gates "
                "(key, stage, description, created_at, updated_at) "
                "SELECT :key, 'ALL_ORGS', :description, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
                "WHERE NOT EXISTS (SELECT 1 FROM release_gates WHERE key=:key)"
            ),
            {"key": key, "description": description},
        )
        bind.execute(
            sa.text(
                "UPDATE release_gates SET stage='ALL_ORGS', "
                "updated_at=CURRENT_TIMESTAMP WHERE key=:key"
            ),
            {"key": key},
        )


def downgrade() -> None:
    bind = op.get_bind()
    for key in [
        "release.accounting.deposits.print",
        "release.accounting.deposits.edit",
    ]:
        bind.execute(
            sa.text(
                "DELETE FROM release_gate_organizations "
                "WHERE release_gate_id IN "
                "(SELECT id FROM release_gates WHERE key=:key)"
            ),
            {"key": key},
        )
        bind.execute(
            sa.text("DELETE FROM release_gates WHERE key=:key"),
            {"key": key},
        )
    op.drop_index("ux_deposits_org_bank_sequence", table_name="deposits")
    op.drop_index("ix_deposits_bank_sequence", table_name="deposits")
    op.drop_column("deposits", "bank_sequence")
