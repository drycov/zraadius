"""Explicit group VPN assignment templates; never share static addresses."""
from alembic import op
revision="0021_identity_vpn_templates"
down_revision="0020_identity_groups"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_identity_group_vpn_templates (
        group_id bigint PRIMARY KEY REFERENCES zradius_identity_groups(id) ON DELETE CASCADE,
        nas_id bigint NOT NULL REFERENCES nas(id) ON DELETE RESTRICT,
        profile_id bigint NOT NULL REFERENCES zradius_ppp_profiles(id) ON DELETE RESTRICT,
        address_space_id bigint REFERENCES zradius_vpn_address_spaces(id) ON DELETE RESTRICT
    )""")

def downgrade():
    op.execute("DROP TABLE zradius_identity_group_vpn_templates")
