"""Central credentials; preserve independent legacy users."""
from alembic import op
revision="0019_identity_credentials"
down_revision="0018_unified_identity"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_identity_credentials (
        identity_id bigint PRIMARY KEY REFERENCES zradius_identities(id) ON DELETE CASCADE,
        password_hash text NOT NULL CHECK(password_hash ~ '^[A-Za-z0-9+/]{107}=$'),
        nt_password varchar(32) CHECK(nt_password ~ '^[0-9a-f]{32}$'),
        updated_at timestamptz NOT NULL DEFAULT now()
    )""")
    # Do not silently choose between inconsistent existing hashes.
    op.execute("""INSERT INTO zradius_identity_credentials(identity_id,password_hash,nt_password)
        SELECT i.id,COALESCE(v.password_hash,d.password_hash),v.nt_password
        FROM zradius_identities i LEFT JOIN zradius_device_users d ON d.identity_id=i.id
        LEFT JOIN zradius_l2tp_users v ON v.identity_id=i.id
        WHERE COALESCE(v.password_hash,d.password_hash) IS NOT NULL
          AND (v.id IS NULL OR d.id IS NULL OR v.password_hash=d.password_hash)""")
    op.execute("ALTER TABLE zradius_device_users ALTER COLUMN password_hash DROP NOT NULL")
    op.execute("ALTER TABLE zradius_l2tp_users ALTER COLUMN password_hash DROP NOT NULL")
    op.execute("ALTER TABLE zradius_l2tp_users ALTER COLUMN nt_password DROP NOT NULL")
    op.execute("UPDATE zradius_device_users SET password_hash=NULL WHERE identity_id IS NOT NULL")
    op.execute("UPDATE zradius_l2tp_users SET password_hash=NULL,nt_password=NULL WHERE identity_id IS NOT NULL")
    op.execute("ALTER TABLE zradius_device_users ADD CHECK((identity_id IS NULL AND password_hash IS NOT NULL) OR (identity_id IS NOT NULL AND password_hash IS NULL))")
    op.execute("ALTER TABLE zradius_l2tp_users ADD CHECK((identity_id IS NULL AND password_hash IS NOT NULL AND nt_password IS NOT NULL) OR (identity_id IS NOT NULL AND password_hash IS NULL AND nt_password IS NULL))")

def downgrade():
    raise RuntimeError("Credential migration requires explicit recovery procedure")
