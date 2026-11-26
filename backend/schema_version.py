"""Check the migration revision without making schema changes."""
from alembic.config import Config
from alembic.script import ScriptDirectory
from pathlib import Path

def expected_revision():
    config=Config(str(Path(__file__).with_name("alembic.ini")))
    return ScriptDirectory.from_config(config).get_current_head()

def require_schema(conn):
    rows=conn.execute("SELECT version_num FROM alembic_version").fetchall()
    if len(rows)!=1 or rows[0]["version_num"]!=expected_revision():
        raise RuntimeError("Database revision mismatch; run alembic upgrade head")
