"""Encrypt existing NAS and proxy secrets in one transaction."""
from alembic import op
from secret_crypto import key,seal,unseal
revision="0003_encrypt_secrets"
down_revision="0002_schema_guard"
branch_labels=None
depends_on=None

def upgrade():
    key()
    conn=op.get_bind().connection.driver_connection
    for table,identity in (("nas","nasname"),("zradius_proxy_realms","realm")):
        conn.execute(f"ALTER TABLE {table} ALTER COLUMN secret TYPE text")
        if table=="zradius_proxy_realms":
            conn.execute("ALTER TABLE zradius_proxy_realms DROP CONSTRAINT IF EXISTS zradius_proxy_realms_secret_check")
        for id,name,value in conn.execute(f"SELECT id,{identity},secret FROM {table} FOR UPDATE").fetchall():
            aad=table+":"+name
            if value.startswith("v1:"):
                unseal(value,aad)
            else:
                conn.execute(f"UPDATE {table} SET secret=%s WHERE id=%s",(seal(value,aad),id))
        conn.execute(f"ALTER TABLE {table} ADD CONSTRAINT {table}_secret_envelope CHECK (secret ~ '^v1:[A-Za-z0-9_=-]+$')")

def downgrade():
    raise RuntimeError("Refusing plaintext downgrade; restore a verified backup")
