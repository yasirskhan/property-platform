"""add menu permissions system

Revision ID: 8a3f2c1e9b44
Revises: 1d77e94a0fb5
Create Date: 2026-09-19

Creates:
  - menu_permissions       (per-org, per-role, per-menu-key visibility)
  - user_permissions       (per-user overrides of role defaults)
  - extends sidebar_preferences with user_id (per-user, not per-org)
  - widens users.role to VARCHAR(32) (fits vendor_crew, applicant)
  - seeds default menu_permissions rows for existing orgs
"""
from alembic import op
import sqlalchemy as sa


# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision = "8a3f2c1e9b44"
down_revision = "1d77e94a0fb5"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Canonical menu keys and per-role defaults
# ---------------------------------------------------------------------------
# Every key here must match the frontend menu key taxonomy exactly.
# Stored uppercase to match existing role values in the users table.

MENU_KEYS = [
    # top level
    "DASHBOARD", "CALENDAR", "LEASING", "PROPERTIES", "PEOPLE",
    "ACCOUNTING", "MAINTENANCE", "REPORTING", "COMMUNICATION", "WHATS_NEW",
    # leasing
    "LEASING.LISTINGS", "LEASING.APPLICATIONS", "LEASING.CRM", "LEASING.TEMPLATES",
    # properties
    "PROPERTIES.ALL", "PROPERTIES.ADD", "PROPERTIES.UNITS", "PROPERTIES.GROUPS",
    # people
    "PEOPLE.TEAM", "PEOPLE.TENANTS", "PEOPLE.OWNERS", "PEOPLE.VENDORS", "PEOPLE.CONTACTS",
    # accounting
    "ACCOUNTING.RECEIVABLES", "ACCOUNTING.PAYABLES", "ACCOUNTING.BANK_ACCOUNTS",
    "ACCOUNTING.JOURNAL_ENTRIES", "ACCOUNTING.BANK_TRANSFERS", "ACCOUNTING.GL_ACCOUNTS",
    "ACCOUNTING.DIAGNOSTICS", "ACCOUNTING.ONLINE_PAYMENTS",
    # maintenance
    "MAINTENANCE.WORK_ORDERS", "MAINTENANCE.RECURRING", "MAINTENANCE.INSPECTIONS",
    "MAINTENANCE.UNIT_TURNS", "MAINTENANCE.PROJECTS", "MAINTENANCE.PURCHASE_ORDERS",
    "MAINTENANCE.INVENTORY", "MAINTENANCE.FIXED_ASSETS", "MAINTENANCE.SMART",
    # reporting
    "REPORTING.ALL", "REPORTING.BUILDER",
    # communication
    "COMMUNICATION.INBOX", "COMMUNICATION.MESSAGES",
    "COMMUNICATION.TEMPLATES", "COMMUNICATION.SURVEYS",
]

ROLES = ["ADMIN", "OWNER", "MANAGER", "CREW", "TENANT", "VENDOR", "VENDOR_CREW", "APPLICANT"]

# Default visibility matrix. Only listed keys are True; anything not listed
# defaults to False for that role.
DEFAULT_MATRIX = {
    "ADMIN": set(MENU_KEYS),  # admin sees everything
    "OWNER": set(MENU_KEYS) - {"PEOPLE.TEAM", "ACCOUNTING.ONLINE_PAYMENTS"},
    "MANAGER": {
        "DASHBOARD", "CALENDAR",
        "LEASING", "LEASING.LISTINGS", "LEASING.APPLICATIONS", "LEASING.CRM", "LEASING.TEMPLATES",
        "PROPERTIES", "PROPERTIES.ALL", "PROPERTIES.ADD", "PROPERTIES.UNITS", "PROPERTIES.GROUPS",
        "PEOPLE", "PEOPLE.TENANTS", "PEOPLE.OWNERS", "PEOPLE.VENDORS", "PEOPLE.CONTACTS",
        "ACCOUNTING", "ACCOUNTING.RECEIVABLES", "ACCOUNTING.PAYABLES",
        "ACCOUNTING.BANK_ACCOUNTS", "ACCOUNTING.JOURNAL_ENTRIES",
        "ACCOUNTING.BANK_TRANSFERS", "ACCOUNTING.GL_ACCOUNTS",
        "ACCOUNTING.DIAGNOSTICS",
        "MAINTENANCE", "MAINTENANCE.WORK_ORDERS", "MAINTENANCE.RECURRING",
        "MAINTENANCE.INSPECTIONS", "MAINTENANCE.UNIT_TURNS",
        "MAINTENANCE.PROJECTS", "MAINTENANCE.PURCHASE_ORDERS",
        "MAINTENANCE.INVENTORY", "MAINTENANCE.FIXED_ASSETS", "MAINTENANCE.SMART",
        "REPORTING", "REPORTING.ALL", "REPORTING.BUILDER",
        "COMMUNICATION", "COMMUNICATION.INBOX", "COMMUNICATION.MESSAGES",
        "COMMUNICATION.TEMPLATES", "COMMUNICATION.SURVEYS",
        "WHATS_NEW",
    },
    "CREW": {
        "DASHBOARD", "CALENDAR",
        "MAINTENANCE", "MAINTENANCE.WORK_ORDERS", "MAINTENANCE.RECURRING",
        "MAINTENANCE.INSPECTIONS", "MAINTENANCE.UNIT_TURNS",
        "COMMUNICATION", "COMMUNICATION.INBOX", "COMMUNICATION.MESSAGES",
        "WHATS_NEW",
    },
    "TENANT": {
        "DASHBOARD",
        "COMMUNICATION", "COMMUNICATION.INBOX", "COMMUNICATION.MESSAGES",
        "WHATS_NEW",
    },
    "VENDOR": {
        "DASHBOARD",
        "MAINTENANCE", "MAINTENANCE.WORK_ORDERS",
        "COMMUNICATION", "COMMUNICATION.INBOX", "COMMUNICATION.MESSAGES",
        "WHATS_NEW",
    },
    "VENDOR_CREW": {
        "DASHBOARD",
        "MAINTENANCE", "MAINTENANCE.WORK_ORDERS",
        "COMMUNICATION", "COMMUNICATION.INBOX", "COMMUNICATION.MESSAGES",
        "WHATS_NEW",
    },
    "APPLICANT": {
        "DASHBOARD",
        "WHATS_NEW",
    },
}


def upgrade() -> None:
    bind = op.get_bind()

    # -----------------------------------------------------------------
    # 1. Widen users.role so vendor_crew / applicant fit
    # -----------------------------------------------------------------
    # SQLite doesn't enforce VARCHAR lengths, but PostgreSQL will.
    # Use batch_alter_table for SQLite compatibility.
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=sa.String(length=7),
            type_=sa.String(length=32),
            existing_nullable=False,
        )

    # -----------------------------------------------------------------
    # 2. Create menu_permissions
    # -----------------------------------------------------------------
    op.create_table(
        "menu_permissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("menu_key", sa.String(length=64), nullable=False),
        sa.Column("visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "organization_id", "role", "menu_key",
            name="uq_menu_permissions_org_role_key",
        ),
    )
    op.create_index(
        "ix_menu_permissions_org_role",
        "menu_permissions",
        ["organization_id", "role"],
    )

    # -----------------------------------------------------------------
    # 3. Create user_permissions
    # -----------------------------------------------------------------
    op.create_table(
        "user_permissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("menu_key", sa.String(length=64), nullable=False),
        sa.Column("visible", sa.Boolean(), nullable=False),
        sa.Column(
            "set_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "menu_key", name="uq_user_permissions_user_key"),
    )
    op.create_index("ix_user_permissions_user", "user_permissions", ["user_id"])

    # -----------------------------------------------------------------
    # 4. Extend sidebar_preferences with user_id (per-user, was per-org)
    # -----------------------------------------------------------------
    with op.batch_alter_table("sidebar_preferences") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))

    # Give the existing per-org row to a sensible user in that org.
    # Priority: ADMIN > OWNER > MANAGER > any user in the org.
    rows = bind.execute(
        sa.text("SELECT id, organization_id FROM sidebar_preferences")
    ).fetchall()
    for row_id, org_id in rows:
        if org_id is None:
            continue
        pick = bind.execute(
            sa.text(
                "SELECT id FROM users WHERE organization_id = :org "
                "ORDER BY "
                "CASE UPPER(role) "
                "  WHEN 'ADMIN' THEN 1 "
                "  WHEN 'OWNER' THEN 2 "
                "  WHEN 'MANAGER' THEN 3 "
                "  ELSE 4 "
                "END, id "
                "LIMIT 1"
            ),
            {"org": org_id},
        ).fetchone()
        if pick is not None:
            bind.execute(
                sa.text("UPDATE sidebar_preferences SET user_id = :uid WHERE id = :rid"),
                {"uid": pick[0], "rid": row_id},
            )

    # Unique index on user_id where not null (partial index in SQLite)
    op.create_index(
        "uq_sidebar_preferences_user_id",
        "sidebar_preferences",
        ["user_id"],
        unique=True,
        sqlite_where=sa.text("user_id IS NOT NULL"),
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )

    # -----------------------------------------------------------------
    # 5. Seed menu_permissions for every existing organization
    # -----------------------------------------------------------------
    org_ids = [
        r[0]
        for r in bind.execute(sa.text("SELECT id FROM organizations")).fetchall()
    ]

    if org_ids:
        menu_table = sa.table(
            "menu_permissions",
            sa.column("organization_id", sa.Integer()),
            sa.column("role", sa.String()),
            sa.column("menu_key", sa.String()),
            sa.column("visible", sa.Boolean()),
        )
        payload = []
        for org_id in org_ids:
            for role in ROLES:
                allowed = DEFAULT_MATRIX.get(role, set())
                for key in MENU_KEYS:
                    payload.append(
                        {
                            "organization_id": org_id,
                            "role": role,
                            "menu_key": key,
                            "visible": key in allowed,
                        }
                    )
        if payload:
            op.bulk_insert(menu_table, payload)


def downgrade() -> None:
    # Remove seed data and tables in reverse order
    op.drop_index("uq_sidebar_preferences_user_id", table_name="sidebar_preferences")
    with op.batch_alter_table("sidebar_preferences") as batch_op:
        batch_op.drop_column("user_id")

    op.drop_index("ix_user_permissions_user", table_name="user_permissions")
    op.drop_table("user_permissions")

    op.drop_index("ix_menu_permissions_org_role", table_name="menu_permissions")
    op.drop_table("menu_permissions")

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=sa.String(length=32),
            type_=sa.String(length=7),
            existing_nullable=False,
        )