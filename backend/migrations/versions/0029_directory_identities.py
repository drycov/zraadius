"""Stable directory object links."""
from alembic import op
revision="0029_directory_identities"
down_revision="0028_directory_profiles"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_directory_identities (
        identity_id bigint PRIMARY KEY REFERENCES zradius_identities(id) ON DELETE RESTRICT,
        profile_id bigint NOT NULL REFERENCES zradius_directory_profiles(id) ON DELETE RESTRICT,
        object_guid uuid NOT NULL,
        directory_username varchar(64) NOT NULL,
        directory_enabled boolean NOT NULL,
        imported_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE(profile_id,object_guid)
    )""")

def downgrade():
    raise RuntimeError("Explicit directory unlink procedure required")
