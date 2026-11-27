"""Persist before/after snapshots without credentials."""
from alembic import op
revision="0039_policy_history"
down_revision="0038_profile_overrides"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_policy_history (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        identity_id bigint NOT NULL,
        username text NOT NULL,
        actor text NOT NULL,
        operation text NOT NULL CHECK(operation IN ('apply','rollback')),
        revision text NOT NULL CHECK(revision ~ '^[a-f0-9]{64}$'),
        before_state jsonb NOT NULL CHECK(jsonb_typeof(before_state)='object'),
        after_state jsonb NOT NULL CHECK(jsonb_typeof(after_state)='object'),
        rollback_of bigint UNIQUE REFERENCES zradius_policy_history(id),
        created_at timestamptz NOT NULL DEFAULT now())""")
    op.execute("CREATE INDEX ix_policy_history_identity ON zradius_policy_history(identity_id,id DESC)")

def downgrade():
    op.execute("DROP TABLE zradius_policy_history")
