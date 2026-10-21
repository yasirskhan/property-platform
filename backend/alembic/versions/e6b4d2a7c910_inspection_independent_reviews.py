"""Independent, immutable inspection decisions, separate from original evidence."""
from alembic import op
import sqlalchemy as sa

revision = "e6b4d2a7c910"
down_revision = "b8f2a91c4d65"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "unit_inspection_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("inspection_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=24), nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["inspection_id"], ["unit_inspection_records.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("decision IN ('CONFIRMED','FOLLOW_UP_REQUIRED')",
                           name="ck_unit_inspection_review_decision"),
    )
    op.create_index("ix_unit_inspection_reviews_organization_id", "unit_inspection_reviews", ["organization_id"])
    op.create_index("ix_unit_inspection_reviews_inspection_id", "unit_inspection_reviews",
                    ["inspection_id"], unique=True)
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""CREATE OR REPLACE FUNCTION prevent_inspection_review_mutation()
            RETURNS trigger AS $$
            BEGIN RAISE EXCEPTION 'unit_inspection_reviews is append-only'; END;
            $$ LANGUAGE plpgsql""")
        op.execute("""CREATE TRIGGER unit_inspection_review_immutable
            BEFORE UPDATE OR DELETE ON unit_inspection_reviews
            FOR EACH ROW EXECUTE FUNCTION prevent_inspection_review_mutation()""")
    elif op.get_bind().dialect.name == "sqlite":
        op.execute("""CREATE TRIGGER unit_inspection_review_no_update BEFORE UPDATE ON unit_inspection_reviews
            BEGIN SELECT RAISE(ABORT, 'unit_inspection_reviews is append-only'); END""")
        op.execute("""CREATE TRIGGER unit_inspection_review_no_delete BEFORE DELETE ON unit_inspection_reviews
            BEGIN SELECT RAISE(ABORT, 'unit_inspection_reviews is append-only'); END""")


def downgrade():
    if op.get_bind().execute(sa.text("SELECT 1 FROM unit_inspection_reviews LIMIT 1")).first():
        raise RuntimeError("Cannot discard independent inspection review evidence")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS unit_inspection_review_immutable ON unit_inspection_reviews")
        op.execute("DROP FUNCTION IF EXISTS prevent_inspection_review_mutation()")
    elif op.get_bind().dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS unit_inspection_review_no_update")
        op.execute("DROP TRIGGER IF EXISTS unit_inspection_review_no_delete")
    op.drop_index("ix_unit_inspection_reviews_inspection_id", table_name="unit_inspection_reviews")
    op.drop_index("ix_unit_inspection_reviews_organization_id", table_name="unit_inspection_reviews")
    op.drop_table("unit_inspection_reviews")
