"""Smoke assertions executed with the actual API connection in CI."""
import psycopg
with psycopg.connect() as conn:
    role,superuser,create_role,create_db=conn.execute("SELECT current_user,rolsuper,rolcreaterole,rolcreatedb FROM pg_roles WHERE rolname=current_user").fetchone()
    assert role=="zradius_api" and not any((superuser,create_role,create_db))
    assert not conn.execute("SELECT has_schema_privilege(current_user,'public','CREATE')").fetchone()[0]
    assert not conn.execute("SELECT has_table_privilege(current_user,'radacct','DELETE')").fetchone()[0]
    assert conn.execute("SELECT has_table_privilege(current_user,'radcheck','INSERT')").fetchone()[0]
print("API role checks passed")
