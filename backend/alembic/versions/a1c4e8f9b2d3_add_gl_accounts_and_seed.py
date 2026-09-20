"""add gl_accounts table and seed 57 standard accounts

Revision ID: a1c4e8f9b2d3
Revises: 9f4b7c1a2d55
Create Date: 2026-09-20

Creates the gl_accounts table and seeds the 57 standard chart
of accounts for every existing organization.

Idempotent: re-running won't duplicate seeds because we check
for existing gl_number per org before inserting.
"""
from alembic import op
import sqlalchemy as sa


# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision = "a1c4e8f9b2d3"
down_revision = "9f4b7c1a2d55"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# The 57 standard accounts
# (gl_number, name, account_type, subject_to_mgmt_fees, include_on_cash_flow)
# ---------------------------------------------------------------------------
STANDARD_ACCOUNTS = [
    # ---------- 1xxx Assets ----------
    ("1150", "Rental Trust",                  "ASSET",     False, True),
    ("1160", "Security Deposit Cash",         "ASSET",     False, True),
    ("1300", "Accounts Receivable",           "ASSET",     False, True),
    ("1610", "Land",                          "ASSET",     False, False),
    ("1710", "Buildings",                     "ASSET",     False, False),
    ("1720", "Accumulated Depreciation",      "ASSET",     False, False),
    ("1810", "Other Assets",                  "ASSET",     False, False),
    ("1820", "Other Depreciation",            "ASSET",     False, False),

    # ---------- 2xxx Liabilities ----------
    ("2101", "Security Deposits",             "LIABILITY", False, True),
    ("2300", "Prepayment",                    "LIABILITY", False, True),
    ("2401", "Owner Funds",                   "LIABILITY", False, True),
    ("2600", "Mortgage",                      "LIABILITY", False, False),

    # ---------- 4xxx Income ----------
    ("4100", "Rent",                          "INCOME",    True,  True),
    ("4105", "Section 8",                     "INCOME",    True,  True),
    ("4110", "Month-to-Month",                "INCOME",    True,  True),
    ("4115", "Gross Potential Rent",          "INCOME",    False, True),
    ("4120", "Loss/Gain",                     "INCOME",    False, True),
    ("4210", "Concessions",                   "INCOME",    False, True),
    ("4405", "NSF",                           "INCOME",    True,  True),
    ("4415", "Pet Fee (deprecated)",          "INCOME",    True,  True),
    ("4416", "Pet Fee",                       "INCOME",    True,  True),
    ("4420", "Application Fee",               "INCOME",    True,  True),
    ("4425", "Insurance",                     "INCOME",    True,  True),
    ("4430", "Late Fee",                      "INCOME",    True,  True),
    ("4435", "Utility",                       "INCOME",    True,  True),
    ("4440", "Violation",                     "INCOME",    True,  True),
    ("4445", "Default",                       "INCOME",    True,  True),
    ("4450", "MRA",                           "INCOME",    True,  True),
    ("4455", "Lease Initiation",              "INCOME",    True,  True),
    ("4457", "Renewal Fee",                   "INCOME",    True,  True),
    ("4460", "Eviction",                      "INCOME",    True,  True),
    ("4465", "Notice",                        "INCOME",    True,  True),
    ("4470", "Early Termination",             "INCOME",    True,  True),
    ("4478", "RBP",                           "INCOME",    True,  True),
    ("4480", "PM Charge",                     "INCOME",    True,  True),
    ("4483", "Utility Reduction",             "INCOME",    True,  True),
    ("4490", "Option Consideration",          "INCOME",    True,  True),
    ("4805", "PM Charge",                     "INCOME",    True,  True),

    # ---------- 6xxx Expenses ----------
    ("6001", "Management Fees",               "EXPENSE",   False, True),
    ("6005", "Leasing Fee",                   "EXPENSE",   False, True),
    ("6015", "Vendor Discounts",              "EXPENSE",   False, True),
    ("6025", "Unknown",                       "EXPENSE",   False, True),
    ("6074", "Landscaping",                   "EXPENSE",   False, True),
    ("6076", "Cleaning",                      "EXPENSE",   False, True),
    ("6091", "Insurance",                     "EXPENSE",   False, True),
    ("6121", "Mortgage",                      "EXPENSE",   False, True),
    ("6144", "HVAC",                          "EXPENSE",   False, True),
    ("6171", "Electric",                      "EXPENSE",   False, True),
    ("6173", "Water",                         "EXPENSE",   False, True),
    ("6174", "Sewer",                         "EXPENSE",   False, True),
    ("6175", "Garbage",                       "EXPENSE",   False, True),
    ("6176", "Cable",                         "EXPENSE",   False, True),
    ("6192", "Bank Fees",                     "EXPENSE",   False, True),
    ("6215", "Water (RUBs)",                  "EXPENSE",   False, True),
    ("6852", "Plumbing",                      "EXPENSE",   False, True),
    ("6855", "HVAC",                          "EXPENSE",   False, True),
    ("6858", "Rekey",                         "EXPENSE",   False, True),
    ("6865", "Electrical",                    "EXPENSE",   False, True),

    # ---------- 8xxx Admin Expense ----------
    ("8010", "Pest",                          "EXPENSE",   False, True),
    ("8050", "Computer",                      "EXPENSE",   False, True),
]


def upgrade() -> None:
    bind = op.get_bind()

    # -----------------------------------------------------------------
    # 1. Create the gl_accounts table
    # -----------------------------------------------------------------
    op.create_table(
        "gl_accounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("gl_number", sa.String(length=20), nullable=False, index=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("account_type", sa.String(length=20), nullable=False, index=True),
        sa.Column(
            "sub_account_of",
            sa.Integer(),
            sa.ForeignKey("gl_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("offset_account", sa.String(length=20), nullable=True),
        sa.Column(
            "subject_to_mgmt_fees",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "include_on_cash_flow",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
            index=True,
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column(
            "deleted_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("delete_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Composite index for the common lookup: "all active accounts in this org"
    op.create_index(
        "ix_gl_accounts_org_number",
        "gl_accounts",
        ["organization_id", "gl_number"],
    )

    # -----------------------------------------------------------------
    # 2. Seed the 57 standard accounts for every existing org
    # -----------------------------------------------------------------
    org_ids = [
        r[0]
        for r in bind.execute(sa.text("SELECT id FROM organizations")).fetchall()
    ]

    if not org_ids:
        return

    # Fetch existing (org_id, gl_number) pairs so we don't duplicate.
    # Table is brand new so this will be empty, but keep it defensive.
    existing = set()
    for row in bind.execute(
        sa.text("SELECT organization_id, gl_number FROM gl_accounts")
    ).fetchall():
        existing.add((row[0], row[1]))

    gl_table = sa.table(
        "gl_accounts",
        sa.column("organization_id", sa.Integer()),
        sa.column("gl_number", sa.String()),
        sa.column("name", sa.String()),
        sa.column("account_type", sa.String()),
        sa.column("subject_to_mgmt_fees", sa.Boolean()),
        sa.column("include_on_cash_flow", sa.Boolean()),
        sa.column("is_active", sa.Boolean()),
    )

    payload = []
    for org_id in org_ids:
        for (number, name, acc_type, mgmt, cashflow) in STANDARD_ACCOUNTS:
            if (org_id, number) in existing:
                continue
            payload.append(
                {
                    "organization_id": org_id,
                    "gl_number": number,
                    "name": name,
                    "account_type": acc_type,
                    "subject_to_mgmt_fees": mgmt,
                    "include_on_cash_flow": cashflow,
                    "is_active": True,
                }
            )

    if payload:
        op.bulk_insert(gl_table, payload)


def downgrade() -> None:
    op.drop_index("ix_gl_accounts_org_number", table_name="gl_accounts")
    op.drop_table("gl_accounts")