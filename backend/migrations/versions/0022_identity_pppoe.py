"""Unified PPPoE assignments, scoped to registered NAS."""
from alembic import op
revision="0022_identity_pppoe"
down_revision="0021_identity_vpn_templates"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_identity_pppoe (
        identity_id bigint PRIMARY KEY REFERENCES zradius_identities(id) ON DELETE CASCADE,
        nas_id bigint NOT NULL REFERENCES nas(id) ON DELETE RESTRICT,
        enabled boolean NOT NULL DEFAULT true,
        rate_limit varchar(32) NOT NULL CHECK(rate_limit ~ '^[1-9][0-9]{0,5}M/[1-9][0-9]{0,5}M$'),
        pool varchar(64) NOT NULL CHECK(pool ~ '^[A-Za-z0-9_.-]{1,64}$'),
        interim_seconds integer NOT NULL DEFAULT 300 CHECK(interim_seconds BETWEEN 60 AND 86400)
    )""")

def downgrade():
    raise RuntimeError("Explicit PPPoE migration required before downgrade")
