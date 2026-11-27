"""Group profile references, separately for person and service identities."""
from alembic import op
revision="0037_group_access_profiles"
down_revision="0036_profile_assignment"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""ALTER TABLE zradius_identity_groups
        ADD COLUMN person_template_id bigint REFERENCES zradius_access_templates(id) ON DELETE RESTRICT,
        ADD COLUMN service_template_id bigint REFERENCES zradius_access_templates(id) ON DELETE RESTRICT""")
    op.execute("CREATE INDEX ix_identity_group_person_template ON zradius_identity_groups(person_template_id)")
    op.execute("CREATE INDEX ix_identity_group_service_template ON zradius_identity_groups(service_template_id)")

def downgrade():
    op.execute("ALTER TABLE zradius_identity_groups DROP COLUMN person_template_id, DROP COLUMN service_template_id")
