# FreeRADIUS runtime

## Image

- Base: `debian:bookworm-slim`
- Packages: `freeradius`, `freeradius-postgresql`, `freeradius-utils`, `postgresql-client`, Python crypto helpers
- Entrypoint: `/usr/local/bin/zradius-entrypoint`
- Enabled site: `sites-enabled/zradius`
- SQL module: `mods-enabled/sql` with `client_table = "nas"`, `read_clients = no` by default

## Startup sequence (entrypoint)

1. Reset enabled sites/mods to known defaults
2. Validate feature flags booleans
3. Require `RADIUS_TEST_SECRET` (≥32 alphanumeric)
4. Write loopback `clients.conf` with that secret and `require_message_authenticator = yes`
5. Wait for schema (psql as `zradius_runtime`, up to 60×2s)
6. Optional: NAS client snapshot, SQL IP pool, EAP/TLS, proxy (flags)
7. `freeradius -C` then `exec freeradius -f -l stdout`

## Compose ports

```yaml
"${RADIUS_BIND_IP:-127.0.0.1}:1812:1812/udp"
"${RADIUS_BIND_IP:-127.0.0.1}:1813:1813/udp"
```

Healthcheck: `radclient` Access-Request that must yield **Access-Reject**.

## Smoke

```bash
docker compose exec radius freeradius -v
sh scripts/smoke-radius.sh
```

## Feature flags

| Flag | Default | Effect |
|------|---------|--------|
| `RADIUS_ENABLE_NAS` | false | Render registered NAS into clients include |
| `RADIUS_ENABLE_SQLIPPOOL` | false | Enable sqlippool mod + pool policy site |
| `RADIUS_ENABLE_EAP` | false | EAP mod + inner tunnel |
| `RADIUS_ENABLE_EAP_TLS` | false | Requires EAP |
| `RADIUS_ENABLE_PROXY` | false | Proxy realms from DB |

SQL dialect PostgreSQL; login `zradius_runtime`; password from `RADIUS_DB_PASSWORD`.
