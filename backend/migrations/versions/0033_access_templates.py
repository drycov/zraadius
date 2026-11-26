"""Reusable account creation templates, independent of runtime authorization."""
from alembic import op
revision="0033_access_templates"
down_revision="0032_identity_profiles"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_access_templates (
        id bigserial PRIMARY KEY,
        name varchar(100) NOT NULL UNIQUE,
        account_type varchar(16) NOT NULL CHECK(account_type IN ('person','service')),
        description varchar(500) NOT NULL DEFAULT '',
        services text[] NOT NULL DEFAULT '{}',
        enabled boolean NOT NULL DEFAULT true,
        CHECK(services <@ ARRAY['device-aaa','l2tp','pppoe','hotspot','dot1x','wpa-enterprise','console']::text[]),
        CHECK(account_type <> 'service' OR NOT ('console'=ANY(services)))
    )""")
    op.execute("""INSERT INTO zradius_access_templates(name,account_type,services) VALUES
        ('Network Administrator','person',ARRAY['device-aaa','l2tp','console']),
        ('Network Operator','person',ARRAY['device-aaa','console']),
        ('Corporate Employee','person',ARRAY['l2tp','dot1x','wpa-enterprise']),
        ('Monitoring Service','service',ARRAY['device-aaa']),
        ('Integration Service','service',ARRAY[]::text[]),
        ('ISP Subscriber','person',ARRAY['pppoe']),
        ('Guest','person',ARRAY['hotspot'])""")

def downgrade():
    op.execute("DROP TABLE zradius_access_templates")
