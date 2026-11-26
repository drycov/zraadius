"""Classify explicitly reported accounting services."""
from alembic import op
revision="0026_session_services"
down_revision="0025_identity_iam"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("ALTER TABLE radacct DROP CONSTRAINT IF EXISTS radacct_zradius_service_check")
    op.execute("""ALTER TABLE radacct ADD CONSTRAINT radacct_zradius_service_check
        CHECK(zradius_service IS NULL OR zradius_service IN ('l2tp','pppoe','hotspot','ipoe','device-aaa'))""")
    op.execute("CREATE INDEX ix_zradius_identity_sessions ON radacct(username,radacctid DESC) WHERE acctstoptime IS NULL")

def downgrade():
    raise RuntimeError("Explicit accounting migration required before downgrade")
