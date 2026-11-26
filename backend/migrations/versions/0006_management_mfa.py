"""TOTP enrollment and single-use recovery codes."""
from alembic import op
revision="0006_management_mfa"
down_revision="0005_iam_sessions"
branch_labels=None
depends_on=None
def upgrade():
    op.execute("ALTER TABLE zradius_admin_users ADD COLUMN mfa_secret text, ADD COLUMN mfa_pending text, ADD COLUMN mfa_pending_until timestamptz, ADD COLUMN mfa_last_step bigint NOT NULL DEFAULT -1, ADD COLUMN mfa_recovery text[] NOT NULL DEFAULT '{}' ")
def downgrade():
    raise RuntimeError("Refusing to remove MFA protections")
