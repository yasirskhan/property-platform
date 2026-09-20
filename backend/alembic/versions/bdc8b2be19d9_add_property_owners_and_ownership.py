# ============================================================
# bdc8b2be19d9_add_property_owners_and_ownership.py
# ------------------------------------------------------------
# Hand-written migration (Rule 9 / Rule 13: no autogenerate).
#
# AppFolio-parity ownership model:
#
#   1. properties.owner_id          — nullable FK to users.id
#      Fast path for single-owner properties (95%+ of cases).
#
#   2. properties.ownership_pct     — numeric(5,2) default 100.00
#      What share the primary owner holds.
#
#   3. property_owners              — join table for co-ownership
#      (property_id, user_id, ownership_pct, is_primary).
#      Enables split 1099 reporting and per-owner sub-ledgers.
#
# Backfill: every existing property gets owner_id = NULL and
# ownership_pct = 100.00. No data migration needed — managers
# will assign owners as they go.
#
# SQLite note: op.batch_alter_table rewrites to a safe table
# rebuild. Same pattern used in prior migrations.
#
# Revision ID: bdc8b2be19d9
# Revises:     3b50fb7fd91a  (owner_id on receipts/bills/gl_entries)
# ============================================================

"""add property owners and ownership

Revision ID: bdc8b2be19d9
Revises: 3b50fb7fd91a
Create Date: 2026-09-20
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "bdc8b2be19d9"
down_revision = "3b50fb7fd91a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------
    # 1. Add owner_id and ownership_pct to properties
    # ---------------------------------------------------------
    with op.batch_alter_table("properties") as batch_op:
        batch_op.add_column(
            sa.Column("owner_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "ownership_pct",
                sa.Numeric(precision=5, scale=2),
                nullable=True,
                server_default="100.00",
            )
        )
    op.create_index(
        "ix_properties_owner_id", "properties", ["owner_id"]
    )

    # ---------------------------------------------------------
    # 2. Create property_owners join table (co-ownership)
    # ---------------------------------------------------------
    op.create_table(
        "property_owners",
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
            sa.ForeignKey("properties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ownership_pct",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default="100.00",
        ),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
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
        "ix_property_owners_organization_id",
        "property_owners",
        ["organization_id"],
    )
    op.create_index(
        "ix_property_owners_property_id",
        "property_owners",
        ["property_id"],
    )
    op.create_index(
        "ix_property_owners_user_id",
        "property_owners",
        ["user_id"],
    )
    # A user can appear only once per property.
    op.create_index(
        "ux_property_owners_property_user",
        "property_owners",
        ["property_id", "user_id"],
        unique=True,
    )

    # ---------------------------------------------------------
    # 3. Backfill property_owners for existing properties that
    #    already have a primary owner. Right now nobody has an
    #    owner (owner_id is NULL everywhere), so this loop is a
    #    no-op for the current data set. It's here so that if we
    #    ever re-run on a DB that already has owner_id set, the
    #    join table stays consistent.
    # ---------------------------------------------------------
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, organization_id, owner_id, ownership_pct "
            "FROM properties WHERE owner_id IS NOT NULL"
        )
    ).fetchall()
    for prop_id, org_id, owner_id, pct in rows:
        # Skip if a matching row already exists
        existing = bind.execute(
            sa.text(
                "SELECT id FROM property_owners "
                "WHERE property_id = :p AND user_id = :u"
            ),
            {"p": prop_id, "u": owner_id},
        ).fetchone()
        if existing:
            continue
        bind.execute(
            sa.text(
                """
                INSERT INTO property_owners (
                    organization_id, property_id, user_id,
                    ownership_pct, is_primary, is_active,
                    created_at, updated_at
                ) VALUES (
                    :org, :prop, :user,
                    :pct, 1, 1,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "org": org_id,
                "prop": prop_id,
                "user": owner_id,
                "pct": pct if pct is not None else 100,
            },
        )


def downgrade() -> None:
    op.drop_index(
        "ux_property_owners_property_user", table_name="property_owners"
    )
    op.drop_index(
        "ix_property_owners_user_id", table_name="property_owners"
    )
    op.drop_index(
        "ix_property_owners_property_id", table_name="property_owners"
    )
    op.drop_index(
        "ix_property_owners_organization_id", table_name="property_owners"
    )
    op.drop_table("property_owners")

    op.drop_index("ix_properties_owner_id", table_name="properties")
    with op.batch_alter_table("properties") as batch_op:
        batch_op.drop_column("ownership_pct")
        batch_op.drop_column("owner_id")