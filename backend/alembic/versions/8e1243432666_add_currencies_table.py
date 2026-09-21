"""add_currencies_table

Per-org list of currencies the customer can choose from.

Each org starts with 9 system currencies (USD, EUR, GBP, INR, AUD,
CAD, NZD, SGD, AED). Admin/Owner can add custom currencies on top.

No conversion. Each org operates in ONE currency at a time
(organizations.currency). This table just defines what's selectable.

See PROJECT_MASTER.md Section 68.

Revision ID: 8e1243432666
Revises: 15d92d8a1eea
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa


revision = "8e1243432666"
down_revision = "15d92d8a1eea"
branch_labels = None
depends_on = None


# Default currencies seeded for every org. Keep in sync with
# CURRENCY_LOCALE in frontend/src/lib/money.ts.
SEED = [
    ("USD", "US Dollar",              "$",   "en-US", 2),
    ("EUR", "Euro",                   "\u20ac", "de-DE", 2),
    ("GBP", "British Pound",          "\u00a3", "en-GB", 2),
    ("INR", "Indian Rupee",           "\u20b9", "en-IN", 2),
    ("AUD", "Australian Dollar",      "A$",  "en-AU", 2),
    ("CAD", "Canadian Dollar",        "C$",  "en-CA", 2),
    ("NZD", "New Zealand Dollar",     "NZ$", "en-NZ", 2),
    ("SGD", "Singapore Dollar",       "S$",  "en-SG", 2),
    ("AED", "UAE Dirham",             "\u062f.\u0625", "en-AE", 2),
]


def upgrade() -> None:
    op.create_table(
        "currencies",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("code", sa.String(length=3), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("symbol", sa.String(length=10), nullable=False),
        sa.Column("locale", sa.String(length=20), nullable=False),
        sa.Column("decimal_places", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("organization_id", "code", name="uq_currency_org_code"),
    )

    # Seed defaults for every existing org
    conn = op.get_bind()
    org_ids = [row[0] for row in conn.execute(
        sa.text("SELECT id FROM organizations")
    ).fetchall()]

    insert_sql = sa.text(
        """
        INSERT INTO currencies
            (organization_id, code, name, symbol, locale,
             decimal_places, is_system, is_active, created_at, updated_at)
        SELECT :org_id, :code, :name, :symbol, :locale, :dp, 1, 1,
               CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        WHERE NOT EXISTS (
            SELECT 1 FROM currencies
            WHERE organization_id = :org_id AND code = :code
        )
        """
    )

    for org_id in org_ids:
        for code, name, symbol, locale, dp in SEED:
            conn.execute(insert_sql, {
                "org_id": org_id,
                "code": code,
                "name": name,
                "symbol": symbol,
                "locale": locale,
                "dp": dp,
            })


def downgrade() -> None:
    op.drop_table("currencies")