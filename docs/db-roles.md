# Database roles

## Roles

| Role | Who uses it | Privileges (intent) |
|------|-------------|---------------------|
| `radius` | Postgres init + `migrate` only | Owner / migration superuser of the cluster role |
| `zradius_api` | API container (`PGUSER`) | SELECT/INSERT/UPDATE/DELETE on management and config tables; SELECT on accounting-ish tables; **no** schema CREATE |
| `zradius_runtime` | FreeRADIUS SQL module | SELECT on auth/config tables; INSERT/UPDATE on accounting, postauth, leases, device auth log |

Passwords must be **distinct**, random, length ≥32. `provision_roles.py` recreates login attributes and **refreshes grants** on every migrate run. Sequence grants are discovered from column defaults, not hard-coded names.

## Migrate command

```text
alembic upgrade head && python provision_roles.py
```

API and radius both require migrate to have completed successfully in Compose.

## Verification helpers

- `check_db_roles.py` — asserts current user is `zradius_api` without superuser/CREATE and without DELETE on `radacct`
- API `GET /health/ready` runs `require_schema`

## Password change

Update `.env`, re-run migrate (role `ALTER … PASSWORD`), recreate api/radius containers. Existing sealed data is independent of DB role passwords.

## Limits

- Owner remains a powerful PostgreSQL role; full migrate as non-superuser is future work
- No comprehensive audit of unrelated `PUBLIC` grants — use a dedicated database
- No automatic future-table grants; new tables need grant list updates in `provision_roles.py`
