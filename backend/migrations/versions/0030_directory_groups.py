"""Directory security group inventory, separate from live authorization."""
from alembic import op
revision="0030_directory_groups"
down_revision="0029_directory_identities"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_directory_groups (
        id bigserial PRIMARY KEY,
        profile_id bigint NOT NULL REFERENCES zradius_directory_profiles(id) ON DELETE RESTRICT,
        object_guid uuid NOT NULL,
        name varchar(256) NOT NULL,
        distinguished_name text NOT NULL,
        observed_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE(profile_id,object_guid)
    )""")
    op.execute("""CREATE TABLE zradius_directory_group_members (
        group_id bigint NOT NULL REFERENCES zradius_directory_groups(id) ON DELETE CASCADE,
        identity_id bigint NOT NULL REFERENCES zradius_directory_identities(identity_id) ON DELETE CASCADE,
        observed_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY(group_id,identity_id)
    )""")

def downgrade():
    op.execute("DROP TABLE zradius_directory_group_members")
    op.execute("DROP TABLE zradius_directory_groups")
