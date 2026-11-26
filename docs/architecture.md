# Architecture

## Purpose

Single-tenant **management plane** (API + React console) and a **FreeRADIUS** process that authenticates and accounts against PostgreSQL. Management is not on the AAA request path: FreeRADIUS talks to the database directly as `zradius_runtime`.

## Runtime topology

```
MikroTik / lab client
        │  UDP 1812/1813 (default bind 127.0.0.1)
        ▼
   radius container  ──SQL──►  postgres (role zradius_runtime)
        ▲
        │ schema wait + optional client snapshot at start
   migrate (once)  ──owner──►  postgres (role radius)
        │
   api container   ──SQL──►  postgres (role zradius_api)
        ▲
   web (nginx)  proxy / static UI  →  browser on 127.0.0.1:8080
```

Compose dependencies:

1. `postgres` healthy (`pg_isready`)
2. `migrate` **completed successfully**
3. `radius` and `api` start
4. `web` depends on `api`

Schema revision is enforced at API startup via `require_schema()` (exact `alembic_version` head). Radius waits up to ~120s for required tables and grants as `zradius_runtime`.

## Layers

| Layer | Code | Notes |
|-------|------|--------|
| UI | `frontend/` | Hash routes; design-kit components; token only in memory |
| Management API | `backend/main.py` + modules | FastAPI, psycopg, Argon2 sessions |
| DB roles | `provision_roles.py` | Explicit table grants, no superuser app roles |
| Migrations | `backend/migrations/versions/` | Baseline FreeRADIUS-compatible tables + ZRADIUS extensions |
| RADIUS | `freeradius/` | Packaged FR 3.x, site `zradius`, mod `sql` |
| Crypto | `secret_crypto.py` | AES-GCM envelopes for NAS/proxy secrets |

## Identity domains (do not mix)

1. **Management IAM** — `zradius_admin_users` / sessions; console operators (`admin` / `operator` / `auditor`). Bootstrap via `bootstrap_admin.py`.
2. **Legacy RADIUS rows** — `radcheck` / `radreply` / `radusergroup` (Cleartext-Password for lab PAP). API still exposes `/api/v1/users` but unified identity is preferred.
3. **Unified identities** — `zradius_identities` and related service bindings (PPP, hotspot, device, EAP metadata, console link).
4. **Machine service tokens** — prefix `zrs_`, scoped endpoint allowlist (`service_tokens.py`).

## AuthZ model (management)

- Bearer session token (opaque, SHA-256 digest stored, ~8h TTL) or optional legacy `ADMIN_TOKEN`, or service token.
- `admin`: all routes.
- `operator` / `auditor`: coarse allowlist in `iam.permitted` — mostly GET on known resources; operator may CoA disconnect/rate.
- Unknown paths deny non-admin.

## Explicit non-goals (current alpha)

- Multi-tenant SaaS
- Automatic FreeRADIUS config reload without container restart
- Production RBAC object scope
- Internet-facing RADIUS without additional hardening
- Claiming full EAP/proxy/IPoE production readiness (feature flags and overlays exist; treat as experimental)
