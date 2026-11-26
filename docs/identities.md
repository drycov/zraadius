# Unified identities

Primary management model for subscribers lives under `/api/v1/identities*`. Legacy `/api/v1/users` still manipulates `radcheck` but refuses usernames that already exist as unified identities (`reserve_legacy_login`).

## Core operations

| Area | Examples |
|------|----------|
| CRUD / state | `GET/POST /identities`, metadata, bulk state, password |
| Services | Assign services per identity, list assignments |
| Groups | Identity groups, bindings, membership |
| Device | Device policy, effective grants |
| VPN / PPP | VPN policy, group VPN templates, apply template |
| PPPoE / Hotspot / EAP | Per-identity service documents |
| Console link | `PUT .../console` ties management login to identity |
| Sessions | RADIUS/web session listing and disconnect |

## Login namespace

Unique constraint `zradius_login_namespace` prevents colliding logins across identity domains; API maps violation to HTTP 409 when possible.

## Migration from legacy

- `GET /api/v1/identities/legacy-candidates`
- `POST /api/v1/identities/legacy-migrate`

Prefer migrating lab users into unified identities rather than growing pure `radcheck` usage.
