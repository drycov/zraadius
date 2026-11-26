"""Separate unified EAP service permissions on dedicated NAS."""
from alembic import op
revision="0024_identity_eap"
down_revision="0023_identity_hotspot"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_identity_eap (
        identity_id bigint NOT NULL REFERENCES zradius_identities(id) ON DELETE CASCADE,
        service_code text NOT NULL CHECK(service_code IN ('dot1x','wpa-enterprise')),
        nas_id bigint NOT NULL REFERENCES nas(id) ON DELETE RESTRICT,
        vlan_id integer CHECK(vlan_id BETWEEN 1 AND 4094),
        enabled boolean NOT NULL DEFAULT true,
        PRIMARY KEY(identity_id,service_code)
    )""")

def downgrade():
    raise RuntimeError("Explicit EAP migration required before downgrade")
