"""Transactional PostgreSQL migrations with a single-writer advisory lock."""
import os
from alembic import context
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.pool import NullPool

url=URL.create("postgresql+psycopg",username=os.environ["PGUSER"],
    password=os.environ["PGPASSWORD"],host=os.environ["PGHOST"],
    port=int(os.getenv("PGPORT","5432")),database=os.environ["PGDATABASE"])
if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not supported")
engine=create_engine(url,poolclass=NullPool,connect_args={"connect_timeout":5})
with engine.connect() as connection:
    with connection.begin():
        connection.execute(text("SET LOCAL lock_timeout = '30s'"))
        connection.execute(text("SELECT pg_advisory_xact_lock(7281192201)"))
        context.configure(connection=connection,transactional_ddl=True)
        with context.begin_transaction():
            context.run_migrations()
engine.dispose()
