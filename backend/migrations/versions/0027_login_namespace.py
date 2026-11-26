"""Enforce unified versus independent login ownership at the database boundary."""
from alembic import op

revision="0027_login_namespace"
down_revision="0026_session_services"
branch_labels=None
depends_on=None

LINKED=("zradius_device_users","zradius_l2tp_users","zradius_admin_users")
LEGACY=("radcheck","zradius_eap_users","zradius_hotspot_vouchers")
TABLES=LINKED+LEGACY

def upgrade():
    # Prevent concurrent namespace writes during validation and installation.
    op.execute("LOCK TABLE public.zradius_identities, "+", ".join("public."+t for t in TABLES)+" IN SHARE ROW EXCLUSIVE MODE")
    legacy=" UNION ALL ".join(
        "SELECT username FROM public."+t+(" WHERE identity_id IS NULL" if t in LINKED else "")
        for t in TABLES
    )
    op.execute(f"""DO $$ BEGIN
        IF EXISTS(SELECT 1 FROM public.zradius_identities i JOIN ({legacy}) l USING(username))
           OR EXISTS(SELECT 1 FROM public.zradius_identities WHERE username ~ '^hs-[a-f0-9]{{20}}$')
        THEN RAISE EXCEPTION 'Existing unified login namespace conflict; resolve before migration';
        END IF;
    END $$""")
    op.execute(f"""CREATE FUNCTION public.zradius_guard_login_namespace() RETURNS trigger
    LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
    DECLARE linked_id bigint;
    BEGIN
        IF TG_OP='UPDATE' THEN
            IF NEW.username IS NOT DISTINCT FROM OLD.username AND
               (to_jsonb(NEW)->>'identity_id') IS NOT DISTINCT FROM (to_jsonb(OLD)->>'identity_id')
            THEN RETURN NEW; END IF;
        END IF;
        -- The advisory lock and subsequent volatile queries require fresh snapshots.
        IF current_setting('transaction_isolation') <> 'read committed' THEN
            RAISE EXCEPTION 'Login namespace changes require READ COMMITTED' USING ERRCODE='25000';
        END IF;
        PERFORM pg_advisory_xact_lock(hashtext(NEW.username));
        IF TG_TABLE_NAME='zradius_identities' THEN
            IF NEW.username ~ '^hs-[a-f0-9]{{20}}$' OR EXISTS(
                SELECT 1 FROM ({legacy}) l WHERE l.username=NEW.username
            ) THEN
                RAISE EXCEPTION 'Login namespace conflict' USING ERRCODE='23505', CONSTRAINT='zradius_login_namespace';
            END IF;
        ELSE
            linked_id := (to_jsonb(NEW)->>'identity_id')::bigint;
            IF linked_id IS NULL AND EXISTS(
                SELECT 1 FROM public.zradius_identities WHERE username=NEW.username
            ) THEN
                RAISE EXCEPTION 'Login namespace conflict' USING ERRCODE='23505', CONSTRAINT='zradius_login_namespace';
            END IF;
        END IF;
        RETURN NEW;
    END $$""")
    for table in ("zradius_identities",)+TABLES:
        columns="username,identity_id" if table in LINKED else "username"
        op.execute(f"CREATE TRIGGER zradius_login_namespace BEFORE INSERT OR UPDATE OF {columns} ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.zradius_guard_login_namespace()")

def downgrade():
    for table in ("zradius_identities",)+TABLES:
        op.execute(f"DROP TRIGGER zradius_login_namespace ON public.{table}")
    op.execute("DROP FUNCTION public.zradius_guard_login_namespace()")
