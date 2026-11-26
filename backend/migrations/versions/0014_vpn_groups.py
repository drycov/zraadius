"""VPN group profile inheritance."""
from alembic import op
revision="0014_vpn_groups"
down_revision="0013_ppp_vpn"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_vpn_groups (
        id bigserial PRIMARY KEY,
        name varchar(64) NOT NULL UNIQUE CHECK(name ~ '^[A-Za-z0-9_.-]{1,64}$'),
        description varchar(200) NOT NULL DEFAULT '',
        profile_id bigint NOT NULL REFERENCES zradius_ppp_profiles(id)
    )""")
    op.execute("ALTER TABLE zradius_l2tp_users ADD COLUMN group_id bigint REFERENCES zradius_vpn_groups(id)")
    op.execute("ALTER TABLE zradius_l2tp_users ALTER COLUMN profile_id DROP NOT NULL")
    op.execute("ALTER TABLE zradius_l2tp_users ADD CHECK(profile_id IS NOT NULL OR group_id IS NOT NULL)")
    op.execute("CREATE INDEX zradius_l2tp_group_idx ON zradius_l2tp_users(group_id)")
    op.execute("""CREATE VIEW zradius_l2tp_effective_profiles WITH (security_invoker=true) AS
        SELECT u.id AS user_id,p.id AS profile_id,p.name,p.pool,p.interim_seconds
        FROM zradius_l2tp_users u LEFT JOIN zradius_vpn_groups g ON g.id=u.group_id
        JOIN zradius_ppp_profiles p ON p.id=COALESCE(u.profile_id,g.profile_id)""")

def downgrade():
    raise RuntimeError("Refusing to discard inherited VPN profiles")
