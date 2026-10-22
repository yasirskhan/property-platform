"""Add independently approved maintenance purchase requests and immutable stock movements."""
from alembic import op
import sqlalchemy as sa

revision = "c5d91a7e2f60"
down_revision = "e6b4d2a7c910"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "maintenance_material_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("work_order_id", sa.Integer(), nullable=False),
        sa.Column("vendor_id", sa.Integer(), nullable=False),
        sa.Column("request_key", sa.String(80), nullable=False),
        sa.Column("sku", sa.String(60), nullable=False),
        sa.Column("item_name", sa.String(255), nullable=False),
        sa.Column("requested_qty", sa.Integer(), nullable=False),
        sa.Column("unit_cost_cents", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("requested_by_id", sa.Integer(), nullable=False),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["vendor_id"], ["vendors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("organization_id", "request_key", name="uq_material_order_org_request"),
        sa.CheckConstraint("requested_qty > 0 AND requested_qty <= 10000", name="ck_material_order_quantity"),
        sa.CheckConstraint("unit_cost_cents >= 0 AND unit_cost_cents <= 100000000",
                           name="ck_material_order_unit_cost"),
        sa.CheckConstraint("status IN ('REQUESTED','APPROVED','DENIED')",
                           name="ck_material_order_status"),
    )
    for key in ("organization_id", "property_id", "work_order_id"):
        op.create_index("ix_maintenance_material_orders_" + key, "maintenance_material_orders", [key])
    op.create_table(
        "maintenance_material_movements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("reference", sa.String(100), nullable=False),
        sa.Column("delta_qty", sa.Integer(), nullable=False),
        sa.Column("received_by_id", sa.Integer(), nullable=False),
        sa.Column("reverses_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_id"], ["maintenance_material_orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["received_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reverses_id"], ["maintenance_material_movements.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("order_id", "reference", name="uq_material_movement_reference"),
        sa.UniqueConstraint("reverses_id", name="uq_material_movement_reversal"),
        sa.CheckConstraint("delta_qty != 0 AND delta_qty BETWEEN -10000 AND 10000",
                           name="ck_material_movement_delta"),
    )
    for key in ("organization_id", "order_id"):
        op.create_index("ix_maintenance_material_movements_" + key,
                        "maintenance_material_movements", [key])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION prevent_material_movement_mutation() RETURNS trigger AS $$
            BEGIN RAISE EXCEPTION 'maintenance_material_movements is append-only'; END;
            $$ LANGUAGE plpgsql""")
        op.execute("""CREATE TRIGGER material_movement_immutable BEFORE UPDATE OR DELETE
            ON maintenance_material_movements FOR EACH ROW
            EXECUTE FUNCTION prevent_material_movement_mutation()""")
    elif op.get_bind().dialect.name == "sqlite":
        op.execute("""CREATE TRIGGER material_movement_no_update
            BEFORE UPDATE ON maintenance_material_movements
            BEGIN SELECT RAISE(ABORT,'maintenance_material_movements is append-only'); END""")
        op.execute("""CREATE TRIGGER material_movement_no_delete
            BEFORE DELETE ON maintenance_material_movements
            BEGIN SELECT RAISE(ABORT,'maintenance_material_movements is append-only'); END""")


def downgrade():
    bind = op.get_bind()
    for table in ("maintenance_material_movements", "maintenance_material_orders"):
        if bind.execute(sa.text("SELECT 1 FROM " + table + " LIMIT 1")).first():
            raise RuntimeError("Cannot discard approved purchasing/physical receipt evidence")
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS material_movement_immutable ON maintenance_material_movements")
        op.execute("DROP FUNCTION IF EXISTS prevent_material_movement_mutation()")
    elif bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS material_movement_no_update")
        op.execute("DROP TRIGGER IF EXISTS material_movement_no_delete")
    for key in ("organization_id", "order_id"):
        op.drop_index("ix_maintenance_material_movements_" + key, table_name="maintenance_material_movements")
    op.drop_table("maintenance_material_movements")
    for key in ("organization_id", "property_id", "work_order_id"):
        op.drop_index("ix_maintenance_material_orders_" + key, table_name="maintenance_material_orders")
    op.drop_table("maintenance_material_orders")
