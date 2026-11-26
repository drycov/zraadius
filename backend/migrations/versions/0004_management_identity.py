"""Separate management identities and revocable opaque sessions."""
from alembic import op
revision="0004_management_identity"
down_revision="0003_encrypt_secrets"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_admin_users (
        id bigserial PRIMARY KEY, username varchar(64) UNIQUE NOT NULL,
        password_hash text NOT NULL, role text NOT NULL CHECK(role IN ('admin','operator','auditor')),
        enabled boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()
    )""")
    op.execute("""CREATE TABLE zradius_admin_sessions (
        token_hash char(64) PRIMARY KEY,
        user_id bigint NOT NULL REFERENCES zradius_admin_users(id) ON DELETE CASCADE,
        expires_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
    )""")
    op.execute("CREATE INDEX zradius_admin_sessions_user_idx ON zradius_admin_sessions(user_id)")
    op.execute("""CREATE TABLE zradius_login_limits (
        bucket char(64) PRIMARY KEY, attempts integer NOT NULL,
        window_start timestamptz NOT NULL DEFAULT now()
    )""")
    op.execute("ALTER TABLE zradius_audit ADD COLUMN actor text")

def downgrade():
    raise RuntimeError("Restore a verified backup instead of deleting management identities")
