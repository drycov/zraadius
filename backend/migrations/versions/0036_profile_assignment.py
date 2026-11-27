"""Persistent reference to an access template; never changes runtime grants."""
from alembic import op
revision="0036_profile_assignment"
down_revision="0035_service_lifecycle"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""ALTER TABLE zradius_identities ADD COLUMN access_template_id bigint
        REFERENCES zradius_access_templates(id) ON DELETE RESTRICT""")
    op.execute("CREATE INDEX ix_identity_access_template ON zradius_identities(access_template_id)")

def downgrade():
    op.execute("ALTER TABLE zradius_identities DROP COLUMN access_template_id")
