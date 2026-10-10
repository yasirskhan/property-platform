"""bank reconciliation and QIF statement lines
Revision ID: d8e0f2a4b6c3
Revises: c7d9e1f3a5b2
"""
from alembic import op
import sqlalchemy as sa
revision="d8e0f2a4b6c3";down_revision="c7d9e1f3a5b2";branch_labels=None;depends_on=None
def upgrade():
    op.create_table("bank_reconciliations",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("organization_id",sa.Integer(),nullable=False),sa.Column("bank_account_id",sa.Integer(),nullable=False),sa.Column("statement_date",sa.Date(),nullable=False),sa.Column("beginning_balance",sa.Numeric(14,2),nullable=False),sa.Column("ending_statement_balance",sa.Numeric(14,2),nullable=False),sa.Column("status",sa.String(20),nullable=False,server_default="OPEN"),sa.Column("finished_at",sa.DateTime()),sa.Column("finished_by_id",sa.Integer()),sa.Column("created_by_id",sa.Integer()),sa.Column("created_at",sa.DateTime(),nullable=False),sa.Column("updated_at",sa.DateTime(),nullable=False),sa.ForeignKeyConstraint(["organization_id"],["organizations.id"],ondelete="CASCADE"),sa.ForeignKeyConstraint(["bank_account_id"],["bank_accounts.id"],ondelete="RESTRICT"),sa.ForeignKeyConstraint(["finished_by_id"],["users.id"],ondelete="SET NULL"),sa.ForeignKeyConstraint(["created_by_id"],["users.id"],ondelete="SET NULL"))
    for c in ["organization_id","bank_account_id","statement_date","status"]:op.create_index(f"ix_bank_reconciliations_{c}","bank_reconciliations",[c])
    op.create_table("bank_reconciliation_items",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("reconciliation_id",sa.Integer(),nullable=False),sa.Column("organization_id",sa.Integer(),nullable=False),sa.Column("source_type",sa.String(30),nullable=False),sa.Column("source_id",sa.Integer(),nullable=False),sa.Column("transaction_date",sa.Date(),nullable=False),sa.Column("description",sa.String(500)),sa.Column("reference_number",sa.String(80)),sa.Column("signed_amount",sa.Numeric(14,2),nullable=False),sa.Column("cleared",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("created_at",sa.DateTime(),nullable=False),sa.ForeignKeyConstraint(["reconciliation_id"],["bank_reconciliations.id"],ondelete="CASCADE"),sa.ForeignKeyConstraint(["organization_id"],["organizations.id"],ondelete="CASCADE"),sa.UniqueConstraint("reconciliation_id","source_type","source_id",name="uq_bank_recon_source"))
    for c in ["reconciliation_id","organization_id","source_type","source_id","transaction_date","cleared"]:op.create_index(f"ix_bank_reconciliation_items_{c}","bank_reconciliation_items",[c])
    op.create_table("bank_statement_lines",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("reconciliation_id",sa.Integer(),nullable=False),sa.Column("organization_id",sa.Integer(),nullable=False),sa.Column("posted_date",sa.Date(),nullable=False),sa.Column("amount",sa.Numeric(14,2),nullable=False),sa.Column("payee",sa.String(300)),sa.Column("memo",sa.Text()),sa.Column("reference_number",sa.String(100)),sa.Column("matched_item_id",sa.Integer()),sa.Column("created_at",sa.DateTime(),nullable=False),sa.ForeignKeyConstraint(["reconciliation_id"],["bank_reconciliations.id"],ondelete="CASCADE"),sa.ForeignKeyConstraint(["organization_id"],["organizations.id"],ondelete="CASCADE"),sa.ForeignKeyConstraint(["matched_item_id"],["bank_reconciliation_items.id"],ondelete="SET NULL"))
    for c in ["reconciliation_id","organization_id","posted_date","matched_item_id"]:op.create_index(f"ix_bank_statement_lines_{c}","bank_statement_lines",[c])
    bind=op.get_bind()
    for key,desc in [("release.accounting.bank_reconciliation","Bank Reconciliation"),("release.accounting.bank_reconciliation.qif","QIF Import")]:
        bind.execute(sa.text("INSERT INTO release_gates (key,stage,description,created_at,updated_at) SELECT :key,'ALL_ORGS',:desc,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP WHERE NOT EXISTS (SELECT 1 FROM release_gates WHERE key=:key)"),{"key":key,"desc":desc})
        bind.execute(sa.text("UPDATE release_gates SET stage='ALL_ORGS',updated_at=CURRENT_TIMESTAMP WHERE key=:key"),{"key":key})
def downgrade():
    bind=op.get_bind()
    for key in ["release.accounting.bank_reconciliation.qif","release.accounting.bank_reconciliation"]:
        bind.execute(sa.text("DELETE FROM release_gate_organizations WHERE release_gate_id IN (SELECT id FROM release_gates WHERE key=:key)"),{"key":key});bind.execute(sa.text("DELETE FROM release_gates WHERE key=:key"),{"key":key})
    op.drop_table("bank_statement_lines");op.drop_table("bank_reconciliation_items");op.drop_table("bank_reconciliations")
