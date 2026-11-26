"""Named, immutable Device AAA reply templates."""
from alembic import op
revision="0012_device_reply_profiles"
down_revision="0011_nas_groups"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_device_reply_profiles (
        id bigserial PRIMARY KEY,
        name varchar(64) NOT NULL UNIQUE CHECK(name ~ '^[A-Za-z0-9_.-]{1,64}$'),
        description varchar(200) NOT NULL DEFAULT '',
        role text NOT NULL REFERENCES zradius_device_role_catalog(name),
        filter_id varchar(64) CHECK(filter_id ~ '^[A-Za-z0-9_.-]{1,64}$')
    )""")
    for table in ("zradius_device_grants","zradius_device_group_grants","zradius_device_nas_group_grants"):
        op.execute(f"ALTER TABLE {table} ADD COLUMN profile_id bigint REFERENCES zradius_device_reply_profiles(id)")
    op.execute("""INSERT INTO zradius_device_reply_profiles(name,description,role,filter_id) VALUES
        ('readonly','Read-only RouterOS group','read','global-read'),
        ('engineering','Full RouterOS group with global-read filter','full','global-read'),
        ('administrator','Full RouterOS group with admin filter','full','admin'),
        ('backup','Backup automation group','forbackup','global-read')""")

def downgrade():
    for table in ("zradius_device_grants","zradius_device_group_grants","zradius_device_nas_group_grants"):
        op.execute(f"ALTER TABLE {table} DROP COLUMN profile_id")
    op.execute("DROP TABLE zradius_device_reply_profiles")
