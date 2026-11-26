"""Public session identifiers independent of secret token digests."""
from alembic import op
revision="0005_iam_sessions"
down_revision="0004_management_identity"
branch_labels=None
depends_on=None
def upgrade():
    op.execute("ALTER TABLE zradius_admin_sessions ADD COLUMN session_id uuid NOT NULL DEFAULT gen_random_uuid()")
    op.execute("CREATE UNIQUE INDEX zradius_admin_sessions_public_id ON zradius_admin_sessions(session_id)")
def downgrade():
    op.execute("ALTER TABLE zradius_admin_sessions DROP COLUMN session_id")
