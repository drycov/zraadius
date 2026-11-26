"""Service account lifecycle metadata and review deadlines."""
from alembic import op
revision="0035_service_lifecycle"
down_revision="0034_template_parameters"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""ALTER TABLE zradius_identities
        ADD COLUMN account_expires_at timestamptz,
        ADD COLUMN rotation_interval_days integer CHECK(rotation_interval_days BETWEEN 1 AND 3650),
        ADD CONSTRAINT service_lifecycle_only CHECK(account_type='service' OR
            (account_expires_at IS NULL AND rotation_interval_days IS NULL))""")

def downgrade():
    op.execute("""ALTER TABLE zradius_identities DROP CONSTRAINT service_lifecycle_only,
        DROP COLUMN rotation_interval_days, DROP COLUMN account_expires_at""")
