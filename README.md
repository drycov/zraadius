# ZRADIUS

Development **alpha** management plane and FreeRADIUS runtime for MikroTik-oriented AAA (PPP/L2TP, optional IPoE, hotspot, device AAA, IPAM). Not production-ready.

## Stack

| Service | Role |
|---------|------|
| `postgres` | PostgreSQL 16, database `radius`, owner role `radius` |
| `migrate` | One-shot: `alembic upgrade head` + `provision_roles.py` |
| `radius` | FreeRADIUS 3.x (Debian Bookworm packages), SQL via `zradius_runtime` |
| `api` | FastAPI management API as `zradius_api` |
| `web` | React + Vite console behind nginx on `127.0.0.1:8080` |

## Quick start

```bash
cp .env.example .env
# Fill every replace_with_* value with independent secrets (see below).

docker compose up --build -d
docker compose exec api python bootstrap_admin.py
# Open http://localhost:8080
```

Day-2 procedures (migrate repair, flags, backup): [docs/operations.md](docs/operations.md).  
Full index: [docs/README.md](docs/README.md).

API OpenAPI: `/docs` on the API service (proxied through web depending on nginx config).

## Required secrets (`.env`)

Generate independently (`openssl rand -hex 32` unless noted):

| Variable | Purpose |
|----------|---------|
| `POSTGRES_PASSWORD` | PostgreSQL owner `radius` |
| `ZRADIUS_API_DB_PASSWORD` | Role `zradius_api` (≥32 chars, unique) |
| `ZRADIUS_RUNTIME_DB_PASSWORD` | Role `zradius_runtime` (≥32 chars, unique) |
| `ZRADIUS_SECRET_KEY` | AES-256 key for sealed NAS/proxy secrets (`openssl rand -hex 32`). **Never regenerate** after data exists |
| `RADIUS_TEST_SECRET` | Loopback FreeRADIUS client secret: **≥32 alphanumeric** only |
| `ADMIN_TOKEN` | Optional legacy bearer; ignored unless `ZRADIUS_LEGACY_TOKEN_ENABLED=true` |

Optional flags (default safe):

```env
RADIUS_ENABLE_NAS=false
RADIUS_BIND_IP=127.0.0.1
RADIUS_ENABLE_SQLIPPOOL=false
COA_ENABLED=false
COA_ALLOWED_NETWORKS=
ZRADIUS_LEGACY_TOKEN_ENABLED=false
```

Live experimental overlays: `compose.eap.yaml`, `compose.eap-tls.yaml`, `compose.proxy.yaml`.  
Empty deprecated stubs: `compose.hotspot.yaml`, `compose.ipoe.yaml`, `compose.device-aaa.yaml` (those features use unified 1812/1813).

## First administrator

```bash
docker compose exec api python bootstrap_admin.py
```

- Username: `[a-zA-Z0-9_.-]{1,64}`
- Password: **16–128** characters (Argon2id)
- Fails if an enabled `admin` already exists

Login: `POST /api/v1/iam/login` (password; OTP when MFA is enabled).

## Documentation map

| Doc | Content |
|------|---------|
| [docs/README.md](docs/README.md) | Index |
| [docs/architecture.md](docs/architecture.md) | Components, data flow, boundaries |
| [docs/iam.md](docs/iam.md) | Management users, roles, sessions |
| [docs/mfa.md](docs/mfa.md) | TOTP / recovery codes |
| [docs/secrets.md](docs/secrets.md) | Secret key, sealing |
| [docs/db-roles.md](docs/db-roles.md) | DB roles and grants |
| [docs/radius.md](docs/radius.md) | FreeRADIUS container |
| [docs/unified-radius.md](docs/unified-radius.md) | Single 1812/1813 endpoint |
| [docs/nas-runtime.md](docs/nas-runtime.md) | External NAS and CoA |
| [docs/services.md](docs/services.md) | Service catalog vs runtime |
| [docs/identities.md](docs/identities.md) | Unified identities |
| [docs/management.md](docs/management.md) | Legacy users/groups/NAS |
| [docs/ppp.md](docs/ppp.md) | L2TP/PPP |
| [docs/ipam.md](docs/ipam.md) | IP pools |
| [docs/device-aaa.md](docs/device-aaa.md) | Device AAA |
| [docs/hotspot.md](docs/hotspot.md) | Vouchers |
| [docs/ipoe.md](docs/ipoe.md) | MAC bindings |
| [docs/eap.md](docs/eap.md) | PEAP overlay |
| [docs/eap-tls.md](docs/eap-tls.md) | EAP-TLS overlay |
| [docs/pki.md](docs/pki.md) | Public cert inventory |
| [docs/proxy.md](docs/proxy.md) | Outbound proxy |
| [docs/operations.md](docs/operations.md) | Operations runbook |

## Status

Alpha. Validate Docker startup, migrate, RADIUS Access-Reject healthcheck, and lab AAA before any real traffic. Do not expose UDP 1812/1813 or the UI to untrusted networks without TLS and firewalling.
