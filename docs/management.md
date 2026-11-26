# Management API surface (practical)

Swagger: service `/docs` when the API is reachable.

## Always-on utilities

- `GET /health/live` — process up
- `GET /health/ready` — DB schema revision matches code head
- `GET /api/v1/dashboard` — console counters
- `GET /api/v1/dictionaries` — curated attribute starter catalog
- `GET /api/v1/audit` — recent audit rows

## Legacy RADIUS users / groups

- Users: list/create, password, enable/disable (`Auth-Type := Reject` + `zradius_disabled_users`), delete (accounting preserved)
- Groups: create, MikroTik profile, network policy, device role, service bindings, radius pool binding
- Blocking does **not** automatically disconnect live sessions unless you call disconnect/CoA

## NAS inventory

- Register address, name, vendor, secret (sealed), description
- Service assignments per NAS
- Not live FreeRADIUS client until `RADIUS_ENABLE_NAS=true` and radius restart

## Accounting

- `GET /api/v1/accounting` with filters
- CoA history `GET /api/v1/coa` when used

## Domain modules

IPoE, IPAM, hotspot vouchers, device-AAA, EAP, PKI, proxy, PPP/L2TP, unified identities — see dedicated docs.

## Safety defaults

- Secrets never returned in API responses
- CoA gated by env allowlist
- RADIUS bind defaults to localhost
