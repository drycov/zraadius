"""Encrypted directory connection profiles."""
from alembic import op
revision="0028_directory_profiles"
down_revision="0027_login_namespace"
branch_labels=None
depends_on=None
def upgrade():
    op.execute("""CREATE TABLE zradius_directory_profiles (
        id bigserial PRIMARY KEY,
        name varchar(64) NOT NULL UNIQUE,
        host varchar(253) NOT NULL,
        base_dn varchar(1024) NOT NULL,
        bind_dn varchar(1024) NOT NULL,
        bind_secret text NOT NULL,
        enabled boolean NOT NULL DEFAULT false,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now()
    )""")
def downgrade():
    raise RuntimeError("Explicit directory profile removal required")
