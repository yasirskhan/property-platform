"""P5-PROC-06 atomic internal multiple-line requisition, no external submission.

Existing single-line requests and their independent review remain unchanged.
"""
from alembic import op
import sqlalchemy as sa

revision = "e4a19d7f6c31"
down_revision = "d93f5c1a7b20"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("maintenance_material_batches",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("property_id",sa.Integer(),sa.ForeignKey("properties.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("work_order_id",sa.Integer(),sa.ForeignKey("work_orders.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("vendor_id",sa.Integer(),sa.ForeignKey("vendors.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("batch_key",sa.String(64),nullable=False),
        sa.Column("reason",sa.Text(),nullable=False),
        sa.Column("line_count",sa.Integer(),nullable=False),
        sa.Column("estimated_total_cents",sa.BigInteger(),nullable=False),
        sa.Column("requested_by_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("requested_at",sa.DateTime(),nullable=False),
        sa.Column("status",sa.String(16),nullable=False),
        sa.Column("reviewed_by_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="RESTRICT"),nullable=True),
        sa.Column("reviewed_at",sa.DateTime(),nullable=True),
        sa.Column("review_reason",sa.Text(),nullable=True),
        sa.UniqueConstraint("organization_id","batch_key",name="uq_material_batch_org_key"),
        sa.CheckConstraint("line_count BETWEEN 2 AND 20",name="ck_material_batch_line_count"),
        sa.CheckConstraint("estimated_total_cents >= 0 AND estimated_total_cents <= 20000000000000",name="ck_material_batch_total"),
        sa.CheckConstraint("status IN ('REQUESTED','APPROVED','DENIED')",name="ck_material_batch_status"),
    )
    op.create_index("ix_maintenance_material_batches_organization_id","maintenance_material_batches",["organization_id"])
    op.create_table("maintenance_material_batch_lines",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("batch_id",sa.Integer(),sa.ForeignKey("maintenance_material_batches.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("order_id",sa.Integer(),sa.ForeignKey("maintenance_material_orders.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("line_number",sa.Integer(),nullable=False),
        sa.UniqueConstraint("batch_id","line_number",name="uq_material_batch_line_number"),
        sa.UniqueConstraint("order_id",name="uq_material_batch_source_order"),
        sa.CheckConstraint("line_number BETWEEN 1 AND 20",name="ck_material_batch_line_number"),
    )
    op.create_index("ix_maintenance_material_batch_lines_batch_id","maintenance_material_batch_lines",["batch_id"])
    dialect=op.get_bind().dialect.name
    if dialect=="postgresql":
        op.execute("""CREATE FUNCTION prevent_material_batch_line_mutation()
            RETURNS trigger AS $batch_guard$
            BEGIN RAISE EXCEPTION 'maintenance_material_batch_lines is append-only'; END;
            $batch_guard$ LANGUAGE plpgsql""")
        op.execute("""CREATE TRIGGER material_batch_line_immutable
            BEFORE UPDATE OR DELETE ON maintenance_material_batch_lines
            FOR EACH ROW EXECUTE FUNCTION prevent_material_batch_line_mutation()""")
    elif dialect=="sqlite":
        for action in ("update","delete"):
            op.execute(f"""CREATE TRIGGER material_batch_line_no_{action}
                BEFORE {action.upper()} ON maintenance_material_batch_lines
                BEGIN SELECT RAISE(ABORT,'maintenance_material_batch_lines is append-only'); END""")


def downgrade():
    conn=op.get_bind()
    for name in ("maintenance_material_batch_lines","maintenance_material_batches"):
        if conn.execute(sa.text("SELECT 1 FROM "+name+" LIMIT 1")).first():
            raise RuntimeError("Cannot erase approved internal material requisition evidence")
    if conn.dialect.name=="postgresql":
        op.execute("DROP TRIGGER IF EXISTS material_batch_line_immutable ON maintenance_material_batch_lines")
        op.execute("DROP FUNCTION IF EXISTS prevent_material_batch_line_mutation()")
    elif conn.dialect.name=="sqlite":
        for action in ("update","delete"):
            op.execute("DROP TRIGGER IF EXISTS material_batch_line_no_"+action)
    op.drop_index("ix_maintenance_material_batch_lines_batch_id",table_name="maintenance_material_batch_lines")
    op.drop_table("maintenance_material_batch_lines")
    op.drop_index("ix_maintenance_material_batches_organization_id",table_name="maintenance_material_batches")
    op.drop_table("maintenance_material_batches")
