# EAP (experimental)

PEAP-MSCHAPv2-oriented path in FreeRADIUS. **Default base stack: EAP off.**

## Enable (lab only)

```bash
# server.key, server.pem (chain), ca.pem — private dir, never commit keys
docker compose -f compose.yaml -f compose.eap.yaml up -d --force-recreate radius
```

`compose.eap.yaml` sets `RADIUS_ENABLE_EAP=true` and mounts `${RADIUS_PKI_DIR:-./pki}:/run/zradius-pki:ro`.

Entrypoint requires readable `/run/zradius-pki/{server.key,server.pem,ca.pem}`, EAP tables, links EAP mod + inner-tunnel, injects Auth-Type EAP, then `freeradius -C`.

## Management API

```
GET  /api/v1/eap/users
PUT  /api/v1/eap/users/{username}
PUT  /api/v1/eap/users/{username}/state
PUT  /api/v1/eap/users/{username}/grants/{nas_id}
DELETE /api/v1/eap/users/{username}/grants/{nas_id}
```

Also: `GET/PUT /api/v1/identities/{identity_id}/eap/{service}`.

PEAP credentials are NT-hash oriented, not Argon2 management hashes.

## Disable

Remove overlay / set flag false, recreate radius. Entrypoint clears EAP links when disabled.

Experimental — isolated lab only.
