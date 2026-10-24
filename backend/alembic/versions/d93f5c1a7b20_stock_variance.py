"""P5-PROC-06 approved immutable physical stock variance requests.

Physically missing units are not a GL posting, payable, tenant charge or an
external insurer/supplier receipt. A different Owner/Admin must review.
"""
from alembic import op
import sqlalchemy as sa

revision = "d93f5c1a7b20"
down_revision = "a15b6c7d8e90"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("maintenance_material_variances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("material_order_id", sa.Integer(), sa.ForeignKey("maintenance_material_orders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("request_key", sa.String(80), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reported_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reported_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id","request_key",name="uq_material_variance_request"),
        sa.CheckConstraint("quantity > 0 AND quantity <= 10000",name="ck_material_variance_qty"),
    )
    op.create_table("maintenance_material_variance_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("variance_id", sa.Integer(), sa.ForeignKey("maintenance_material_variances.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("approved", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reviewed_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("variance_id",name="uq_material_variance_decision"),
        sa.CheckConstraint("approved IN (0,1)",name="ck_material_variance_approval"),
    )
    op.create_table("maintenance_material_variance_restorations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("variance_id", sa.Integer(), sa.ForeignKey("maintenance_material_variances.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("restored_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("restored_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("variance_id",name="uq_material_variance_restore"),
    )
    for name in ("maintenance_material_variances","maintenance_material_variance_decisions","maintenance_material_variance_restorations"):
        op.create_index("ix_" + name + "_organization_id",name,["organization_id"])
    op.create_index("ix_maintenance_material_variances_material_order_id","maintenance_material_variances",["material_order_id"])
    db=op.get_bind()
    for name in ("maintenance_material_variances","maintenance_material_variance_decisions","maintenance_material_variance_restorations"):
        if db.dialect.name=="postgresql":
            op.execute(f"""CREATE FUNCTION prevent_{name}_mutation() RETURNS trigger AS $immutable$
                BEGIN RAISE EXCEPTION '{name} is append-only'; END;
                $immutable$ LANGUAGE plpgsql""")
            op.execute(f"""CREATE TRIGGER {name}_immutable BEFORE UPDATE OR DELETE ON {name}
                FOR EACH ROW EXECUTE FUNCTION prevent_{name}_mutation()""")
        elif db.dialect.name=="sqlite":
            for action in ("update","delete"):
                op.execute(f"""CREATE TRIGGER {name}_no_{action}
                    BEFORE {action.upper()} ON {name}
                    BEGIN SELECT RAISE(ABORT,'{name} is append-only'); END""")


def downgrade():
    db=op.get_bind()
    for name in ("maintenance_material_variances","maintenance_material_variance_decisions","maintenance_material_variance_restorations"):
        if db.execute(sa.text(f"SELECT 1 FROM {name} LIMIT 1")).first():
            raise RuntimeError("Cannot delete permanent physical stock variance evidence")
    for name in ("maintenance_material_variance_restorations","maintenance_material_variance_decisions","maintenance_material_variances"):
        if db.dialect.name=="postgresql":
            op.execute(f"DROP TRIGGER IF EXISTS {name}_immutable ON {name}")
            op.execute(f"DROP FUNCTION IF EXISTS prevent_{name}_mutation()")
        elif db.dialect.name=="sqlite":
            for action in ("update","delete"):
                op.execute(f"DROP TRIGGER IF EXISTS {name}_no_{action}")
        if name=="maintenance_material_variances":
            op.drop_index("ix_maintenance_material_variances_material_order_id",table_name=name)
        op.drop_index("ix_" + name + "_organization_id",table_name=name)
        op.drop_table(name)
