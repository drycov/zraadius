"""Device AAA group grants with fail-closed conflict resolution."""
from alembic import op
revision="0010_device_user_groups"
down_revision="0009_device_profiles"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_device_user_groups (
        id bigserial PRIMARY KEY,
        name varchar(64) NOT NULL UNIQUE CHECK(name ~ '^[A-Za-z0-9_.-]{1,64}$'),
        description varchar(200) NOT NULL DEFAULT ''
    )""")
    op.execute("""CREATE TABLE zradius_device_user_members (
        group_id bigint REFERENCES zradius_device_user_groups(id) ON DELETE CASCADE,
        user_id bigint REFERENCES zradius_device_users(id) ON DELETE CASCADE,
        PRIMARY KEY(group_id,user_id)
    )""")
    op.execute("CREATE INDEX zradius_device_members_user_idx ON zradius_device_user_members(user_id,group_id)")
    op.execute("""CREATE TABLE zradius_device_group_grants (
        group_id bigint REFERENCES zradius_device_user_groups(id) ON DELETE CASCADE,
        nas_id bigint REFERENCES nas(id) ON DELETE CASCADE,
        role text NOT NULL REFERENCES zradius_device_role_catalog(name),
        filter_id varchar(64) CHECK(filter_id ~ '^[A-Za-z0-9_.-]{1,64}$'),
        PRIMARY KEY(group_id,nas_id)
    )""")
    op.execute("""CREATE VIEW zradius_device_effective_grants WITH (security_invoker=true) AS
        WITH inherited AS (
            SELECT m.user_id,g.nas_id,min(g.role) AS role,min(g.filter_id) AS filter_id
            FROM zradius_device_user_members m JOIN zradius_device_group_grants g ON g.group_id=m.group_id
            GROUP BY m.user_id,g.nas_id
            HAVING count(DISTINCT (g.role,COALESCE(g.filter_id,'')))=1
        ), candidates AS (
            SELECT user_id,nas_id,role,filter_id,'direct'::text AS source FROM zradius_device_grants
            UNION ALL
            SELECT i.user_id,i.nas_id,i.role,i.filter_id,'group'::text
            FROM inherited i WHERE NOT EXISTS (
                SELECT 1 FROM zradius_device_grants d WHERE d.user_id=i.user_id AND d.nas_id=i.nas_id
            )
        )
        SELECT c.user_id,c.nas_id,c.role,c.filter_id,c.source
        FROM candidates c JOIN zradius_device_users u ON u.id=c.user_id AND u.enabled
        JOIN nas n ON n.id=c.nas_id AND n.type='mikrotik'
        JOIN zradius_nas_services s ON s.nas_id=c.nas_id AND s.service_code='device-aaa'
    """)

def downgrade():
    op.execute("DROP VIEW zradius_device_effective_grants")
    op.execute("DROP TABLE zradius_device_group_grants")
    op.execute("DROP TABLE zradius_device_user_members")
    op.execute("DROP TABLE zradius_device_user_groups")
