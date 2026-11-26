"""Custom RouterOS groups and per-grant Filter-Id."""
from alembic import op
revision="0009_device_profiles"
down_revision="0008_service_tokens"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_device_role_catalog (
        name varchar(64) PRIMARY KEY CHECK(name ~ '^[A-Za-z0-9_.-]{1,64}$'),
        description varchar(200) NOT NULL DEFAULT ''
    )""")
    op.execute("INSERT INTO zradius_device_role_catalog(name) VALUES ('read'),('write'),('full'),('forbackup')")
    op.execute("ALTER TABLE zradius_device_grants DROP CONSTRAINT zradius_device_grants_role_check")
    op.execute("ALTER TABLE zradius_device_grants ADD CONSTRAINT zradius_device_grants_role_fk FOREIGN KEY(role) REFERENCES zradius_device_role_catalog(name)")
    op.execute("ALTER TABLE zradius_device_grants ADD COLUMN filter_id varchar(64) CHECK(filter_id ~ '^[A-Za-z0-9_.-]{1,64}$')")

def downgrade():
    raise RuntimeError("Custom roles cannot be safely downgraded")
