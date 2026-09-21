"""add_charges_table

Standalone tenant charges.

Charges are one-off amounts owed by a tenant (late fee, damage,
utility, misc). Distinct from rent_invoices (auto-generated for
active leases) and receipt_lines (payments against charges).

A charge has amount and amount_paid so we can compute outstanding
balance without scanning the ledger.

See PROJECT_MASTER.md Section 19 and JSON item
accounting.charges.enter_charge.

Revision ID: f49b93dcb1e2
Revises: 8e1243432666
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa


revision = "f49b93dcb1e2"
down_revision = "8e1243432666"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "charges",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "tenant_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "unit_id",
            sa.Integer(),
            sa.ForeignKey("units.id"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "property_id",
            sa.Integer(),
            sa.ForeignKey("properties.id"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "gl_account_id",
            sa.Integer(),
            sa.ForeignKey("gl_accounts.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("charge_date", sa.Date(), nullable=False, index=True),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("delete_reason", sa.String(length=500), nullable=True),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_index(
        "ix_charges_org_date",
        "charges",
        ["organization_id", "charge_date"],
    )
    op.create_index(
        "ix_charges_org_tenant",
        "charges",
        ["organization_id", "tenant_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_charges_org_tenant", table_name="charges")
    op.drop_index("ix_charges_org_date", table_name="charges")
    op.drop_table("charges")