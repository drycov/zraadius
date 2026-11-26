# Operations runbook

## Healthy first boot

```bash
cp .env.example .env
# fill all secrets — distinct ≥32 hex for DB passwords and ZRADIUS_SECRET_KEY
# RADIUS_TEST_SECRET: ≥32 alphanumeric only

docker compose up --build -d
docker compose ps -a
docker compose logs migrate --tail=50    # must exit 0
docker compose logs radius --tail=80
docker compose logs api --tail=40

docker compose exec api python bootstrap_admin.py
# UI http://127.0.0.1:8080
```

Never use `docker compose down -v` on a deployment you care about — that deletes `pgdata`.

## Schema / roles repair

Symptoms: API `Name or service not known`, radius `Database schema readiness timeout`, revision mismatch on `/health/ready`.

```bash
docker compose stop api radius
docker compose run --rm migrate          # must print success / exit 0
docker compose up -d --force-recreate api radius
```

Keep **unchanged**:

- `ZRADIUS_SECRET_KEY` (sealed NAS/proxy secrets)
- `POSTGRES_PASSWORD` on an **existing** volume does not re-init role password inside PG; changing it only in `.env` without `ALTER ROLE` will desync

Inspect runtime DB role:

```bash
docker compose run --rm --no-deps --entrypoint sh radius -c \
  'PGPASSWORD="$RADIUS_DB_PASSWORD" psql -X -w -h postgres -U zradius_runtime -d radius -c "SELECT current_user, current_database()"'
```

## Stale FreeRADIUS image

```bash
docker compose build --no-cache radius
docker compose up -d --force-recreate radius
```

Do **not** bind-mount over `/etc/freeradius/3.0` or override entrypoint.

## After NAS or secret changes

With `RADIUS_ENABLE_NAS=true`, clients are rendered at **container start** only:

```bash
docker compose up -d --force-recreate radius
```

## Feature flags cheatsheet

| Goal | Action |
|------|--------|
| External NAS | `RADIUS_ENABLE_NAS=true`, safe `RADIUS_BIND_IP`, firewall, recreate radius |
| CoA | `COA_ENABLED=true`, `COA_ALLOWED_NETWORKS=cidr,...`, NAS incoming 3799 |
| SQL IP pool | `RADIUS_ENABLE_SQLIPPOOL=true`, recreate radius |
| PEAP | `-f compose.eap.yaml`, PKI files in `RADIUS_PKI_DIR` |
| EAP-TLS | eap + eap-tls overlays |
| Proxy | `-f compose.proxy.yaml` |

## Backups

1. `pg_dump` (or volume snapshot) of database `radius`
2. Offline copy of `ZRADIUS_SECRET_KEY` **separate** from DB dumps
3. Host PKI private keys (`server.key`) if EAP used
4. `.env` without committing it to git

Restore order: restore volume/DB → same secret key in `.env` → `migrate` → recreate api/radius.

## Frontend build failure

`web` image runs `tsc --noEmit && vite build`. Type errors fail the whole `compose up --build`. Fix TypeScript or build selectively:

```bash
docker compose up -d --build postgres migrate api radius
docker compose build web
```

## Smoke

```bash
sh scripts/smoke-radius.sh
```
