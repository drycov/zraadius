"""Persistent planning attributes for existing reusable policies."""
from alembic import op
revision="0044_policy_attributes"
down_revision="0043_policy_profiles"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_policy_attributes (
        id bigserial PRIMARY KEY,
        policy_id bigint NOT NULL REFERENCES zradius_policies(id) ON DELETE CASCADE,
        service text NOT NULL CHECK(service IN ('device-aaa','l2tp','pppoe','hotspot','dot1x','wpa-enterprise')),
        nas_id bigint REFERENCES nas(id) ON DELETE RESTRICT,
        name varchar(64) NOT NULL,
        attribute_list text NOT NULL CHECK(attribute_list IN ('check','control','reply')),
        operator varchar(2) NOT NULL CHECK(operator IN (':=','==','!=')),
        value varchar(253) NOT NULL,
        priority integer NOT NULL CHECK(priority BETWEEN 0 AND 1000),
        enabled boolean NOT NULL DEFAULT true,
        UNIQUE NULLS NOT DISTINCT(policy_id,service,nas_id,name,attribute_list)
    )""")

def downgrade():
    raise RuntimeError("Export attribute policies before downgrade")
