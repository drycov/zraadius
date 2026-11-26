"""NAS groups and CIDR selectors for registered clients only."""
from alembic import op
revision="0011_nas_groups"
down_revision="0010_device_user_groups"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_nas_groups (
        id bigserial PRIMARY KEY,
        name varchar(64) NOT NULL UNIQUE CHECK(name ~ '^[A-Za-z0-9_.-]{1,64}$'),
        description varchar(200) NOT NULL DEFAULT ''
    )""")
    op.execute("""CREATE TABLE zradius_nas_group_members (
        group_id bigint REFERENCES zradius_nas_groups(id) ON DELETE CASCADE,
        nas_id bigint REFERENCES nas(id) ON DELETE CASCADE,
        PRIMARY KEY(group_id,nas_id)
    )""")
    op.execute("""CREATE TABLE zradius_nas_group_networks (
        group_id bigint REFERENCES zradius_nas_groups(id) ON DELETE CASCADE,
        network cidr NOT NULL CHECK(masklen(network)>0),
        PRIMARY KEY(group_id,network)
    )""")
    op.execute("""CREATE TABLE zradius_device_nas_group_grants (
        group_id bigint REFERENCES zradius_device_user_groups(id) ON DELETE CASCADE,
        nas_group_id bigint REFERENCES zradius_nas_groups(id) ON DELETE CASCADE,
        role text NOT NULL REFERENCES zradius_device_role_catalog(name),
        filter_id varchar(64) CHECK(filter_id ~ '^[A-Za-z0-9_.-]{1,64}$'),
        PRIMARY KEY(group_id,nas_group_id)
    )""")
    op.execute("""CREATE VIEW zradius_nas_group_effective_members WITH (security_invoker=true) AS
        SELECT group_id,nas_id FROM zradius_nas_group_members
        UNION
        SELECT g.group_id,n.id FROM zradius_nas_group_networks g JOIN nas n
        ON CASE WHEN pg_input_is_valid(n.nasname,'inet') THEN n.nasname::inet <<= g.network ELSE false END
    """)
    op.execute("""CREATE OR REPLACE VIEW zradius_device_effective_grants WITH (security_invoker=true) AS
        WITH group_candidates AS (
            SELECT m.user_id,g.nas_id,g.role,g.filter_id
            FROM zradius_device_user_members m JOIN zradius_device_group_grants g ON g.group_id=m.group_id
            UNION ALL
            SELECT m.user_id,n.nas_id,g.role,g.filter_id
            FROM zradius_device_user_members m JOIN zradius_device_nas_group_grants g ON g.group_id=m.group_id
            JOIN zradius_nas_group_effective_members n ON n.group_id=g.nas_group_id
        ), inherited AS (
            SELECT user_id,nas_id,min(role) AS role,min(filter_id) AS filter_id
            FROM group_candidates GROUP BY user_id,nas_id
            HAVING count(DISTINCT (role,COALESCE(filter_id,'')))=1
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
    op.execute("""CREATE OR REPLACE VIEW zradius_device_effective_grants WITH (security_invoker=true) AS
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
    op.execute("DROP VIEW zradius_nas_group_effective_members")
    op.execute("DROP TABLE zradius_device_nas_group_grants")
    op.execute("DROP TABLE zradius_nas_group_networks")
    op.execute("DROP TABLE zradius_nas_group_members")
    op.execute("DROP TABLE zradius_nas_groups")
