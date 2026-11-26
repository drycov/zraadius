"""Explicit AD-to-local group mapping; no automatic authorization."""
from alembic import op
revision="0031_directory_mapping"
down_revision="0030_directory_groups"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_directory_group_mappings (
        directory_group_id bigint NOT NULL REFERENCES zradius_directory_groups(id) ON DELETE CASCADE,
        identity_group_id bigint NOT NULL REFERENCES zradius_identity_groups(id) ON DELETE RESTRICT,
        created_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY(directory_group_id,identity_group_id)
    )""")

def downgrade():
    op.execute("DROP TABLE zradius_directory_group_mappings")
