"""Freeze the existing development schema without dropping user data."""
from pathlib import Path
from alembic import op
revision="0001_baseline"
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    # Use the driver directly to preserve PostgreSQL dollar-quoted functions
    # and avoid SQLAlchemy interpreting SQL strings as bind parameters.
    sql=Path(__file__).with_name("0001_baseline.sql").read_text(encoding="utf-8")
    op.get_bind().connection.driver_connection.execute(sql)

def downgrade():
    raise RuntimeError("Baseline downgrade is intentionally unsupported; restore a verified backup")
