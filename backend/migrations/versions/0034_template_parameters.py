"""Optional reusable service parameters for account creation templates."""
from alembic import op
revision="0034_template_parameters"
down_revision="0033_access_templates"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""ALTER TABLE zradius_access_templates ADD COLUMN parameters jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK(jsonb_typeof(parameters)='object')""")

def downgrade():
    op.execute("ALTER TABLE zradius_access_templates DROP COLUMN parameters")
