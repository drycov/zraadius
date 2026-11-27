"""Reusable policy catalog. Existing direct rules are preserved."""
from alembic import op
revision="0041_reusable_policies"
down_revision="0040_centralized_policy"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_policies (
        id bigserial PRIMARY KEY,
        name text NOT NULL UNIQUE CHECK(length(btrim(name)) BETWEEN 1 AND 128),
        description text NOT NULL DEFAULT '' CHECK(length(description)<=500),
        enabled boolean NOT NULL DEFAULT false,
        revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now())""")
    op.execute("""CREATE TABLE zradius_policy_entries (
        id bigserial PRIMARY KEY,
        policy_id bigint NOT NULL REFERENCES zradius_policies(id) ON DELETE CASCADE,
        service text CHECK(service IN ('device-aaa','l2tp','pppoe','hotspot','dot1x','wpa-enterprise')),
        nas_id integer REFERENCES nas(id) ON DELETE RESTRICT,
        effect text NOT NULL CHECK(effect IN ('ALLOW','DENY')),
        enabled boolean NOT NULL DEFAULT true,
        reason text NOT NULL CHECK(length(btrim(reason)) BETWEEN 1 AND 500),
        UNIQUE NULLS NOT DISTINCT(policy_id,service,nas_id,effect))""")
    op.execute("""CREATE TABLE zradius_policy_assignments (
        id bigserial PRIMARY KEY,
        policy_id bigint NOT NULL REFERENCES zradius_policies(id) ON DELETE RESTRICT,
        identity_id bigint REFERENCES zradius_identities(id) ON DELETE CASCADE,
        group_id bigint REFERENCES zradius_identity_groups(id) ON DELETE CASCADE,
        created_at timestamptz NOT NULL DEFAULT now(),
        CHECK(num_nonnulls(identity_id,group_id)=1),
        UNIQUE NULLS NOT DISTINCT(policy_id,identity_id,group_id))""")
    op.execute("CREATE INDEX ix_policy_assignment_identity ON zradius_policy_assignments(identity_id) WHERE identity_id IS NOT NULL")
    op.execute("CREATE INDEX ix_policy_assignment_group ON zradius_policy_assignments(group_id) WHERE group_id IS NOT NULL")
    op.execute("CREATE INDEX ix_policy_entry_nas ON zradius_policy_entries(nas_id) WHERE nas_id IS NOT NULL")

def downgrade():
    op.execute("DROP TABLE zradius_policy_assignments")
    op.execute("DROP TABLE zradius_policy_entries")
    op.execute("DROP TABLE zradius_policies")
