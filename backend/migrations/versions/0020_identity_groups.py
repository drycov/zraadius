"""Global identity groups with live Device AAA inheritance."""
from alembic import op
revision="0020_identity_groups"
down_revision="0019_identity_credentials"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_identity_groups (
        id bigserial PRIMARY KEY,
        name varchar(64) NOT NULL UNIQUE CHECK(name ~ '^[A-Za-z0-9_.-]{1,64}$'),
        description varchar(200) NOT NULL DEFAULT ''
    )""")
    op.execute("""CREATE TABLE zradius_identity_group_members (
        group_id bigint NOT NULL REFERENCES zradius_identity_groups(id) ON DELETE CASCADE,
        identity_id bigint NOT NULL REFERENCES zradius_identities(id) ON DELETE CASCADE,
        PRIMARY KEY(group_id,identity_id)
    )""")
    op.execute("CREATE INDEX ON zradius_identity_group_members(identity_id)")
    op.execute("""CREATE TABLE zradius_identity_group_device_bindings (
        group_id bigint NOT NULL REFERENCES zradius_identity_groups(id) ON DELETE CASCADE,
        device_group_id bigint NOT NULL REFERENCES zradius_device_user_groups(id) ON DELETE RESTRICT,
        PRIMARY KEY(group_id,device_group_id)
    )""")
    op.execute("""CREATE OR REPLACE VIEW zradius_device_effective_grants WITH (security_invoker=true) AS
        WITH memberships AS (
            SELECT user_id,group_id FROM zradius_device_user_members
            UNION
            SELECT u.id,b.device_group_id FROM zradius_identity_group_members m
            JOIN zradius_identity_group_device_bindings b ON b.group_id=m.group_id
            JOIN zradius_device_users u ON u.identity_id=m.identity_id
        ), group_candidates AS (
            SELECT m.user_id,g.nas_id,g.role,g.filter_id
            FROM memberships m JOIN zradius_device_group_grants g ON g.group_id=m.group_id
            UNION ALL
            SELECT m.user_id,n.nas_id,g.role,g.filter_id
            FROM memberships m JOIN zradius_device_nas_group_grants g ON g.group_id=m.group_id
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
    op.execute("DROP TABLE zradius_identity_group_device_bindings")
    op.execute("DROP TABLE zradius_identity_group_members")
    op.execute("DROP TABLE zradius_identity_groups")
