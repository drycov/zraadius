"""Unified identity links, retaining independent legacy accounts."""
from alembic import op
revision="0018_unified_identity"
down_revision="0017_vpn_accounting"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_identities (
        id bigserial PRIMARY KEY,
        username varchar(64) NOT NULL UNIQUE CHECK(username ~ '^[A-Za-z0-9_.-]{1,64}$'),
        full_name varchar(200) NOT NULL DEFAULT '',
        department varchar(200) NOT NULL DEFAULT '',
        enabled boolean NOT NULL DEFAULT true,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE(id,username)
    )""")
    for table in ("zradius_device_users","zradius_l2tp_users"):
        op.execute(f"ALTER TABLE {table} ADD COLUMN identity_id bigint UNIQUE")
        op.execute(f"ALTER TABLE {table} ADD FOREIGN KEY(identity_id,username) REFERENCES zradius_identities(id,username) ON DELETE RESTRICT")

def downgrade():
    raise RuntimeError("Explicit identity migration required before downgrade")
