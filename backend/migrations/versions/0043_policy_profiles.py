"""Reuse existing typed access templates rather than duplicate service parameters."""
from alembic import op
revision="0043_policy_profiles"
down_revision="0042_effective_policy_rules"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""ALTER TABLE zradius_policies
        ADD COLUMN person_template_id bigint REFERENCES zradius_access_templates(id) ON DELETE RESTRICT,
        ADD COLUMN service_template_id bigint REFERENCES zradius_access_templates(id) ON DELETE RESTRICT""")

def downgrade():
    op.execute("ALTER TABLE zradius_policies DROP COLUMN person_template_id, DROP COLUMN service_template_id")
