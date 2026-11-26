"""Dedicated L2TP credentials and NAS-scoped address assignments."""
from alembic import op
revision="0013_ppp_vpn"
down_revision="0012_device_reply_profiles"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_ppp_profiles (
        id bigserial PRIMARY KEY,
        name varchar(64) NOT NULL UNIQUE CHECK(name ~ '^[A-Za-z0-9_.-]{1,64}$'),
        pool varchar(64) CHECK(pool ~ '^[A-Za-z0-9_.-]{1,64}$'),
        interim_seconds integer NOT NULL DEFAULT 300 CHECK(interim_seconds BETWEEN 60 AND 86400),
        description varchar(200) NOT NULL DEFAULT ''
    )""")
    op.execute("""CREATE TABLE zradius_l2tp_users (
        id bigserial PRIMARY KEY,
        username varchar(64) NOT NULL UNIQUE CHECK(username ~ '^[A-Za-z0-9_.@-]{1,64}$'),
        nt_password varchar(32) NOT NULL CHECK(nt_password ~ '^[0-9a-f]{32}$'),
        password_hash text NOT NULL,
        nas_id bigint NOT NULL REFERENCES nas(id) ON DELETE RESTRICT,
        profile_id bigint NOT NULL REFERENCES zradius_ppp_profiles(id) ON DELETE RESTRICT,
        static_ip inet CHECK(static_ip IS NULL OR (family(static_ip)=4 AND masklen(static_ip)=32)),
        enabled boolean NOT NULL DEFAULT true,
        description varchar(200) NOT NULL DEFAULT '',
        created_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE(nas_id,static_ip)
    )""")

def downgrade():
    raise RuntimeError("Refusing to discard L2TP credentials")
