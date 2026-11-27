"""Centralized diagnostic access rules. No runtime authorization changes."""
from alembic import op
revision="0040_centralized_policy"
down_revision="0039_policy_history"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_policy_rules (
        id bigserial PRIMARY KEY,
        identity_id bigint REFERENCES zradius_identities(id) ON DELETE CASCADE,
        group_id bigint REFERENCES zradius_identity_groups(id) ON DELETE CASCADE,
        service text CHECK(service IN ('device-aaa','l2tp','pppoe','hotspot','dot1x','wpa-enterprise')),
        nas_id integer REFERENCES nas(id) ON DELETE RESTRICT,
        effect text NOT NULL CHECK(effect IN ('ALLOW','DENY')),
        enabled boolean NOT NULL DEFAULT true,
        reason text NOT NULL CHECK(length(btrim(reason)) BETWEEN 1 AND 500),
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now(),
        CHECK(num_nonnulls(identity_id,group_id)=1),
        UNIQUE NULLS NOT DISTINCT(identity_id,group_id,service,nas_id,effect))""")
    op.execute("CREATE INDEX ix_policy_rules_identity ON zradius_policy_rules(identity_id) WHERE enabled")
    op.execute("CREATE INDEX ix_policy_rules_group ON zradius_policy_rules(group_id) WHERE enabled")
    op.execute("CREATE INDEX ix_policy_rules_nas ON zradius_policy_rules(nas_id) WHERE nas_id IS NOT NULL")

def downgrade():
    op.execute("DROP TABLE zradius_policy_rules")
