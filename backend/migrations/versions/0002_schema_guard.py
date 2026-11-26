"""Check required columns for an existing ZRADIUS installation."""
from alembic import op
from sqlalchemy import text
revision="0002_schema_guard"
down_revision="0001_baseline"
branch_labels=None
depends_on=None

def upgrade():
    required={
        "radcheck":{"id","username","attribute","op","value"},
        "radacct":{"acctuniqueid","acctsessionid","nasipaddress","acctstoptime","class"},
        "nas":{"id","nasname","secret"},
        "radippool":{"id","pool_name","framedipaddress","lease_token","lease_session"},
        "zradius_proxy_realms":{"id","realm","home_ip","enabled"},
        "zradius_pki_certificates":{"fingerprint","revoked_at"},
        "zradius_eap_users":{"username","nt_password"},
    }
    conn=op.get_bind()
    rows=conn.execute(text("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='public'"))
    actual={}
    for table,column in rows:
        actual.setdefault(table,set()).add(column)
    missing=[f"{t}.{c}" for t,cols in required.items() for c in sorted(cols-actual.get(t,set()))]
    if missing:
        raise RuntimeError("Incompatible existing schema: "+", ".join(missing))

def downgrade():
    pass
