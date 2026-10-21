"""Record Owner/Admin intent for future maintenance dispatch automation.

This revision does not activate an autonomous executor or any delivery channel.
"""
from alembic import op
import sqlalchemy as sa

revision = "f6c8e2a104d9"
down_revision = "d7a1c0e948b2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("maintenance_dispatch_groups",
                  sa.Column("automation_requested", sa.Boolean(), nullable=False,
                            server_default=sa.false()))


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM maintenance_dispatch_groups WHERE automation_requested = true LIMIT 1")).first():
        raise RuntimeError("Cannot discard customer automation opt-in evidence")
    op.drop_column("maintenance_dispatch_groups", "automation_requested")
