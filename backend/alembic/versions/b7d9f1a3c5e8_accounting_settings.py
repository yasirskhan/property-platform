"""add accounting settings

Revision ID: b7d9f1a3c5e8
Revises: a6c8e0f2b4d7
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa


revision = "b7d9f1a3c5e8"
down_revision = "a6c8e0f2b4d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounting_settings",
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "gpr_rent_gl_account_id",
            sa.Integer(),
            sa.ForeignKey("gl_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "gpr_market_gl_account_id",
            sa.Integer(),
            sa.ForeignKey("gl_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "gpr_loss_gain_gl_account_id",
            sa.Integer(),
            sa.ForeignKey("gl_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "receipt_cash_gl_account_id",
            sa.Integer(),
            sa.ForeignKey("gl_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "report_export_format",
            sa.String(length=10),
            nullable=False,
            server_default="CSV",
        ),
        sa.Column(
            "fiscal_year_start_month",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    conn = op.get_bind()
    insert_sql = sa.text(
        """
        INSERT INTO menu_permissions
            (organization_id, role, menu_key, visible, created_at, updated_at)
        SELECT :org_id, :role, 'SETTINGS.ACCOUNTING', :visible,
               CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        WHERE NOT EXISTS (
            SELECT 1 FROM menu_permissions
            WHERE organization_id = :org_id
              AND role = :role
              AND menu_key = 'SETTINGS.ACCOUNTING'
        )
        """
    )
    org_ids = [
        row[0]
        for row in conn.execute(sa.text("SELECT id FROM organizations")).fetchall()
    ]
    roles = [
        "ADMIN", "OWNER", "MANAGER", "CREW",
        "TENANT", "VENDOR", "VENDOR_CREW", "APPLICANT",
    ]
    for org_id in org_ids:
        for role in roles:
            conn.execute(
                insert_sql,
                {
                    "org_id": org_id,
                    "role": role,
                    "visible": 1 if role in {"ADMIN", "OWNER"} else 0,
                },
            )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM menu_permissions WHERE menu_key = 'SETTINGS.ACCOUNTING'"
        )
    )
    op.drop_table("accounting_settings")
