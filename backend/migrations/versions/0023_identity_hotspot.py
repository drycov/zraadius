"""Permanent unified Hotspot assignments; vouchers remain independent."""
from alembic import op
revision="0023_identity_hotspot"
down_revision="0022_identity_pppoe"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_identity_hotspot (
        identity_id bigint PRIMARY KEY REFERENCES zradius_identities(id) ON DELETE CASCADE,
        nas_id bigint NOT NULL REFERENCES nas(id) ON DELETE RESTRICT,
        enabled boolean NOT NULL DEFAULT true,
        rate_limit varchar(32) NOT NULL CHECK(rate_limit ~ '^[1-9][0-9]{0,5}M/[1-9][0-9]{0,5}M$'),
        session_seconds integer NOT NULL DEFAULT 3600 CHECK(session_seconds BETWEEN 60 AND 86400),
        idle_seconds integer NOT NULL DEFAULT 300 CHECK(idle_seconds BETWEEN 60 AND session_seconds)
    )""")

def downgrade():
    raise RuntimeError("Explicit Hotspot migration required before downgrade")
