# RADIUS proxy (experimental)

Outbound proxy realms. **Default: off.**

```bash
docker compose -f compose.yaml -f compose.proxy.yaml up -d --force-recreate radius
```

Sets `RADIUS_ENABLE_PROXY=true`. Entrypoint renders home servers into `proxy.conf` via `render_secrets.py`, injects proxy policy fragments.

## API

```
GET/POST  /api/v1/proxy/realms
PUT       /api/v1/proxy/realms/{realm_id}/state
GET/PUT/DELETE grants on NAS
```

Firewall egress to known upstream only; avoid hairpin. Restart radius after realm/secret changes. No RadSec in this alpha path. Experimental.
