"""Indexes for filtered accounting cursor queries."""
from alembic import op
revision="0007_accounting_indexes"
down_revision="0006_management_mfa"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("CREATE INDEX zradius_radacct_user_cursor ON radacct(username,radacctid DESC)")
    op.execute("CREATE INDEX zradius_radacct_nas_cursor ON radacct(nasipaddress,radacctid DESC)")
    op.execute("CREATE INDEX zradius_radacct_open_cursor ON radacct(radacctid DESC) WHERE acctstoptime IS NULL")

def downgrade():
    for index in ("zradius_radacct_user_cursor","zradius_radacct_nas_cursor","zradius_radacct_open_cursor"):
        op.execute("DROP INDEX "+index)
