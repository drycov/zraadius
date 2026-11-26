"""Classify unified identities and store operational profile metadata."""
from alembic import op
revision="0032_identity_profiles"
down_revision="0031_directory_mapping"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""ALTER TABLE zradius_identities
        ADD COLUMN account_type varchar(16) NOT NULL DEFAULT 'person' CHECK(account_type IN ('person','service')),
        ADD COLUMN account_owner varchar(200) NOT NULL DEFAULT '',
        ADD COLUMN account_purpose varchar(500) NOT NULL DEFAULT ''""")

def downgrade():
    raise RuntimeError("Explicit identity profile export required before downgrade")
