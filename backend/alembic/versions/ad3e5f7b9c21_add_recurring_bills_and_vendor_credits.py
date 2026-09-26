"""add recurring bills and vendor credits

Revision ID: ad3e5f7b9c21
Revises: 9c2e4f6a8b10
"""
from alembic import op
import sqlalchemy as sa
revision="ad3e5f7b9c21"
down_revision="9c2e4f6a8b10"
branch_labels=None
depends_on=None

def upgrade()->None:
    op.create_table("recurring_bills",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("organization_id",sa.Integer(),nullable=False),
        sa.Column("entry_type",sa.String(length=20),nullable=False,server_default="BILL"),
        sa.Column("payee_name",sa.String(length=200),nullable=False),
        sa.Column("payee_user_id",sa.Integer(),nullable=True),
        sa.Column("start_date",sa.Date(),nullable=False),
        sa.Column("end_date",sa.Date(),nullable=True),
        sa.Column("bill_day",sa.Integer(),nullable=False),
        sa.Column("due_day",sa.Integer(),nullable=True),
        sa.Column("post_code",sa.String(length=40),nullable=True),
        sa.Column("next_post_date",sa.Date(),nullable=False),
        sa.Column("last_posted_date",sa.Date(),nullable=True),
        sa.Column("reference_number",sa.String(length=60),nullable=True),
        sa.Column("remarks",sa.Text(),nullable=True),
        sa.Column("payable_gl_account_id",sa.Integer(),nullable=False),
        sa.Column("cash_gl_account_id",sa.Integer(),nullable=True),
        sa.Column("property_id",sa.Integer(),nullable=True),
        sa.Column("unit_id",sa.Integer(),nullable=True),
        sa.Column("owner_id",sa.Integer(),nullable=True),
        sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column("created_by_id",sa.Integer(),nullable=True),
        sa.Column("created_at",sa.DateTime(),nullable=False),
        sa.Column("updated_at",sa.DateTime(),nullable=False),
        sa.ForeignKeyConstraint(["organization_id"],["organizations.id"],ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payee_user_id"],["users.id"],ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["payable_gl_account_id"],["gl_accounts.id"],ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cash_gl_account_id"],["gl_accounts.id"],ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["property_id"],["properties.id"],ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["unit_id"],["units.id"],ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"],["users.id"],ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"],["users.id"],ondelete="SET NULL"))
    op.create_index("ix_recurring_bills_due","recurring_bills",["organization_id","is_active","next_post_date"])
    for col in ["organization_id","entry_type","payee_user_id","post_code","next_post_date","payable_gl_account_id","cash_gl_account_id","property_id","unit_id","owner_id","created_by_id"]:
        op.create_index(f"ix_recurring_bills_{col}","recurring_bills",[col])

    op.create_table("recurring_bill_lines",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("recurring_bill_id",sa.Integer(),nullable=False),
        sa.Column("gl_account_id",sa.Integer(),nullable=False),
        sa.Column("property_id",sa.Integer(),nullable=True),
        sa.Column("unit_id",sa.Integer(),nullable=True),
        sa.Column("description",sa.String(length=500),nullable=True),
        sa.Column("amount",sa.Numeric(14,2),nullable=False),
        sa.Column("created_at",sa.DateTime(),nullable=False),
        sa.ForeignKeyConstraint(["recurring_bill_id"],["recurring_bills.id"],ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["gl_account_id"],["gl_accounts.id"],ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["property_id"],["properties.id"],ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["unit_id"],["units.id"],ondelete="SET NULL"))
    for col in ["recurring_bill_id","gl_account_id","property_id","unit_id"]:
        op.create_index(f"ix_recurring_bill_lines_{col}","recurring_bill_lines",[col])

    op.create_table("vendor_credits",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("organization_id",sa.Integer(),nullable=False),
        sa.Column("credit_number",sa.String(length=40),nullable=True),
        sa.Column("payee_name",sa.String(length=200),nullable=False),
        sa.Column("payee_user_id",sa.Integer(),nullable=True),
        sa.Column("credit_date",sa.Date(),nullable=False),
        sa.Column("reference_number",sa.String(length=60),nullable=True),
        sa.Column("amount",sa.Numeric(14,2),nullable=False),
        sa.Column("property_id",sa.Integer(),nullable=True),
        sa.Column("unit_id",sa.Integer(),nullable=True),
        sa.Column("owner_id",sa.Integer(),nullable=True),
        sa.Column("payable_gl_account_id",sa.Integer(),nullable=False),
        sa.Column("remarks",sa.Text(),nullable=True),
        sa.Column("source_type",sa.String(length=40),nullable=True),
        sa.Column("source_id",sa.Integer(),nullable=True),
        sa.Column("gl_transaction_id",sa.Integer(),nullable=True),
        sa.Column("status",sa.String(length=20),nullable=False,server_default="POSTED"),
        sa.Column("is_reversed",sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column("reversal_of_id",sa.Integer(),nullable=True),
        sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column("created_by_id",sa.Integer(),nullable=True),
        sa.Column("created_at",sa.DateTime(),nullable=False),
        sa.Column("updated_at",sa.DateTime(),nullable=False),
        sa.ForeignKeyConstraint(["organization_id"],["organizations.id"],ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payee_user_id"],["users.id"],ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["property_id"],["properties.id"],ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["unit_id"],["units.id"],ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"],["users.id"],ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["payable_gl_account_id"],["gl_accounts.id"],ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["gl_transaction_id"],["gl_transactions.id"],ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reversal_of_id"],["vendor_credits.id"],ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"],["users.id"],ondelete="SET NULL"))
    for col in ["organization_id","credit_number","payee_user_id","credit_date","property_id","unit_id","owner_id","payable_gl_account_id","source_type","gl_transaction_id","status","is_active"]:
        op.create_index(f"ix_vendor_credits_{col}","vendor_credits",[col])

    op.create_table("vendor_credit_lines",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("vendor_credit_id",sa.Integer(),nullable=False),
        sa.Column("organization_id",sa.Integer(),nullable=False),
        sa.Column("gl_account_id",sa.Integer(),nullable=False),
        sa.Column("property_id",sa.Integer(),nullable=True),
        sa.Column("unit_id",sa.Integer(),nullable=True),
        sa.Column("description",sa.String(length=500),nullable=True),
        sa.Column("amount",sa.Numeric(14,2),nullable=False),
        sa.Column("created_at",sa.DateTime(),nullable=False),
        sa.ForeignKeyConstraint(["vendor_credit_id"],["vendor_credits.id"],ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"],["organizations.id"],ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["gl_account_id"],["gl_accounts.id"],ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["property_id"],["properties.id"],ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["unit_id"],["units.id"],ondelete="SET NULL"))
    for col in ["vendor_credit_id","organization_id","gl_account_id","property_id","unit_id"]:
        op.create_index(f"ix_vendor_credit_lines_{col}","vendor_credit_lines",[col])
    bind=op.get_bind()
    for key,description in [
        ("release.accounting.bills.recurring","Recurring bills and credits"),
        ("release.accounting.bills.manual_post","Manual posting of recurring bills"),
        ("release.accounting.vendor_credits","Vendor credits")]:
        bind.execute(sa.text("INSERT INTO release_gates (key, stage, description, created_at, updated_at) SELECT :key, 'ALL_ORGS', :description, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP WHERE NOT EXISTS (SELECT 1 FROM release_gates WHERE key=:key)"),{"key":key,"description":description})
        bind.execute(sa.text("UPDATE release_gates SET stage='ALL_ORGS', updated_at=CURRENT_TIMESTAMP WHERE key=:key"),{"key":key})

def downgrade()->None:
    bind=op.get_bind()
    for key in ["release.accounting.bills.recurring","release.accounting.bills.manual_post","release.accounting.vendor_credits"]:
        bind.execute(sa.text("DELETE FROM release_gate_organizations WHERE release_gate_id IN (SELECT id FROM release_gates WHERE key=:key)"),{"key":key})
        bind.execute(sa.text("DELETE FROM release_gates WHERE key=:key"),{"key":key})
    op.drop_table("vendor_credit_lines")
    op.drop_table("vendor_credits")
    op.drop_table("recurring_bill_lines")
    op.drop_table("recurring_bills")
