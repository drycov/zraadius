"""Explicit VPN address spaces and static address uniqueness."""
from alembic import op
revision="0015_vpn_address_spaces"
down_revision="0014_vpn_groups"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_vpn_address_spaces (
        id bigserial PRIMARY KEY,
        name varchar(64) NOT NULL UNIQUE CHECK(name ~ '^[A-Za-z0-9_.-]{1,64}$'),
        description varchar(200) NOT NULL DEFAULT ''
    )""")
    op.execute("ALTER TABLE zradius_l2tp_users ADD COLUMN address_space_id bigint REFERENCES zradius_vpn_address_spaces(id)")
    op.execute("CREATE UNIQUE INDEX zradius_vpn_space_static_unique ON zradius_l2tp_users(address_space_id,static_ip) WHERE address_space_id IS NOT NULL AND static_ip IS NOT NULL")

def downgrade():
    op.execute("DROP INDEX zradius_vpn_space_static_unique")
    op.execute("ALTER TABLE zradius_l2tp_users DROP COLUMN address_space_id")
    op.execute("DROP TABLE zradius_vpn_address_spaces")
