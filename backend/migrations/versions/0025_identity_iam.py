"""Link management accounts to unified identities."""
from alembic import op
revision="0025_identity_iam"
down_revision="0024_identity_eap"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("ALTER TABLE zradius_admin_users ADD COLUMN identity_id bigint UNIQUE")
    op.execute("ALTER TABLE zradius_admin_users ADD FOREIGN KEY(identity_id,username) REFERENCES zradius_identities(id,username) ON DELETE RESTRICT")
    op.execute("ALTER TABLE zradius_identity_credentials ADD COLUMN web_password_hash text")

def downgrade():
    raise RuntimeError("Explicit IAM recovery required before downgrade")
