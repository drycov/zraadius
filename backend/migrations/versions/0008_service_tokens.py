"""Scoped, expiring machine API credentials."""
from alembic import op
revision="0008_service_tokens"
down_revision="0007_accounting_indexes"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""CREATE TABLE zradius_service_accounts (
        id bigserial PRIMARY KEY,
        name varchar(64) NOT NULL UNIQUE,
        enabled boolean NOT NULL DEFAULT true,
        created_at timestamptz NOT NULL DEFAULT now()
    )""")
    op.execute("""CREATE TABLE zradius_service_tokens (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        account_id bigint NOT NULL REFERENCES zradius_service_accounts(id),
        label varchar(64) NOT NULL,
        token_hash char(64) NOT NULL UNIQUE,
        scopes text[] NOT NULL CHECK (cardinality(scopes)>0),
        created_at timestamptz NOT NULL DEFAULT now(),
        expires_at timestamptz NOT NULL CHECK (expires_at>created_at),
        revoked_at timestamptz
    )""")
    op.execute("CREATE INDEX zradius_service_tokens_account ON zradius_service_tokens(account_id)")

def downgrade():
    raise RuntimeError("Refusing to discard service credential history")
