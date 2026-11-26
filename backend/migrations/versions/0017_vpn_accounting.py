"""Explicit L2TP accounting classification."""
from alembic import op
revision="0017_vpn_accounting"
down_revision="0016_vpn_pools"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("ALTER TABLE radacct ADD COLUMN zradius_service text CHECK(zradius_service IS NULL OR zradius_service='l2tp')")
    op.execute("CREATE INDEX radacct_l2tp_history_idx ON radacct(radacctid DESC) WHERE zradius_service='l2tp'")
    op.execute("CREATE INDEX radacct_l2tp_open_idx ON radacct(radacctid DESC) WHERE zradius_service='l2tp' AND acctstoptime IS NULL")

def downgrade():
    op.execute("DROP INDEX radacct_l2tp_open_idx")
    op.execute("DROP INDEX radacct_l2tp_history_idx")
    op.execute("ALTER TABLE radacct DROP COLUMN zradius_service")
