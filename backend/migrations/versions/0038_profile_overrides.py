"""Individual service-level reconciliation protection."""
from alembic import op
revision="0038_profile_overrides"
down_revision="0037_group_access_profiles"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_profile_overrides (
        identity_id bigint NOT NULL REFERENCES zradius_identities(id) ON DELETE CASCADE,
        service text NOT NULL CHECK(service IN ('device-aaa','l2tp','pppoe','hotspot','dot1x','wpa-enterprise','console')),
        mode text NOT NULL CHECK(mode IN ('OVERRIDE','LOCKED','EXCLUDED')),
        reason text NOT NULL CHECK(length(btrim(reason)) BETWEEN 1 AND 500),
        updated_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY(identity_id,service))""")

def downgrade():
    op.execute("DROP TABLE zradius_profile_overrides")
