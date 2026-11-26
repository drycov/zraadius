"""Provision restricted application roles after migrations using the legacy DB owner."""
import os
import psycopg
from psycopg import sql

roles={
    "zradius_api":os.environ["ZRADIUS_API_DB_PASSWORD"],
    "zradius_runtime":os.environ["ZRADIUS_RUNTIME_DB_PASSWORD"],
}
if any(len(p)<32 or p.startswith("replace_with") for p in roles.values()) or len(set(roles.values())|{os.environ["PGPASSWORD"]})!=3:
    raise RuntimeError("Use distinct random database passwords, at least 32 characters")
api_write="""radcheck radreply radgroupcheck radgroupreply radusergroup zradius_groups zradius_audit
zradius_disabled_users nas zradius_coa_requests zradius_nas_services zradius_group_services
zradius_device_roles zradius_ipoe_bindings zradius_ip_pools zradius_ip_allocations
zradius_radius_pool_exports zradius_radius_pool_addresses zradius_radius_pool_groups
radippool zradius_radius_pool_active zradius_hotspot_vouchers zradius_device_users
zradius_device_grants zradius_eap_users zradius_eap_grants zradius_pki_certificates
zradius_pki_grants zradius_proxy_realms zradius_proxy_grants zradius_admin_users zradius_admin_sessions zradius_login_limits zradius_service_accounts zradius_service_tokens zradius_device_role_catalog zradius_device_user_groups zradius_device_user_members zradius_device_group_grants zradius_nas_groups zradius_nas_group_members zradius_nas_group_networks zradius_device_nas_group_grants zradius_device_reply_profiles zradius_ppp_profiles zradius_l2tp_users""".split()
api_read="alembic_version radacct radpostauth nasreload zradius_services zradius_device_auth_log zradius_device_effective_grants zradius_nas_group_effective_members".split()
runtime_read="""radcheck radreply radgroupcheck radgroupreply radusergroup nas zradius_nas_services
zradius_ipoe_bindings zradius_hotspot_vouchers zradius_device_users zradius_device_grants
zradius_eap_users zradius_eap_grants zradius_pki_certificates zradius_pki_grants
zradius_proxy_realms zradius_proxy_grants zradius_radius_pool_groups
zradius_radius_pool_active zradius_ip_pools zradius_device_user_members zradius_device_group_grants zradius_device_effective_grants zradius_nas_group_members zradius_nas_group_networks zradius_device_nas_group_grants zradius_nas_group_effective_members zradius_ppp_profiles zradius_l2tp_users""".split()
runtime_write="radacct radpostauth nasreload radippool zradius_device_auth_log".split()
def grant(conn,role,privileges,tables):
    for table in tables:
        conn.execute(sql.SQL("GRANT "+privileges+" ON TABLE public.{} TO {}").format(sql.Identifier(table),sql.Identifier(role)))
def main():
    with psycopg.connect(connect_timeout=5) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(7281192201)")
        # Refuse pre-existing roles with memberships or owned application objects.
        for role,password in roles.items():
            row=conn.execute("SELECT oid FROM pg_roles WHERE rolname=%s",(role,)).fetchone()
            ident=sql.Identifier(role)
            if row:
                if conn.execute("SELECT 1 FROM pg_auth_members WHERE member=%s OR roleid=%s",(row[0],row[0])).fetchone():
                    raise RuntimeError("Unexpected database role membership: "+role)
                if conn.execute("SELECT 1 FROM pg_class WHERE relowner=%s UNION ALL SELECT 1 FROM pg_namespace WHERE nspowner=%s UNION ALL SELECT 1 FROM pg_database WHERE datdba=%s",(row[0],row[0],row[0])).fetchone():
                    raise RuntimeError("Application role owns database objects: "+role)
            else:
                conn.execute(sql.SQL("CREATE ROLE {}").format(ident))
            conn.execute(sql.SQL("ALTER ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT PASSWORD {}").format(ident,sql.Literal(password)))
            conn.execute(sql.SQL("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {}").format(ident))
            conn.execute(sql.SQL("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM {}").format(ident))
            conn.execute(sql.SQL("REVOKE ALL ON SCHEMA public FROM {}").format(ident))
            conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(ident))
        conn.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        conn.execute("REVOKE ALL ON DATABASE radius FROM PUBLIC")
        for role in roles:
            conn.execute(sql.SQL("GRANT CONNECT ON DATABASE radius TO {}").format(sql.Identifier(role)))
        grant(conn,"zradius_api","SELECT, INSERT, UPDATE, DELETE",api_write)
        grant(conn,"zradius_api","SELECT",api_read)
        grant(conn,"zradius_runtime","SELECT",runtime_read)
        grant(conn,"zradius_runtime","SELECT, INSERT, UPDATE",runtime_write)
        # Shared legacy sequences are discovered from column defaults, not guessed.
        for role,tables in (("zradius_api",api_write),("zradius_runtime",runtime_write)):
            seqs=conn.execute("""SELECT DISTINCT ns.nspname,s.relname FROM pg_attrdef d
                JOIN pg_class t ON t.oid=d.adrelid JOIN pg_namespace tn ON tn.oid=t.relnamespace
                JOIN pg_depend dep ON dep.classid='pg_attrdef'::regclass AND dep.objid=d.oid AND dep.refclassid='pg_class'::regclass
                JOIN pg_class s ON s.oid=dep.refobjid AND s.relkind='S'
                JOIN pg_namespace ns ON ns.oid=s.relnamespace WHERE tn.nspname='public' AND t.relname=ANY(%s)""",(tables,)).fetchall()
            for schema,name in seqs:
                conn.execute(sql.SQL("GRANT USAGE, SELECT ON SEQUENCE {}.{} TO {}").format(sql.Identifier(schema),sql.Identifier(name),sql.Identifier(role)))
if __name__=="__main__":
    main()
