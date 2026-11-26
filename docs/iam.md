# Management IAM

Management accounts are **independent** of RADIUS subscribers, device AAA users, and EAP identities.

## Password hashing

- Argon2id via `argon2-cffi`: `time_cost=3`, `memory_cost=65536` (64 MiB), `parallelism=2`
- Password length enforced: **16–128** characters (`iam.hash_password`)

## Bootstrap

```bash
docker compose exec api python bootstrap_admin.py
```

Interactive only (no CLI password args). Creates one enabled user with `role='admin'`. Refuses if an enabled admin already exists.

## Login

`POST /api/v1/iam/login`

- Body: `username`, `password`, optional `otp` when MFA is on
- Rate limits in `zradius_login_limits`: global ~100 / 5 min, per username ~10 / 5 min → HTTP 429
- On success: opaque bearer token; digest stored in `zradius_admin_sessions` with expiry
- Browser keeps token in memory only

## Roles

| Role | Access |
|------|--------|
| `admin` | Full API |
| `operator` | Read allowlisted resources + session disconnect/rate |
| `auditor` | Read allowlisted resources only |

Allowlist resources (GET): `identities`, `dashboard`, `users`, `groups`, `nas`, `accounting`, `coa`, `services`, `dictionaries`, `audit`, `ipoe`, `ipam`, `hotspot`, `device-aaa`, `ppp`, `eap`, `pki`, `proxy`.

Coarse path-based authorization, not object-scoped RBAC.

## Legacy token

```env
ZRADIUS_LEGACY_TOKEN_ENABLED=true
ADMIN_TOKEN=<≥32 random characters, not a placeholder>
```

When enabled, Bearer equal to `ADMIN_TOKEN` authenticates as `legacy-token` with role `admin`. **Disabled by default.** Bypasses personal MFA.

## Service tokens

Prefix `zrs_`. Scoped endpoint allowlist in `service_tokens.py`.

## UI

- Route `#/iam` — administrators (admin role only in nav)
- Route `#/account` — current user, password, MFA panel
