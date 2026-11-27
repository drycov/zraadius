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
        runtime_apply boolean NOT NULL DEFAULT false,
        CHECK (NOT runtime_apply OR (service='pppoe' AND attribute_list='reply' AND operator=':=' AND name IN ('Idle-Timeout','Session-Timeout') AND CASE WHEN value ~ '^[0-9]{1,6}
        UNIQUE NULLS NOT DISTINCT(policy_id,service,nas_id,name,attribute_list)
    )""")

    op.execute("""CREATE VIEW zradius_pppoe_runtime_timeouts AS
        WITH candidates AS (
            SELECT i.id AS identity_id,i.username,p.nas_id,n.nasname,e.name,e.value,
                dense_rank() OVER (PARTITION BY i.id,p.nas_id,e.name ORDER BY (a.identity_id IS NOT NULL) DESC,(e.nas_id IS NOT NULL) DESC,e.priority DESC) AS precedence
            FROM zradius_identity_pppoe p JOIN zradius_identities i ON i.id=p.identity_id
            JOIN nas n ON n.id=p.nas_id
            JOIN zradius_policy_assignments a ON a.identity_id=i.id OR EXISTS(SELECT 1 FROM zradius_identity_group_members m WHERE m.identity_id=i.id AND m.group_id=a.group_id)
            JOIN zradius_policies policy ON policy.id=a.policy_id AND policy.enabled
            JOIN zradius_policy_attributes e ON e.policy_id=policy.id AND e.enabled AND e.runtime_apply AND e.service='pppoe' AND (e.nas_id IS NULL OR e.nas_id=p.nas_id)
        ) SELECT identity_id,username,nas_id,nasname,name,CASE WHEN count(DISTINCT value)=1 THEN min(value)::integer ELSE -1 END AS seconds
          FROM candidates WHERE precedence=1 GROUP BY identity_id,username,nas_id,nasname,name""")

def downgrade():
    raise RuntimeError("Export attribute policies before downgrade")
 THEN value::integer BETWEEN 1 AND 604800 ELSE false END)),
        UNIQUE NULLS NOT DISTINCT(policy_id,service,nas_id,name,attribute_list)
    )""")

def downgrade():
    raise RuntimeError("Export attribute policies before downgrade")
