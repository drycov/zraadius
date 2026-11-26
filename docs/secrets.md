# Secrets and encryption

## Environment secrets

| Secret | Used by | Notes |
|--------|---------|--------|
| `POSTGRES_PASSWORD` | postgres, migrate | Owner role |
| `ZRADIUS_API_DB_PASSWORD` | api | App role password |
| `ZRADIUS_RUNTIME_DB_PASSWORD` | radius as `RADIUS_DB_PASSWORD` | Runtime role |
| `ZRADIUS_SECRET_KEY` | api, radius (startup only) | 32-byte hex key material for AES-GCM |
| `RADIUS_TEST_SECRET` | radius clients.conf localhost | ≥32 `[A-Za-z0-9]` |
| `ADMIN_TOKEN` | api optional | Legacy bearer |

`provision_roles.py` refuses passwords <32 chars, placeholders `replace_with*`, or non-distinct passwords among owner/api/runtime.

## Sealed NAS / proxy secrets

- Format: versioned AES-GCM envelope (`secret_crypto.seal` / `unseal`)
- API decrypts for CoA; FreeRADIUS entrypoint renders client/proxy snippets at **startup**

## Operational rules

1. Generate `ZRADIUS_SECRET_KEY` once; store offline backup separate from DB dumps
2. Never rotate by regenerating the key without a designed re-encrypt procedure (not implemented)
3. Rendered FreeRADIUS client files contain **plaintext** secrets on the container filesystem
4. PPP Cleartext-Password and similar RADIUS credential attributes are **not** covered by this envelope
