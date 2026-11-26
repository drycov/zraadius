# Device AAA

Routes `/api/v1/device-aaa/*`. UI: `#/device`. RADIUS realm: `device-aaa`.

## Purpose

Separate equipment accounts (not subscriber PPP, not management IAM): roles, users, grants on NAS / NAS-groups, reply profiles, auth log.

## API (summary)

- Roles, users (state, rotate-password)
- User grants and effective grants
- Groups, members, grants, nas-group-grants
- Reply profiles
- Auth log

Runtime writes `zradius_device_auth_log` as `zradius_runtime`.

Requires registered NAS + realm when external clients are enabled.
