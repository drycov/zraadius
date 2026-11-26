"""Inventory of external RouterOS VPN pool ranges."""
from alembic import op
revision="0016_vpn_pools"
down_revision="0015_vpn_address_spaces"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_vpn_pools (
        id bigserial PRIMARY KEY,
        name varchar(64) NOT NULL CHECK(name ~ '^[A-Za-z0-9_.-]{1,64}$'),
        nas_id bigint NOT NULL REFERENCES nas(id),
        address_space_id bigint NOT NULL REFERENCES zradius_vpn_address_spaces(id),
        network cidr NOT NULL CHECK(family(network)=4),
        first_ip inet NOT NULL CHECK(family(first_ip)=4 AND masklen(first_ip)=32),
        last_ip inet NOT NULL CHECK(family(last_ip)=4 AND masklen(last_ip)=32),
        CHECK(first_ip <<= network AND last_ip <<= network AND first_ip<=last_ip),
        UNIQUE(nas_id,name)
    )""")
    op.execute("CREATE INDEX zradius_vpn_pool_space_idx ON zradius_vpn_pools(address_space_id)")
def downgrade():
    op.execute("DROP TABLE zradius_vpn_pools")
