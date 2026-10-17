"""add checks and bill allocations
Revision ID: f4a6c8d0e2b1
Revises: ad3e5f7b9c21
"""
from alembic import op
import sqlalchemy as sa
revision="f4a6c8d0e2b1"
down_revision="ad3e5f7b9c21"
branch_labels=None
depends_on=None
def upgrade()->None:
    op.create_table("checks",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("organization_id",sa.Integer(),nullable=False),sa.Column("bank_account_id",sa.Integer(),nullable=False),sa.Column("check_number",sa.String(length=40),nullable=True),sa.Column("check_date",sa.Date(),nullable=False),sa.Column("payee_name",sa.String(length=200),nullable=False),sa.Column("memo",sa.Text(),nullable=True),sa.Column("amount",sa.Numeric(14,2),nullable=False),sa.Column("status",sa.String(length=20),nullable=False,server_default="ISSUED"),sa.Column("gl_transaction_id",sa.Integer(),nullable=True),sa.Column("void_gl_transaction_id",sa.Integer(),nullable=True),sa.Column("void_reason",sa.Text(),nullable=True),sa.Column("voided_at",sa.DateTime(),nullable=True),sa.Column("voided_by_id",sa.Integer(),nullable=True),sa.Column("created_by_id",sa.Integer(),nullable=True),sa.Column("created_at",sa.DateTime(),nullable=False),sa.Column("updated_at",sa.DateTime(),nullable=False),sa.ForeignKeyConstraint(["organization_id"],["organizations.id"],ondelete="CASCADE"),sa.ForeignKeyConstraint(["bank_account_id"],["bank_accounts.id"],ondelete="RESTRICT"),sa.ForeignKeyConstraint(["gl_transaction_id"],["gl_transactions.id"],ondelete="SET NULL"),sa.ForeignKeyConstraint(["void_gl_transaction_id"],["gl_transactions.id"],ondelete="SET NULL"),sa.ForeignKeyConstraint(["voided_by_id"],["users.id"],ondelete="SET NULL"),sa.ForeignKeyConstraint(["created_by_id"],["users.id"],ondelete="SET NULL"),sa.UniqueConstraint("organization_id","check_number",name="uq_checks_org_number"))
    for col in ["organization_id","bank_account_id","check_number","check_date","payee_name","status","gl_transaction_id","void_gl_transaction_id"]:op.create_index(f"ix_checks_{col}","checks",[col])
    op.create_table("check_bill_allocations",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("check_id",sa.Integer(),nullable=False),sa.Column("bill_id",sa.Integer(),nullable=False),sa.Column("amount",sa.Numeric(14,2),nullable=False),sa.Column("created_at",sa.DateTime(),nullable=False),sa.ForeignKeyConstraint(["check_id"],["checks.id"],ondelete="CASCADE"),sa.ForeignKeyConstraint(["bill_id"],["bills.id"],ondelete="RESTRICT"),sa.UniqueConstraint("check_id","bill_id",name="uq_check_bill_allocation"))
    op.create_index("ix_check_bill_allocations_check_id","check_bill_allocations",["check_id"]);op.create_index("ix_check_bill_allocations_bill_id","check_bill_allocations",["bill_id"])
    bind=op.get_bind()
    for key,description in [("release.accounting.write_checks","Write Checks"),("release.accounting.check_printing","Check Printing")]:
        bind.execute(sa.text("INSERT INTO release_gates (key, stage, description, created_at, updated_at) SELECT :key, 'ALL_ORGS', :description, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP WHERE NOT EXISTS (SELECT 1 FROM release_gates WHERE key=:key)"),{"key":key,"description":description});bind.execute(sa.text("UPDATE release_gates SET stage='ALL_ORGS', updated_at=CURRENT_TIMESTAMP WHERE key=:key"),{"key":key})
def downgrade()->None:
    bind=op.get_bind()
    for key in ["release.accounting.write_checks","release.accounting.check_printing"]:
        bind.execute(sa.text("DELETE FROM release_gate_organizations WHERE release_gate_id IN (SELECT id FROM release_gates WHERE key=:key)"),{"key":key});bind.execute(sa.text("DELETE FROM release_gates WHERE key=:key"),{"key":key})
    op.drop_table("check_bill_allocations");op.drop_table("checks")
