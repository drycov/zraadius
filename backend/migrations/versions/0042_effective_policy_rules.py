"""Common read projection for direct and reusable access rules."""
from alembic import op
revision="0042_effective_policy_rules"
down_revision="0041_reusable_policies"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE VIEW zradius_effective_policy_rules AS
        SELECT r.id,r.identity_id,r.group_id,r.service,r.nas_id,r.effect,r.enabled,r.reason,
            NULL::bigint AS policy_id,NULL::text AS policy_name
        FROM zradius_policy_rules r
        UNION ALL
        SELECT -e.id,a.identity_id,a.group_id,e.service,e.nas_id,e.effect,
            (p.enabled AND e.enabled),e.reason,p.id,p.name
        FROM zradius_policy_entries e
        JOIN zradius_policies p ON p.id=e.policy_id
        JOIN zradius_policy_assignments a ON a.policy_id=p.id""")

def downgrade():
    op.execute("DROP VIEW zradius_effective_policy_rules")
