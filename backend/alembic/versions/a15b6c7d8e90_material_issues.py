"""P5-PROC-06: append-only physical stock issues with independent reversal.

No GL posting, vendor communication, billing, tenant liability or automatic
consumption. Consumed units are linked to real same-property maintenance jobs.
"""
from alembic import op
import sqlalchemy as sa

revision = "a15b6c7d8e90"
down_revision = "c5d91a7e2f60"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "maintenance_material_issues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("material_order_id", sa.Integer(), nullable=False),
        sa.Column("target_work_order_id", sa.Integer(), nullable=False),
        sa.Column("reference", sa.String(100), nullable=False),
        sa.Column("delta_qty", sa.Integer(), nullable=False),
        sa.Column("issued_by_id", sa.Integer(), nullable=False),
        sa.Column("reverses_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["material_order_id"], ["maintenance_material_orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["target_work_order_id"], ["work_orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["issued_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reverses_id"], ["maintenance_material_issues.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("material_order_id", "reference", name="uq_material_issue_reference"),
        sa.UniqueConstraint("reverses_id", name="uq_material_issue_reversal"),
        sa.CheckConstraint("delta_qty != 0 AND delta_qty BETWEEN -10000 AND 10000",
                           name="ck_material_issue_quantity"),
    )
    for name in ("organization_id", "material_order_id"):
        op.create_index("ix_maintenance_material_issues_" + name,
                        "maintenance_material_issues", [name])
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION prevent_material_issue_mutation() RETURNS trigger AS $$
            BEGIN RAISE EXCEPTION 'maintenance_material_issues is append-only'; END;
            $$ LANGUAGE plpgsql""")
        op.execute("""CREATE TRIGGER material_issue_immutable BEFORE UPDATE OR DELETE
            ON maintenance_material_issues FOR EACH ROW
            EXECUTE FUNCTION prevent_material_issue_mutation()""")
    elif bind.dialect.name == "sqlite":
        op.execute("""CREATE TRIGGER material_issue_no_update
            BEFORE UPDATE ON maintenance_material_issues
            BEGIN SELECT RAISE(ABORT,'maintenance_material_issues is append-only'); END""")
        op.execute("""CREATE TRIGGER material_issue_no_delete
            BEFORE DELETE ON maintenance_material_issues
            BEGIN SELECT RAISE(ABORT,'maintenance_material_issues is append-only'); END""")


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM maintenance_material_issues LIMIT 1")).first():
        raise RuntimeError("Cannot discard immutable material issue/consumption evidence")
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS material_issue_immutable ON maintenance_material_issues")
        op.execute("DROP FUNCTION IF EXISTS prevent_material_issue_mutation()")
    elif bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS material_issue_no_update")
        op.execute("DROP TRIGGER IF EXISTS material_issue_no_delete")
    for name in ("organization_id", "material_order_id"):
        op.drop_index("ix_maintenance_material_issues_" + name, table_name="maintenance_material_issues")
    op.drop_table("maintenance_material_issues")
